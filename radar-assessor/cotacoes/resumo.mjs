/**
 * Resumo do pregão escrito por IA — usado por /api/resumo (cloudflare/worker.mjs).
 *
 * Parte das cotações do mural (/api/cotacoes) e pede a um modelo de linguagem da própria
 * Cloudflare (Workers AI, binding "AI" no wrangler.jsonc) um texto curto em português.
 * A IA só descreve os números que recebe: não inventa notícia nem motivo, e não recomenda nada.
 * Se a IA falhar ou não estiver disponível, o resumo é montado por regras simples, para a página nunca ficar vazia.
 */
export const MODELO = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";

const pct = (v) => (v == null ? "s/d" : `${v > 0 ? "+" : ""}${v.toFixed(2).replace(".", ",")}%`);
const preco = (v, casas = 2) => v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

/** Organiza as cotações em fatos simples (o que entra no texto). */
export function fatos(cot) {
  const itens = (cot.itens || []).filter((i) => i.preco != null);
  const ibov = itens.find((i) => i.simbolo === "IBOV");
  const acoes = itens.filter((i) => i.tipo === "acao" && i.variacao != null).sort((a, b) => b.variacao - a.variacao);
  const win = itens.find((i) => i.simbolo.startsWith("WIN"));
  const wdo = itens.find((i) => i.simbolo.startsWith("WDO"));
  const altas = acoes.filter((a) => a.variacao > 0).length;
  return { ibov, acoes, win, wdo, altas, baixas: acoes.filter((a) => a.variacao < 0).length, em_pregao: !!cot.em_pregao };
}

export function textoDosFatos(f) {
  const l = [];
  if (f.ibov) l.push(`Ibovespa: ${preco(f.ibov.preco, 0)} pontos (${pct(f.ibov.variacao)})`);
  for (const a of f.acoes) l.push(`${a.simbolo} (${a.nome}): R$ ${preco(a.preco)} (${pct(a.variacao)})`);
  if (f.win) l.push(`Minicontrato de Ibovespa ${f.win.simbolo}: ${preco(f.win.preco, 0)} pontos no último ajuste (${pct(f.win.variacao)})`);
  if (f.wdo) l.push(`Minicontrato de dólar ${f.wdo.simbolo}: ${preco(f.wdo.preco, 1)} no último ajuste (${pct(f.wdo.variacao)})`);
  l.push(`Ações em alta: ${f.altas}; em baixa: ${f.baixas}`);
  l.push(f.em_pregao ? "Situação: pregão aberto (cotações com atraso de cerca de 30 minutos)" : "Situação: pregão fechado (números do último pregão)");
  return l.join("\n");
}

/** Resumo sem IA: frases montadas por regra. */
export function resumoPorRegras(f) {
  const dir = (v) => (v == null ? "estável" : v > 0.15 ? "em alta" : v < -0.15 ? "em queda" : "perto da estabilidade");
  const manchete = f.ibov
    ? `Ibovespa ${dir(f.ibov.variacao)}, ${pct(f.ibov.variacao)}, aos ${preco(f.ibov.preco, 0)} pontos`
    : "Resumo das principais cotações";
  const pontos = [];
  if (f.acoes.length) {
    const m = f.acoes[0], p = f.acoes[f.acoes.length - 1];
    pontos.push(`Entre as ações acompanhadas, ${f.altas} sobem e ${f.baixas} caem. A maior alta é ${m.nome} (${m.simbolo}, ${pct(m.variacao)}) e a maior queda, ${p.nome} (${p.simbolo}, ${pct(p.variacao)}).`);
  }
  if (f.win) pontos.push(`O minicontrato de Ibovespa (${f.win.simbolo}) fechou o último ajuste em ${preco(f.win.preco, 0)} pontos, ${pct(f.win.variacao)}.`);
  if (f.wdo) pontos.push(`O minicontrato de dólar (${f.wdo.simbolo}) ficou em ${preco(f.wdo.preco, 1)}, ${pct(f.wdo.variacao)}.`);
  return { manchete, pontos };
}

const INSTRUCAO = `Você escreve o resumo do pregão da bolsa brasileira para operadores de mesa.
Regras:
- Use SOMENTE os números fornecidos. Não invente notícias, causas, horários nem outros ativos.
- Português do Brasil, tom profissional e direto, frases curtas.
- Não faça recomendação de compra ou venda nem previsão.
- Responda APENAS com JSON válido, sem texto fora dele, no formato:
{"manchete": "uma frase de até 14 palavras", "pontos": ["frase 1", "frase 2", "frase 3"]}
- Os 3 pontos: (1) o Ibovespa e o quadro geral de altas e baixas; (2) os destaques entre as ações; (3) os minicontratos WIN e WDO.`;

function lerJson(texto) {
  if (texto && typeof texto === "object") return texto;
  const m = String(texto || "").match(/\{[\s\S]*\}/);
  if (!m) return null;
  try { return JSON.parse(m[0]); } catch { return null; }
}

/** Gera o resumo. `ai` é o binding do Workers AI (pode faltar). */
export async function gerarResumo(cot, ai) {
  const f = fatos(cot);
  const base = { gerado_em: new Date().toISOString(), em_pregao: f.em_pregao, cotacoes_de: cot.atualizado_em || null,
    itens: (cot.itens || []).map(({ simbolo, nome, tipo, preco, variacao }) => ({ simbolo, nome, tipo, preco, variacao })) };
  if (!f.ibov && !f.acoes.length) return { ...base, ia: false, ...resumoPorRegras(f) };
  if (ai) {
    try {
      const r = await ai.run(MODELO, {
        messages: [{ role: "system", content: INSTRUCAO }, { role: "user", content: `Números de agora:\n${textoDosFatos(f)}` }],
        max_tokens: 400, temperature: 0.3,
      });
      const j = lerJson(r && r.response);
      const pontos = j && Array.isArray(j.pontos) ? j.pontos.map((p) => String(p).trim()).filter(Boolean).slice(0, 4) : [];
      if (j && typeof j.manchete === "string" && j.manchete.trim() && pontos.length) {
        return { ...base, ia: true, manchete: j.manchete.trim().replace(/\.$/, ""), pontos };
      }
      console.log("resumo: resposta da IA fora do formato", JSON.stringify(r).slice(0, 300));
    } catch (e) {
      console.log("resumo: IA falhou", String(e.message || e));
    }
  }
  return { ...base, ia: false, ...resumoPorRegras(f) };
}
