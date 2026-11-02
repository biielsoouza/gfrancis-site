/**
 * /api/cotacoes na Netlify. A lógica fica em ../../cotacoes/nucleo.mjs
 * (a mesma usada pelo Worker da Cloudflare). O token vem da variável BRAPI_TOKEN.
 */
import { buscarCotacoes } from "../../cotacoes/nucleo.mjs";

export default async () => {
  const { corpo, ttl, status } = await buscarCotacoes(process.env.BRAPI_TOKEN || "");
  return new Response(JSON.stringify(corpo), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=60",
      "Netlify-CDN-Cache-Control": `public, durable, s-maxage=${ttl}, stale-while-revalidate=300`,
    },
  });
};

export const config = { path: "/api/cotacoes" };
