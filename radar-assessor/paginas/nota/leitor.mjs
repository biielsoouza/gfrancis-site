/**
 * Leitor de nota de corretagem — tudo roda no navegador de quem usa; o PDF nunca sai do computador.
 *
 * Entende o layout padrão das notas (o mesmo da maioria das corretoras):
 *   - nota de futuros (BM&F): linhas "C/V  Mercadoria  Vencimento  Quantidade  Preço  Tipo  Valor  D/C";
 *   - nota de ações (Bovespa): linhas "1-BOVESPA  C/V  Tipo mercado  Título  Quantidade  Preço  Valor  D/C".
 * Do quadro "Resumo" pega custos e totais procurando os rótulos conhecidos.
 */

// Valor de 1 ponto por contrato, em reais.
export const MULTIPLICADOR = { WIN: 0.2, IND: 1, WDO: 10, DOL: 50 };

export const num = (t) => (t == null || t === "" ? null : Number(String(t).replace(/\./g, "").replace(",", ".")));
const semAcento = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Junta os pedaços de texto do PDF em linhas, na ordem da página. */
export async function linhasDoPdf(pdf) {
  const linhas = [];
  for (let p = 1; p <= pdf.numPages; p++) {
    const pagina = await pdf.getPage(p);
    const { items } = await pagina.getTextContent();
    const grupos = [];
    for (const it of items) {
      if (!it.str || !it.str.trim()) continue;
      const y = it.transform[5], x = it.transform[4];
      let g = grupos.find((g) => Math.abs(g.y - y) < 2.5);
      if (!g) grupos.push((g = { y, itens: [] }));
      g.itens.push({ x, t: it.str });
    }
    grupos.sort((a, b) => b.y - a.y);
    for (const g of grupos) linhas.push(g.itens.sort((a, b) => a.x - b.x).map((i) => i.t.trim()).join(" ").replace(/\s+/g, " "));
  }
  return linhas;
}

const RE_FUT = /^(C|V)\s+([A-Z]{3})\s?([FGHJKMNQUVXZ]\d{2})\b(?:\s+\d{2}\/\d{2}\/\d{4})?\s+(\d+)\s+([\d.]+,\d+)\s*(DAY ?TRADE|NORMAL)?(?:\s+([\d.]+,\d{2})\s*([DC])?)?/i;
const RE_ACAO = /(?:\d-)?BOVESPA\s+([CV])\s+(VISTA|FRACIONARIO|OPCAO DE COMPRA|OPCAO DE VENDA|EXERC OPC COMPRA|EXERC OPC VENDA|TERMO)\s+(.+?)\s+(?:[#D@*FBHTCIXYLAPR]{1,2}\s+)?(\d[\d.]*)\s+([\d.]+,\d{2,})\s+([\d.]+,\d{2})\s+([DC])\b/i;

// Rótulos do quadro "Resumo". [chave, rótulo que aparece na nota, nome mostrado na tela]
const ROTULOS = [
  ["ajuste_dt", "ajuste day trade", "Ajuste day trade"],
  ["ajuste_pos", "ajuste de posicao", "Ajuste de posição"],
  ["irrf_dt", "irrf day trade", "IRRF day trade (projeção)"],
  ["tx_operacional", "taxa operacional", "Taxa operacional"],
  ["tx_registro_bmf", "taxa registro bm&f", "Taxa de registro"],
  ["tx_bmf", "taxas bm&f", "Emolumentos e taxas B3"],
  ["outros_custos", "outros custos", "Outros custos"],
  ["total_despesas", "total das despesas", "Total das despesas"],
  ["liquido_nota", "total liquido da nota", "Líquido da nota"],
  ["vendas_vista", "vendas a vista", "Vendas à vista"],
  ["compras_vista", "compras a vista", "Compras à vista"],
  ["valor_liquido_ops", "valor liquido das operacoes", "Valor líquido das operações"],
  ["tx_liquidacao", "taxa de liquidacao", "Taxa de liquidação"],
  ["tx_registro", "taxa de registro", "Taxa de registro"],
  ["emolumentos", "emolumentos", "Emolumentos"],
  ["corretagem", "corretagem", "Corretagem"],
  ["execucao", "execucao", "Execução"],
  ["custodia", "taxa de custodia", "Taxa de custódia"],
  ["iss", "iss", "ISS"],
  ["irrf", "i.r.r.f.", "IRRF"],
  ["impostos", "impostos", "Impostos"],
  ["outros", "outros", "Outros"],
  ["total_custos", "total custos / despesas", "Total de custos"],
  ["liquido_para", "liquido para", "Líquido da nota"],
];

/** Lê o quadro de resumo: para cada rótulo, o último número antes do próximo rótulo da mesma linha. */
function lerResumo(linhas) {
  const r = {};
  for (const linha of linhas) {
    const base = semAcento(linha);
    const achados = [];
    for (const [chave, rot] of ROTULOS) {
      let i = base.indexOf(rot);
      while (i >= 0) {
        // evita que "taxa de registro" case dentro de "taxa registro bm&f" e afins
        if (!achados.some((a) => i >= a.ini && i < a.fim)) achados.push({ chave, ini: i, fim: i + rot.length });
        i = base.indexOf(rot, i + 1);
      }
    }
    achados.sort((a, b) => a.ini - b.ini || b.fim - a.fim);
    const limpos = achados.filter((a, k) => !achados.slice(0, k).some((b) => a.ini >= b.ini && a.ini < b.fim));
    limpos.forEach((a, k) => {
      const trecho = linha.slice(a.fim, k + 1 < limpos.length ? limpos[k + 1].ini : undefined);
      const nums = [...trecho.matchAll(/(-?[\d.]*\d,\d{2})(?:\s*([DC])\b)?/g)];
      if (!nums.length || r[a.chave] != null) return;
      const [, v, dc] = nums[nums.length - 1];
      r[a.chave] = { valor: num(v), dc: dc || null };
    });
  }
  return r;
}

const comSinal = (x) => (x ? (x.dc === "D" ? -x.valor : x.valor) : null);

/** Interpreta as linhas de uma nota. */
export function lerNota(linhas, arquivo = "") {
  const texto = linhas.join("\n");
  const data = (texto.match(/data\s*preg[aã]o\D{0,12}(\d{2}\/\d{2}\/\d{4})/i) || [])[1] || null;
  const numero = (texto.match(/n[rº°.]*\s*(?:da\s*)?nota\D{0,12}(\d{2,})/i) || [])[1] || null;

  const operacoes = [];
  for (const l of linhas) {
    let m = l.match(RE_FUT);
    if (m) {
      const [, cv, base, venc, qtd, preco, tipo, valor, dc] = m;
      operacoes.push({ mercado: "futuro", cv: cv.toUpperCase(), ativo: base.toUpperCase() + venc.toUpperCase(),
        base: base.toUpperCase(), qtd: +qtd, preco: num(preco), tipo: (tipo || "").toUpperCase().replace("DAYTRADE", "DAY TRADE") || "NORMAL",
        valor: valor ? num(valor) : null, dc: dc || null });
      continue;
    }
    m = l.match(RE_ACAO);
    if (m) {
      const [, cv, tipo, titulo, qtd, preco, valor, dc] = m;
      operacoes.push({ mercado: "acao", cv: cv.toUpperCase(), ativo: titulo.trim(), base: titulo.trim(), qtd: num(qtd),
        preco: num(preco), tipo: tipo.toUpperCase(), valor: num(valor), dc });
    }
  }

  const resumo = lerResumo(linhas);
  const tipo = operacoes.some((o) => o.mercado === "futuro") ? "futuros" : operacoes.length ? "acoes" : "desconhecido";

  // Resultado calculado por contrato (futuros): preço médio de venda − compra × quantidade zerada × valor do ponto.
  const contratos = [];
  if (tipo === "futuros") {
    const porAtivo = {};
    for (const o of operacoes) {
      const a = (porAtivo[o.ativo] ||= { ativo: o.ativo, base: o.base, qc: 0, vc: 0, qv: 0, vv: 0 });
      if (o.cv === "C") { a.qc += o.qtd; a.vc += o.qtd * o.preco; } else { a.qv += o.qtd; a.vv += o.qtd * o.preco; }
    }
    for (const a of Object.values(porAtivo)) {
      const mult = MULTIPLICADOR[a.base] ?? null;
      const pmc = a.qc ? a.vc / a.qc : null, pmv = a.qv ? a.vv / a.qv : null;
      const zerado = Math.min(a.qc, a.qv);
      const pontos = pmc != null && pmv != null ? pmv - pmc : null;
      contratos.push({ ativo: a.ativo, compras: a.qc, vendas: a.qv, pmc, pmv, zerado, aberto: a.qc - a.qv, pontos,
        resultado: mult != null && pontos != null ? Math.round(pontos * zerado * mult * 100) / 100 : null });
    }
  }

  // Números principais, já com sinal (+ crédito, − débito).
  let bruto, custos, liquido;
  if (tipo === "futuros") {
    bruto = comSinal(resumo.ajuste_dt) ?? contratos.reduce((s, c) => s + (c.resultado || 0), 0);
    if (resumo.ajuste_pos) bruto += comSinal(resumo.ajuste_pos);
    custos = resumo.total_despesas ? -Math.abs(resumo.total_despesas.valor)
      : -["tx_operacional", "tx_registro_bmf", "tx_bmf", "outros_custos", "impostos"].reduce((s, k) => s + (resumo[k]?.valor || 0), 0);
    liquido = comSinal(resumo.liquido_nota) ?? bruto + custos;
  } else {
    bruto = comSinal(resumo.valor_liquido_ops) ?? operacoes.reduce((s, o) => s + (o.dc === "C" ? o.valor : -o.valor), 0);
    custos = resumo.total_custos ? -Math.abs(resumo.total_custos.valor)
      : -["tx_liquidacao", "tx_registro", "emolumentos", "corretagem", "execucao", "custodia", "iss", "impostos"].reduce((s, k) => s + (resumo[k]?.valor || 0), 0);
    liquido = comSinal(resumo.liquido_para) ?? bruto + custos;
  }

  const calculado = contratos.reduce((s, c) => s + (c.resultado || 0), 0);
  const confere = tipo === "futuros" && resumo.ajuste_dt ? Math.abs(calculado - comSinal(resumo.ajuste_dt)) < 0.05 : null;

  const custosDetalhe = ROTULOS
    .filter(([k]) => ["tx_operacional", "tx_registro_bmf", "tx_bmf", "outros_custos", "tx_liquidacao", "tx_registro",
      "emolumentos", "corretagem", "execucao", "custodia", "iss", "irrf_dt", "irrf", "impostos"].includes(k))
    .filter(([k]) => resumo[k] && resumo[k].valor)
    .map(([k, , nome]) => ({ nome, valor: resumo[k].valor }));

  return { arquivo, data, numero, tipo, operacoes, contratos, resumo, custosDetalhe,
    bruto: arred(bruto), custos: arred(custos), liquido: arred(liquido), calculado: arred(calculado), confere };
}

const arred = (x) => (x == null || Number.isNaN(x) ? null : Math.round(x * 100) / 100);
