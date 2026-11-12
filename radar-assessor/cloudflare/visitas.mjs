/**
 * Contador de visitas do site — sem cookies, sem IP e sem nenhum dado pessoal.
 *
 *   POST /api/evento   {e, p, r}  → soma 1 no dia (e = tipo do evento, p = página, r = site de origem)
 *   GET  /api/painel?dias=30      → totais por dia, origens e páginas, para a página /painel/
 *
 * Guarda um registro por dia no KV "VISITAS" (chave "dia:AAAA-MM-DD"), por 400 dias.
 * Como o KV não soma de forma atômica, dois acessos no mesmo instante podem contar como um: os números são aproximados.
 */
export const EVENTOS = ["visita", "curriculo", "whatsapp", "linkedin", "email", "ferramenta"];
const ROBO = /bot|crawl|spider|slurp|preview|monitor|headless|lighthouse|curl|wget|python|go-http/i;

const hoje = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
const limpar = (s, max) => String(s || "").toLowerCase().replace(/[^a-z0-9./_-]/g, "").slice(0, max);

export async function registrar(request, env) {
  const vazio = new Response(null, { status: 204 });
  if (!env.VISITAS || ROBO.test(request.headers.get("user-agent") || "")) return vazio;
  let d;
  try { d = JSON.parse(await request.text()); } catch { return vazio; }
  if (!d || !EVENTOS.includes(d.e)) return vazio;
  const chave = `dia:${hoje()}`;
  const reg = JSON.parse((await env.VISITAS.get(chave)) || "{}");
  reg[d.e] = (reg[d.e] || 0) + 1;
  if (d.e === "visita") {
    const pagina = limpar(d.p, 60) || "/";
    const origem = limpar(d.r, 60).replace(/^www\./, "") || "direto";
    (reg.paginas ||= {})[pagina] = (reg.paginas[pagina] || 0) + 1;
    (reg.origens ||= {})[origem] = (reg.origens[origem] || 0) + 1;
    const pais = limpar(request.cf && request.cf.country, 2).toUpperCase();
    if (pais) (reg.paises ||= {})[pais] = (reg.paises[pais] || 0) + 1;
  }
  await env.VISITAS.put(chave, JSON.stringify(reg), { expirationTtl: 400 * 86400 });
  return vazio;
}

export async function painel(url, env) {
  const dias = Math.min(90, Math.max(1, +url.searchParams.get("dias") || 30));
  const lista = [];
  const base = new Date(`${hoje()}T12:00:00Z`);
  for (let i = dias - 1; i >= 0; i--) lista.push(new Date(base - i * 86400000).toISOString().slice(0, 10));
  const regs = await Promise.all(lista.map(async (dia) => ({ dia, ...JSON.parse((await env.VISITAS.get(`dia:${dia}`)) || "{}") })));
  const somar = (campo) => {
    const t = {};
    for (const r of regs) for (const [k, v] of Object.entries(r[campo] || {})) t[k] = (t[k] || 0) + v;
    return Object.entries(t).sort((a, b) => b[1] - a[1]).slice(0, 12);
  };
  return {
    dias: regs.map((r) => ({ dia: r.dia, ...Object.fromEntries(EVENTOS.map((e) => [e, r[e] || 0])) })),
    origens: somar("origens"), paginas: somar("paginas"), paises: somar("paises"),
  };
}
