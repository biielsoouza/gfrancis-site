/**
 * Gráficos — histórico de preços e lista de ativos para a busca
 *
 *   historico(ativo, periodo, token)  → candles diários de uma ação, índice ou minicontrato
 *   ativos(token)                      → lista de códigos e nomes para o campo de busca
 *
 * Ações e índices vêm da brapi (plano gratuito: até 3 meses de histórico, com token).
 * WIN e WDO vêm da API de futuros da brapi, que libera esses dois sem token
 * (fechamento de cada pregão, atualizado à noite). Quem chama (o Worker) guarda
 * as respostas em cache, então cada gráfico gasta poucas consultas por dia.
 */
import { BASE, contratosVigentes, emPregao, pegarJson } from "./nucleo.mjs";

export const PERIODOS = { "5d": 5, "1mo": 31, "3mo": 92 };

// Usada se a brapi não devolver a lista completa: os ativos mais negociados.
const RESERVA = [
  ["IBOV", "Ibovespa", "indice"], ["PETR4", "Petrobras PN"], ["PETR3", "Petrobras ON"], ["VALE3", "Vale ON"],
  ["ITUB4", "Itaú Unibanco PN"], ["BBDC4", "Bradesco PN"], ["BBAS3", "Banco do Brasil ON"], ["B3SA3", "B3 ON"],
  ["WEGE3", "WEG ON"], ["ABEV3", "Ambev ON"], ["MGLU3", "Magazine Luiza ON"], ["PRIO3", "PRIO ON"],
  ["SUZB3", "Suzano ON"], ["RENT3", "Localiza ON"], ["ITSA4", "Itaúsa PN"], ["BBSE3", "BB Seguridade ON"],
  ["ELET3", "Eletrobras ON"], ["GGBR4", "Gerdau PN"], ["RADL3", "Raia Drogasil ON"], ["LREN3", "Lojas Renner ON"],
  ["EQTL3", "Equatorial ON"], ["RAIL3", "Rumo ON"], ["VIVT3", "Telefônica Brasil ON"], ["CSAN3", "Cosan ON"],
  ["HAPV3", "Hapvida ON"], ["JBSS3", "JBS ON"], ["EMBR3", "Embraer ON"], ["TOTS3", "Totvs ON"],
  ["SANB11", "Santander Unit"], ["BPAC11", "BTG Pactual Unit"], ["CMIG4", "Cemig PN"], ["CPLE6", "Copel PNB"],
  ["KLBN11", "Klabin Unit"], ["CSNA3", "CSN ON"], ["USIM5", "Usiminas PNA"], ["AZUL4", "Azul PN"],
  ["NTCO3", "Natura ON"], ["COGN3", "Cogna ON"], ["BOVA11", "iShares Ibovespa (ETF)"], ["IVVB11", "iShares S&P 500 (ETF)"],
];

/** WIN e WDO no topo da lista, já com o contrato vigente. */
function futurosDaLista() {
  const [win, wdo] = contratosVigentes();
  return [
    { codigo: "WIN", nome: `Mini Ibovespa · contrato ${win}`, tipo: "futuro" },
    { codigo: "WDO", nome: `Mini dólar · contrato ${wdo}`, tipo: "futuro" },
  ];
}

export async function ativos(token = "") {
  let lista = [], daBrapi = false;
  try {
    // brapi v1: lista com código, nome e tipo (ação, fundo, BDR...).
    const json = await pegarJson(`https://brapi.dev/api/quote/list?limit=2000&sortBy=volume&sortOrder=desc${token ? `&token=${token}` : ""}`);
    lista = (json.stocks || []).map((s) => ({ codigo: s.stock, nome: s.name || "", tipo: s.type || "acao" }));
    for (const i of json.indexes || []) lista.unshift({ codigo: i.stock === "^BVSP" ? "IBOV" : i.stock, nome: i.name || "", tipo: "indice" });
  } catch (e) {
    console.log("ativos: lista da brapi falhou, usando a reserva", String(e.message || e));
  }
  daBrapi = lista.length >= 20;
  if (!daBrapi) lista = RESERVA.map(([codigo, nome, tipo]) => ({ codigo, nome, tipo: tipo || "acao" }));
  const vistos = new Set();
  const final = [...futurosDaLista(), ...lista].filter((a) => a.codigo && !vistos.has(a.codigo) && vistos.add(a.codigo));
  return { ativos: final, completa: daBrapi };
}

const iso = (d) => d.toISOString().slice(0, 10);
const num = (v) => (v == null || v === "" || Number.isNaN(Number(v)) ? null : Number(v));
// Datas da brapi podem vir em segundos (unix) ou como texto "2026-10-30".
const paraData = (v) => (typeof v === "number" ? new Date(v * 1000) : new Date(String(v).length === 10 ? `${v}T12:00:00Z` : v));

/** Resolve o que a pessoa digitou: "win" → WINZ26, "^BVSP"/"IBOV" → índice, o resto como ação. */
export function resolverAtivo(entrada) {
  const a = String(entrada || "").trim().toUpperCase().replace(/[^A-Z0-9^]/g, "");
  if (!a) return null;
  const [win, wdo] = contratosVigentes();
  if (a === "WIN") return { pedido: a, codigo: win, tipo: "futuro" };
  if (a === "WDO") return { pedido: a, codigo: wdo, tipo: "futuro" };
  if (/^(WIN|WDO|IND|DOL)[FGHJKMNQUVXZ]\d{2}$/.test(a)) return { pedido: a, codigo: a, tipo: "futuro" };
  if (a === "IBOV" || a === "^BVSP") return { pedido: "IBOV", codigo: "^BVSP", tipo: "indice" };
  return { pedido: a, codigo: a, tipo: "acao" };
}

export async function historico(entrada, periodo = "1mo", token = "") {
  const r = resolverAtivo(entrada);
  if (!r) throw new Error("ativo vazio");
  if (!PERIODOS[periodo]) periodo = "1mo";
  let candles = [], nome = "", bruto;

  if (r.tipo === "futuro") {
    const fim = new Date(), inicio = new Date(Date.now() - PERIODOS[periodo] * 86400000 * 1.5);
    bruto = await pegarJson(`${BASE}/v2/futures/historical?symbol=${r.codigo}&startDate=${iso(inicio)}&endDate=${iso(fim)}&sortOrder=asc`);
    const fut = bruto.future || bruto.results?.[0] || bruto;
    nome = fut.assetDescription || (r.codigo.startsWith("WIN") ? "Mini Ibovespa" : r.codigo.startsWith("WDO") ? "Mini dólar" : "Contrato futuro");
    const linhas = fut.history || fut.historicalDataPrice || bruto.history || [];
    let anterior = null;
    for (const h of linhas) {
      const fech = num(h.close) ?? num(h.settlement);
      if (fech == null) continue;
      const ab = num(h.open) ?? anterior ?? fech;          // a B3 não informa abertura: usa o fechamento anterior
      candles.push({ t: paraData(h.date ?? h.tradeDate).getTime(), o: ab, h: num(h.high) ?? Math.max(ab, fech),
                     l: num(h.low) ?? Math.min(ab, fech), c: fech, v: num(h.volume) ?? num(h.trades) ?? 0 });
      anterior = fech;
    }
  } else {
    bruto = await pegarJson(`${BASE}/quote/${encodeURIComponent(r.codigo)}?range=${periodo}&interval=1d${token ? `&token=${token}` : ""}`);
    const q = (bruto.results || [])[0] || {};
    nome = q.longName || q.shortName || "";
    for (const h of q.historicalDataPrice || []) {
      const c = num(h.close);
      if (c == null) continue;
      candles.push({ t: paraData(h.date).getTime(), o: num(h.open) ?? c, h: num(h.high) ?? c, l: num(h.low) ?? c, c, v: num(h.volume) ?? 0 });
    }
  }
  candles.sort((a, b) => a.t - b.t);
  const corte = Date.now() - PERIODOS[periodo] * 86400000 - 86400000;
  candles = candles.filter((k) => k.t >= corte);
  if (!candles.length) throw new Error(`sem histórico para ${r.pedido}`);
  return {
    corpo: { ativo: r.pedido === "IBOV" ? "IBOV" : r.codigo, pedido: r.pedido, nome, tipo: r.tipo, periodo, candles,
             fonte: "brapi.dev", atualizado_em: new Date().toISOString(),
             aviso: r.tipo === "futuro" ? "Fechamento (ajuste) de cada pregão, atualizado à noite." : "Dados diários com atraso de cerca de 30 minutos." },
    bruto,
    ttl: emPregao() ? 900 : 6 * 3600,
  };
}
