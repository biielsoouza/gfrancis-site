/**
 * Contador de visitas do site — os visitantes não recebem cookie e nada que os identifique (nem IP) é guardado.
 *
 *   POST /api/evento   {e, p, r}  → soma 1 no dia (e = tipo do evento, p = página, r = site de origem)
 *   GET  /api/painel?dias=30      → totais por dia, origens e páginas, para a página /painel/ (só com senha)
 *   GET  /api/painel/estado        → se a senha já foi criada e se este navegador está logado
 *   POST /api/painel/criar|entrar|sair
 *
 * Senha do painel: criada pelo dono no primeiro acesso e guardada só como hash (PBKDF2) no KV, em "painel:senha".
 * O login vira um cookie assinado (HttpOnly) válido por 180 dias; o navegador logado também deixa de contar como visita.
 * Bloqueio: 5 senhas erradas seguidas travam o login por 15 minutos naquela conexão. Para isso guarda, só por
 * 15 minutos, um código embaralhado da conexão (nunca o IP em si) com o número de tentativas.
 * Esqueceu a senha? Apague a chave "painel:senha" no KV "gfrancis-visitas" (painel da Cloudflare) e crie outra.
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
  if (await logado(request, env)) return vazio;   // o próprio dono não conta como visita
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

// ---------- Senha do painel ----------
const COOKIE = "gf_painel";
const DIAS_LOGIN = 180;
const enc = new TextEncoder();
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const aleatorio = (n) => hex(crypto.getRandomValues(new Uint8Array(n)));

async function pbkdf2(senha, sal, iter = 100000) {
  const chave = await crypto.subtle.importKey("raw", enc.encode(senha), "PBKDF2", false, ["deriveBits"]);
  return hex(await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: enc.encode(sal), iterations: iter }, chave, 256));
}
async function hmac(segredo, texto) {
  const k = await crypto.subtle.importKey("raw", enc.encode(segredo), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, enc.encode(texto)));
}
function igual(a, b) {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
const MAX_TENTATIVAS = 5, BLOQUEIO_MIN = 15;
async function chaveTentativas(request, cfg) {
  const ip = request.headers.get("cf-connecting-ip") || "sem-ip";
  return `painel:falhas:${(await hmac(cfg.segredo, ip)).slice(0, 24)}`;
}
const lerSenha = async (env) => JSON.parse((await env.VISITAS.get("painel:senha")) || "null");

async function logado(request, env) {
  const m = (request.headers.get("cookie") || "").match(new RegExp(`(?:^|;\\s*)${COOKIE}=([0-9]+)\\.([0-9a-f]{64})`));
  if (!m || +m[1] < Date.now()) return false;
  const cfg = await lerSenha(env);
  return !!cfg && igual(await hmac(cfg.segredo, m[1]), m[2]);
}

async function cookieDeLogin(cfg) {
  const ate = Date.now() + DIAS_LOGIN * 86400000;
  return `${COOKIE}=${ate}.${await hmac(cfg.segredo, String(ate))}; Path=/; Max-Age=${DIAS_LOGIN * 86400}; HttpOnly; Secure; SameSite=Strict`;
}
const resp = (corpo, status = 200, cookie) => new Response(JSON.stringify(corpo), { status, headers: {
  "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...(cookie ? { "Set-Cookie": cookie } : {}) } });

/** Todas as rotas /api/painel*. */
export async function rotasPainel(request, url, env) {
  if (!env.VISITAS) return resp({ erro: "contador não configurado" }, 503);
  const rota = url.pathname.replace("/api/painel", "") || "/";
  const cfg = await lerSenha(env);
  if (rota === "/estado") return resp({ configurada: !!cfg, logado: await logado(request, env) });
  if (request.method === "POST") {
    let d = {};
    try { d = JSON.parse(await request.text()); } catch {}
    const senha = String(d.senha || "");
    if (rota === "/criar") {
      if (cfg) return resp({ erro: "A senha já foi criada." }, 409);
      if (senha.length < 8) return resp({ erro: "Use pelo menos 8 caracteres." }, 400);
      const sal = aleatorio(16), novo = { sal, hash: await pbkdf2(senha, sal), iter: 100000, segredo: aleatorio(32), criada_em: new Date().toISOString() };
      await env.VISITAS.put("painel:senha", JSON.stringify(novo));
      return resp({ ok: true }, 200, await cookieDeLogin(novo));
    }
    if (rota === "/entrar") {
      if (!cfg) return resp({ erro: "Crie a senha primeiro." }, 409);
      const chave = await chaveTentativas(request, cfg);
      const t = JSON.parse((await env.VISITAS.get(chave)) || '{"n":0}');
      if (t.ate && t.ate > Date.now()) {
        const min = Math.ceil((t.ate - Date.now()) / 60000);
        return resp({ erro: `Muitas senhas erradas. Tente de novo em ${min} minuto${min > 1 ? "s" : ""}.`, bloqueado: true }, 429);
      }
      if (!igual(await pbkdf2(senha, cfg.sal, cfg.iter), cfg.hash)) {
        const n = (t.ate ? 0 : t.n) + 1;   // depois de um bloqueio vencido, a contagem recomeça
        const novo = n >= MAX_TENTATIVAS ? { n, ate: Date.now() + BLOQUEIO_MIN * 60000 } : { n };
        await env.VISITAS.put(chave, JSON.stringify(novo), { expirationTtl: BLOQUEIO_MIN * 60 });
        await new Promise((r) => setTimeout(r, 800));   // freia tentativas em sequência
        if (novo.ate) return resp({ erro: `Muitas senhas erradas. O login ficou bloqueado por ${BLOQUEIO_MIN} minutos.`, bloqueado: true }, 429);
        const resta = MAX_TENTATIVAS - n;
        return resp({ erro: `Senha incorreta. ${resta === 1 ? "Mais 1 erro" : `Mais ${resta} erros`} e o login fica bloqueado por ${BLOQUEIO_MIN} minutos.` }, 401);
      }
      if (t.n) await env.VISITAS.put(chave, '{"n":0}', { expirationTtl: 60 });
      return resp({ ok: true }, 200, await cookieDeLogin(cfg));
    }
    if (rota === "/sair") return resp({ ok: true }, 200, `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`);
  }
  if (rota === "/") {
    if (!(await logado(request, env))) return resp({ erro: "Entre com a senha." }, 401);
    return resp(await painel(url, env));
  }
  return resp({ erro: "rota não encontrada" }, 404);
}
