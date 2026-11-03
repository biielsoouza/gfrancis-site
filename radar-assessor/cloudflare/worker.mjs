/**
 * Worker da Cloudflare do gfrancis.com.br
 *
 * As páginas (início e Radar) são arquivos estáticos servidos direto pela Cloudflare,
 * sem passar por aqui. Este código só atende /api/cotacoes (veja wrangler.jsonc na raiz):
 * busca as cotações (cotacoes/nucleo.mjs) e guarda a resposta no cache da Cloudflare,
 * 15 min durante o pregão e 4 h fora dele. O token fica no segredo BRAPI_TOKEN,
 * configurado no painel da Cloudflare (Worker > Configurações > Variáveis e segredos).
 */
import { buscarCotacoes } from "../cotacoes/nucleo.mjs";

const VERSAO_CACHE = "2";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname !== "/api/cotacoes") return new Response("Não encontrado", { status: 404 });

    const cache = caches.default;
    // Mudar VERSAO_CACHE faz o Worker ignorar respostas antigas guardadas no cache.
    const chave = new Request(`${url.origin}/api/cotacoes?cache=${VERSAO_CACHE}`, { method: "GET" });
    const guardada = await cache.match(chave);
    if (guardada) return guardada;

    const { corpo, ttl, status } = await buscarCotacoes(env.BRAPI_TOKEN || "");
    const resposta = new Response(JSON.stringify(corpo), {
      status,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": `public, max-age=${ttl}` },
    });
    if (status === 200) ctx.waitUntil(cache.put(chave, resposta.clone()));
    // Para o navegador, só 1 minuto: o cache longo fica do lado da Cloudflare.
    const saida = new Response(resposta.body, resposta);
    saida.headers.set("Cache-Control", "public, max-age=60");
    return saida;
  },
};
