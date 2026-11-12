/**
 * Worker da Cloudflare do gfrancis.com.br
 *
 * As páginas (início e Radar) são arquivos estáticos servidos direto pela Cloudflare,
 * sem passar por aqui. Este código só atende /api/* (veja wrangler.jsonc na raiz):
 *   /api/cotacoes                         mural de cotações (cotacoes/nucleo.mjs)
 *   /api/historico?ativo=PETR4&periodo=1mo  candles diários para a aba Gráficos
 *   /api/ativos                           lista de códigos para a busca de ativos
 *   /api/resumo                           resumo do pregão escrito por IA (cotacoes/resumo.mjs)
 *   /api/analise[?dia=AAAA-MM-DD]          análise da manhã feita por IA, guardada no KV (cotacoes/analise.mjs)
 *   /api/analise/dias                     datas com análise guardada
 * Agendamento (triggers.crons no wrangler.jsonc): todo dia útil às 7h40 de Brasília refaz a análise da manhã.
 * As respostas ficam no cache da Cloudflare (minutos durante o pregão, horas fora dele),
 * então a brapi é pouco consultada. O token fica no segredo BRAPI_TOKEN do Worker.
 */
import { buscarCotacoes } from "../cotacoes/nucleo.mjs";
import { ativos, historico, PERIODOS } from "../cotacoes/mercado.mjs";
import { gerarResumo } from "../cotacoes/resumo.mjs";
import { gerarEGuardar } from "../cotacoes/analise.mjs";
import { emPregao } from "../cotacoes/nucleo.mjs";

// Mudar VERSAO_CACHE faz o Worker ignorar respostas antigas guardadas no cache.
const VERSAO_CACHE = "3";

const json = (corpo, status = 200, segundos = 60) => new Response(JSON.stringify(corpo), {
  status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": `public, max-age=${segundos}` },
});

async function comCache(chaveUrl, ctx, gerar) {
  const cache = caches.default;
  const chave = new Request(`${chaveUrl}${chaveUrl.includes("?") ? "&" : "?"}cache=${VERSAO_CACHE}`, { method: "GET" });
  const guardada = await cache.match(chave);
  if (guardada) return guardada;
  const { corpo, ttl, status = 200 } = await gerar();
  if (status === 200) ctx.waitUntil(cache.put(chave, json(corpo, 200, ttl)));
  return json(corpo, status, 60);   // para o navegador, só 1 minuto
}

const hojeEmBrasilia = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
const horaEmBrasilia = () => +new Intl.DateTimeFormat("en-US", { timeZone: "America/Sao_Paulo", hour: "numeric", hour12: false }).format(new Date()) % 24;
const diaUtil = () => !["Sat", "Sun"].includes(new Intl.DateTimeFormat("en-US", { timeZone: "America/Sao_Paulo", weekday: "short" }).format(new Date()));

async function analise(url, env) {
  if (!env.ANALISE) return json({ erro: "armazenamento da análise não configurado" }, 503, 0);
  if (url.pathname === "/api/analise/dias") return json(JSON.parse((await env.ANALISE.get("dias")) || "[]"), 200, 300);
  const dia = url.searchParams.get("dia");
  if (dia) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dia)) return json({ erro: "data inválida" }, 400, 0);
    const salvo = await env.ANALISE.get(`dia:${dia}`);
    return salvo ? new Response(salvo, { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=3600" } })
      : json({ erro: "sem análise nesse dia" }, 404, 300);
  }
  let atual = await env.ANALISE.get("atual");
  // Se o agendamento falhou (ou é a primeira vez), refaz agora: dia útil, depois das 7h e ainda sem a análise de hoje.
  const velha = !atual || (diaUtil() && horaEmBrasilia() >= 7 && JSON.parse(atual).dia !== hojeEmBrasilia());
  if (velha) {
    try { atual = JSON.stringify(await gerarEGuardar(env)); } catch (e) { if (!atual) throw e; }
  }
  return new Response(atual, { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=300" } });
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(gerarEGuardar(env).then((a) => console.log("analise: gerada", a.dia, a.ia ? "com IA" : "por regras")));
  },

  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const token = env.BRAPI_TOKEN || "";
    try {
      if (url.pathname === "/api/cotacoes") {
        return await comCache(`${url.origin}/api/cotacoes`, ctx, () => buscarCotacoes(token));
      }
      if (url.pathname === "/api/analise" || url.pathname === "/api/analise/dias") return await analise(url, env);
      if (url.pathname === "/api/resumo") {
        // O texto da IA fica guardado 30 minutos no pregão e 4 horas fora dele.
        return await comCache(`${url.origin}/api/resumo`, ctx, async () => {
          const cot = await (await comCache(`${url.origin}/api/cotacoes`, ctx, () => buscarCotacoes(token))).json();
          const corpo = await gerarResumo(cot, env.AI);
          return { corpo, ttl: !corpo.itens.length ? 60 : emPregao() ? 1800 : 4 * 3600, status: corpo.itens.length ? 200 : 503 };
        });
      }
      if (url.pathname === "/api/ativos") {
        return await comCache(`${url.origin}/api/ativos`, ctx, async () => ({ corpo: await ativos(token), ttl: 24 * 3600 }));
      }
      if (url.pathname === "/api/historico") {
        const ativo = (url.searchParams.get("ativo") || "IBOV").toUpperCase().replace(/[^A-Z0-9^.]/g, "").slice(0, 12);
        const periodo = PERIODOS[url.searchParams.get("periodo")] ? url.searchParams.get("periodo") : "1mo";
        if (url.searchParams.get("bruto") === "1") {
          // Diagnóstico: a resposta original da brapi (sem cache, sem o token).
          const { bruto } = await historico(ativo, periodo, token);
          return json(bruto, 200, 0);
        }
        return await comCache(`${url.origin}/api/historico?ativo=${ativo}&periodo=${periodo}`, ctx,
          async () => { const { corpo, ttl } = await historico(ativo, periodo, token); return { corpo, ttl }; });
      }
      return json({ erro: "não encontrado" }, 404);
    } catch (e) {
      return json({ erro: String(e.message || e).replace(/token=[^&\s]+/g, "token=***") }, 502, 0);
    }
  },
};
