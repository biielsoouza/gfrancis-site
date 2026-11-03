/**
 * Worker da Cloudflare do gfrancis.com.br
 *
 * As páginas (início e Radar) são arquivos estáticos servidos direto pela Cloudflare,
 * sem passar por aqui. Este código só atende /api/* (veja wrangler.jsonc na raiz):
 *   /api/cotacoes                         mural de cotações (cotacoes/nucleo.mjs)
 *   /api/historico?ativo=PETR4&periodo=1mo  candles diários para a aba Gráficos
 *   /api/ativos                           lista de códigos para a busca de ativos
 * As respostas ficam no cache da Cloudflare (minutos durante o pregão, horas fora dele),
 * então a brapi é pouco consultada. O token fica no segredo BRAPI_TOKEN do Worker.
 */
import { buscarCotacoes } from "../cotacoes/nucleo.mjs";
import { ativos, historico, PERIODOS } from "../cotacoes/mercado.mjs";

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

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const token = env.BRAPI_TOKEN || "";
    try {
      if (url.pathname === "/api/cotacoes") {
        return await comCache(`${url.origin}/api/cotacoes`, ctx, () => buscarCotacoes(token));
      }
      if (url.pathname === "/api/ativos") {
        return await comCache(`${url.origin}/api/ativos`, ctx, async () => ({ corpo: await ativos(token), ttl: 24 * 3600 }));
      }
      if (url.pathname === "/api/historico") {
        const ativo = (url.searchParams.get("ativo") || "IBOV").toUpperCase().slice(0, 12);
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
