/**
 * Mural de cotações — função da Netlify em /api/cotacoes
 *
 * Busca as cotações na brapi.dev e devolve tudo num JSON só, já no formato do mural.
 * O token fica na variável de ambiente BRAPI_TOKEN (configurada na Netlify),
 * nunca no código nem no navegador.
 *
 * Para não estourar o plano gratuito (15 mil consultas por mês, 1 ativo por consulta),
 * a resposta fica guardada no cache da Netlify:
 *   - durante o pregão (seg a sex, 10h às 18h30, horário de Brasília): 15 minutos;
 *   - fora do pregão: 4 horas.
 * Não importa quantas pessoas abram o site: a brapi só é chamada quando o cache vence.
 *
 * O dólar comercial não vem daqui: o plano gratuito da brapi não inclui moedas e a AwesomeAPI
 * bloqueia servidores compartilhados. O próprio navegador de quem visita busca o dólar na AwesomeAPI.
 * As cotações do plano gratuito têm atraso de cerca de 30 minutos. Os minicontratos
 * (WIN e WDO) vêm do fechamento (ajuste) do último pregão.
 */

const ACOES = [
  ["^BVSP", "Ibovespa"],
  ["PETR4", "Petrobras"],
  ["VALE3", "Vale"],
  ["ITUB4", "Itaú"],
  ["BBDC4", "Bradesco"],
  ["BBAS3", "Banco do Brasil"],
  ["B3SA3", "B3"],
  ["WEGE3", "WEG"],
  ["ABEV3", "Ambev"],
];
const BASE = "https://brapi.dev/api";
const LETRAS = "FGHJKMNQUVXZ";

// Guarda a última resposta boa enquanto a função estiver "quente": se a brapi falhar, o mural não some.
let ultimaBoa = null;

function agoraEmBrasilia() {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Sao_Paulo", year: "numeric", month: "numeric", day: "numeric",
    hour: "numeric", minute: "numeric", weekday: "short", hour12: false,
  }).formatToParts(new Date()).map((x) => [x.type, x.value]));
  return { ano: +p.year, mes: +p.month, dia: +p.day, hora: +p.hour % 24, minuto: +p.minute, semana: p.weekday };
}

function emPregao() {
  const a = agoraEmBrasilia();
  if (a.semana === "Sat" || a.semana === "Sun") return false;
  const min = a.hora * 60 + a.minuto;
  return min >= 10 * 60 && min <= 18 * 60 + 30;
}

// Vencimentos B3: WIN vence na quarta-feira mais próxima do dia 15 dos meses pares;
// WDO vence no 1º dia útil do mês, então o contrato mais negociado é o do mês seguinte.
function quartaMaisProxima15(ano, mes) {
  const d = new Date(Date.UTC(ano, mes - 1, 15));
  const dif = (3 - d.getUTCDay() + 7) % 7;
  return dif <= 3 ? 15 + dif : 15 + dif - 7;
}
function contratosVigentes() {
  const { ano, mes, dia } = agoraEmBrasilia();
  let mWin = mes % 2 === 0 ? mes : mes + 1, aWin = ano;
  if (mWin === mes && dia >= quartaMaisProxima15(ano, mes)) mWin += 2;
  if (mWin > 12) { mWin -= 12; aWin += 1; }
  let mWdo = mes + 1, aWdo = ano;
  if (mWdo > 12) { mWdo = 1; aWdo += 1; }
  const cod = (ativo, m, a) => ativo + LETRAS[m - 1] + String(a % 100).padStart(2, "0");
  return [cod("WIN", mWin, aWin), cod("WDO", mWdo, aWdo)];
}

async function pegarJson(url, token) {
  const resp = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!resp.ok) throw new Error(`${resp.status} em ${url.replace(/token=[^&]+/, "token=***")}`);
  return resp.json();
}

async function acao(simbolo, nome, token) {
  const url = `${BASE}/quote/${encodeURIComponent(simbolo)}${token ? `?token=${token}` : ""}`;
  const json = await pegarJson(url);
  const r = (json.results || [])[0] || {};
  const d = r.data || r;                       // aceita o formato antigo e o novo da brapi
  if (d.regularMarketPrice == null) throw new Error(`sem preço para ${simbolo}`);
  return {
    simbolo: simbolo === "^BVSP" ? "IBOV" : simbolo, nome, tipo: simbolo.startsWith("^") ? "indice" : "acao",
    preco: d.regularMarketPrice, variacao: d.regularMarketChangePercent ?? null,
    quando: d.regularMarketTime || null,
  };
}

async function futuros() {
  // Sem token, a brapi libera a cotação de WIN e WDO (fechamento do último pregão).
  const simbolos = contratosVigentes();
  const json = await pegarJson(`${BASE}/v2/futures/quote?symbols=${simbolos.join(",")}`);
  return (json.quotes || []).map((q) => ({
    simbolo: q.symbol, nome: q.underlyingAsset === "WIN" ? "Mini Ibovespa" : "Mini dólar", tipo: "futuro",
    preco: q.settlement ?? q.close, variacao: q.oscillationPct ?? null,
    quando: q.date ? new Date(q.date * 1000).toISOString() : null,
  }));
}

export default async () => {
  const token = process.env.BRAPI_TOKEN || "";
  const itens = [], erros = [];
  // Uma consulta por vez (limite do plano gratuito).
  for (const [s, n] of ACOES) {
    try { itens.push(await acao(s, n, token)); } catch (e) { erros.push(String(e.message || e)); }
  }
  try { itens.push(...(await futuros())); } catch (e) { erros.push(String(e.message || e)); }

  const pregao = emPregao();
  let corpo = { atualizado_em: new Date().toISOString(), em_pregao: pregao, fonte: "brapi.dev",
                atraso: "cerca de 30 minutos", itens, erros: erros.length,
                falhas: erros.map((e) => e.slice(0, 160)) };
  if (erros.length) console.log("cotacoes: falhas", erros);
  if (itens.length) ultimaBoa = corpo;
  else if (ultimaBoa) corpo = { ...ultimaBoa, de_reserva: true };

  const ttl = !itens.length ? 60 : pregao ? 900 : 4 * 3600;
  return new Response(JSON.stringify(corpo), {
    status: corpo.itens.length ? 200 : 503,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=60",
      "Netlify-CDN-Cache-Control": `public, durable, s-maxage=${ttl}, stale-while-revalidate=300`,
    },
  });
};

export const config = { path: "/api/cotacoes" };
