/**
 * Análise do mercado da manhã — feita por IA, refeita todo dia útil antes da abertura.
 *
 * O Worker roda isto sozinho pelo agendamento (triggers.crons no wrangler.jsonc) e guarda o
 * resultado no KV "ANALISE": a análise do dia em "atual" e uma cópia por data em "dia:AAAA-MM-DD".
 * A página /analise/ só lê o que está guardado.
 *
 * Os números (variações, máximas, mínimas, média de 20 dias) são calculados aqui, no código.
 * A IA (Workers AI) só transforma esses números em texto: não inventa notícia nem causa e não recomenda nada.
 * Se a IA falhar, o texto é montado por regras.
 */
import { historico } from "./mercado.mjs";

export const MODELO = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
export const AVISO = "Análise feita por inteligência artificial a partir de dados de mercado. Não é dica nem recomendação de investimento.";

export const ATIVOS = [
  ["IBOV", "Ibovespa", "indice"], ["PETR4", "Petrobras", "acao"], ["VALE3", "Vale", "acao"], ["ITUB4", "Itaú", "acao"],
  ["BBDC4", "Bradesco", "acao"], ["BBAS3", "Banco do Brasil", "acao"], ["B3SA3", "B3", "acao"], ["WEGE3", "WEG", "acao"],
  ["ABEV3", "Ambev", "acao"], ["WIN", "Mini Ibovespa", "futuro"], ["WDO", "Mini dólar", "futuro"],
];

const r2 = (x) => (x == null || !Number.isFinite(x) ? null : Math.round(x * 100) / 100);
const varPct = (a, b) => (a != null && b ? r2((a / b - 1) * 100) : null);

/** Indicadores de um ativo a partir dos candles diários (do mais antigo ao mais novo). */
export function indicadores(candles) {
  const c = candles.map((k) => k.c);
  const n = c.length, ult = c[n - 1];
  const janela = candles.slice(-22);
  const max = Math.max(...janela.map((k) => k.h)), min = Math.min(...janela.map((k) => k.l));
  const mm20 = n >= 20 ? c.slice(-20).reduce((s, x) => s + x, 0) / 20 : null;
  return {
    fechamento: ult, data: new Date(candles[n - 1].t).toISOString().slice(0, 10),
    var_dia: varPct(ult, c[n - 2]), var_semana: varPct(ult, c[n - 6]), var_mes: varPct(ult, c[Math.max(0, n - 22)]),
    max_mes: max, min_mes: min, mm20: mm20 == null ? null : r2(mm20),
    acima_mm20: mm20 == null ? null : ult > mm20,
    posicao_faixa: max > min ? Math.round(((ult - min) / (max - min)) * 100) : null,   // 0 = na mínima do mês, 100 = na máxima
  };
}

export async function coletar(token) {
  const ativos = [], falhas = [];
  for (const [codigo, nome, tipo] of ATIVOS) {
    try {
      const { corpo } = await historico(codigo, "1mo", token);
      if (corpo.candles.length < 3) throw new Error("histórico curto");
      ativos.push({ codigo: tipo === "futuro" ? corpo.ativo : codigo, nome, tipo, ...indicadores(corpo.candles) });
    } catch (e) {
      falhas.push(`${codigo}: ${String(e.message || e).slice(0, 120)}`);
    }
  }
  return { ativos, falhas };
}

const pct = (v) => (v == null ? "s/d" : `${v > 0 ? "+" : ""}${v.toFixed(2).replace(".", ",")}%`);
const casas = (a) => (a.tipo === "indice" || a.codigo.startsWith("WIN") ? 0 : a.codigo.startsWith("WDO") ? 1 : 2);
const fmt = (a, v) => (v == null ? "s/d" : v.toLocaleString("pt-BR", { minimumFractionDigits: casas(a), maximumFractionDigits: casas(a) }));

export function textoDosFatos(ativos) {
  return ativos.map((a) => `${a.codigo} (${a.nome}): fechamento ${fmt(a, a.fechamento)} em ${a.data}; dia ${pct(a.var_dia)}; 5 pregões ${pct(a.var_semana)}; mês ${pct(a.var_mes)}; ` +
    `máxima do mês ${fmt(a, a.max_mes)}; mínima do mês ${fmt(a, a.min_mes)}; média de 20 dias ${fmt(a, a.mm20)} ` +
    `(${a.acima_mm20 == null ? "s/d" : a.acima_mm20 ? "acima" : "abaixo"}); posição na faixa do mês ${a.posicao_faixa ?? "s/d"}%`).join("\n");
}

const INSTRUCAO = `Você é analista de mercado e escreve a análise da manhã da bolsa brasileira para operadores de mesa.
Regras obrigatórias:
- Use SOMENTE os números fornecidos. Não invente notícias, causas, eventos, agenda, indicadores nem outros ativos.
- Não faça recomendação de compra ou venda, não sugira operações e não faça previsões de preço.
- Português do Brasil, tom profissional, frases curtas e diretas. Números no formato brasileiro (vírgula decimal).
- Responda APENAS com JSON válido, sem nada fora dele, neste formato:
{"titulo": "frase de até 12 palavras que resume o momento",
 "abertura": "2 ou 3 frases com o panorama geral",
 "secoes": [
   {"titulo": "Ibovespa", "texto": "3 a 4 frases: fechamento, variação no dia, na semana e no mês, posição em relação à média de 20 dias e à faixa do mês"},
   {"titulo": "Ações em destaque", "texto": "3 a 4 frases sobre as maiores altas e quedas no dia e no mês"},
   {"titulo": "Minicontratos", "texto": "3 a 4 frases sobre WIN e WDO: ajuste, variações e posição na faixa do mês"},
   {"titulo": "Níveis de referência", "texto": "2 ou 3 frases citando a máxima, a mínima do mês e a média de 20 dias do Ibovespa, do WIN e do WDO, apenas como referência, sem previsão"}
 ]}`;

function lerJson(t) {
  if (t && typeof t === "object") return t;
  const m = String(t || "").match(/\{[\s\S]*\}/);
  if (!m) return null;
  try { return JSON.parse(m[0]); } catch { return null; }
}

export function analisePorRegras(ativos) {
  const by = (c) => ativos.find((a) => a.codigo === c || a.codigo.startsWith(c));
  const ibov = by("IBOV"), win = by("WIN"), wdo = by("WDO");
  const acoes = ativos.filter((a) => a.tipo === "acao" && a.var_dia != null).sort((a, b) => b.var_dia - a.var_dia);
  const mes = [...acoes].sort((a, b) => (b.var_mes ?? -999) - (a.var_mes ?? -999));
  const tend = (a) => (a.acima_mm20 == null ? "" : a.acima_mm20 ? "acima da média de 20 dias" : "abaixo da média de 20 dias");
  const secoes = [];
  if (ibov) secoes.push({ titulo: "Ibovespa", texto: `O Ibovespa fechou em ${fmt(ibov, ibov.fechamento)} pontos, ${pct(ibov.var_dia)} no dia, ${pct(ibov.var_semana)} em 5 pregões e ${pct(ibov.var_mes)} no mês. Está ${tend(ibov)} e em ${ibov.posicao_faixa}% da faixa do mês (0% é a mínima, 100% a máxima).` });
  if (acoes.length) secoes.push({ titulo: "Ações em destaque", texto: `No dia, ${acoes[0].var_dia > 0 ? "a maior alta foi" : "o melhor desempenho foi de"} ${acoes[0].nome} (${pct(acoes[0].var_dia)}) e ${acoes.at(-1).var_dia < 0 ? "a maior queda, de" : "o pior, de"} ${acoes.at(-1).nome} (${pct(acoes.at(-1).var_dia)}). No mês, ${mes[0].nome} lidera (${pct(mes[0].var_mes)}) e ${mes.at(-1).nome} tem o pior desempenho (${pct(mes.at(-1).var_mes)}).` });
  const m = [win, wdo].filter(Boolean).map((a) => `${a.nome} (${a.codigo}) ajustou em ${fmt(a, a.fechamento)}, ${pct(a.var_dia)} no dia e ${pct(a.var_mes)} no mês, ${tend(a)}`);
  if (m.length) secoes.push({ titulo: "Minicontratos", texto: m.join(". ") + "." });
  const niveis = [ibov, win, wdo].filter(Boolean).map((a) => `${a.nome}: máxima do mês ${fmt(a, a.max_mes)}, mínima ${fmt(a, a.min_mes)}, média de 20 dias ${fmt(a, a.mm20)}`);
  if (niveis.length) secoes.push({ titulo: "Níveis de referência", texto: niveis.join(". ") + "." });
  return {
    titulo: ibov ? `Ibovespa ${ibov.var_dia >= 0 ? "sobe" : "cai"} ${pct(ibov.var_dia).replace(/^[+-]/, "")} no último pregão` : "Análise do mercado",
    abertura: ibov ? `O Ibovespa acumula ${pct(ibov.var_mes)} no mês. Entre as ações acompanhadas, ${acoes.filter((a) => a.var_dia > 0).length} subiram e ${acoes.filter((a) => a.var_dia < 0).length} caíram no último pregão.` : "",
    secoes,
  };
}

/** Faz a análise completa. `ai` = binding do Workers AI (pode faltar). */
export async function gerarAnalise(token, ai) {
  const { ativos, falhas } = await coletar(token);
  if (falhas.length) console.log("analise: falhas", falhas);
  const agora = new Date();
  const dia = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(agora);   // AAAA-MM-DD
  const base = { dia, gerado_em: agora.toISOString(), aviso: AVISO, ativos, falhas: falhas.length };
  if (!ativos.length) throw new Error("sem dados de mercado: " + falhas.join("; "));
  if (ai) {
    try {
      const r = await ai.run(MODELO, {
        messages: [{ role: "system", content: INSTRUCAO }, { role: "user", content: `Dados do último pregão e do último mês:\n${textoDosFatos(ativos)}` }],
        max_tokens: 1100, temperature: 0.3,
      });
      const j = lerJson(r && r.response);
      const secoes = j && Array.isArray(j.secoes) ? j.secoes.filter((s) => s && s.titulo && s.texto).map((s) => ({ titulo: String(s.titulo).trim(), texto: String(s.texto).trim() })) : [];
      if (j && j.titulo && secoes.length >= 3) {
        return { ...base, ia: true, titulo: String(j.titulo).trim().replace(/\.$/, ""), abertura: String(j.abertura || "").trim(), secoes };
      }
      console.log("analise: resposta da IA fora do formato", JSON.stringify(r).slice(0, 400));
    } catch (e) {
      console.log("analise: IA falhou", String(e.message || e));
    }
  }
  return { ...base, ia: false, ...analisePorRegras(ativos) };
}

/** Gera e guarda no KV (a do dia e o histórico dos últimos 30 dias). */
export async function gerarEGuardar(env) {
  const a = await gerarAnalise(env.BRAPI_TOKEN || "", env.AI);
  const json = JSON.stringify(a);
  await env.ANALISE.put("atual", json);
  await env.ANALISE.put(`dia:${a.dia}`, json, { expirationTtl: 40 * 86400 });
  const dias = JSON.parse((await env.ANALISE.get("dias")) || "[]").filter((d) => d !== a.dia);
  dias.unshift(a.dia);
  await env.ANALISE.put("dias", JSON.stringify(dias.slice(0, 30)));
  return a;
}
