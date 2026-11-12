// Tela do Leitor de nota: recebe os PDFs, chama o leitor e desenha o resultado. Nada sai do navegador.
import * as pdfjs from "/nota/pdf.min.mjs";
import { linhasDoPdf, lerNota } from "/nota/leitor.mjs";

pdfjs.GlobalWorkerOptions.workerSrc = "/nota/pdf.worker.min.mjs";

const $ = (s) => document.querySelector(s);
const brl = (v) => (v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }));
const sinal = (v) => (v == null ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + brl(Math.abs(v)).replace("-", ""));
const cls = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "");
const numBR = (v, d = 2) => (v == null ? "—" : v.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }));
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const chaveData = (d) => (d ? d.split("/").reverse().join("") : "");
const TIPO = { futuros: "Futuros", acoes: "Ações" };

let notas = [];
let atual = 0;

async function lerArquivo(nome, bytes) {
  const pdf = await pdfjs.getDocument({ data: bytes }).promise;
  const linhas = await linhasDoPdf(pdf);
  return lerNota(linhas, nome);
}

async function receber(lista) {
  const aviso = $("#aviso");
  aviso.textContent = "";
  const falhas = [];
  for (const { nome, bytes } of lista) {
    try {
      const n = await lerArquivo(nome, bytes);
      if (!n.operacoes.length) { falhas.push(`${nome}: não achei operações (a nota é uma imagem ou tem um layout diferente)`); continue; }
      const dup = notas.findIndex((x) => x.numero && x.numero === n.numero && x.data === n.data);
      if (dup >= 0) notas[dup] = n; else notas.push(n);
    } catch (e) {
      falhas.push(`${nome}: não consegui abrir o PDF`);
    }
  }
  notas.sort((a, b) => chaveData(a.data).localeCompare(chaveData(b.data)));
  if (falhas.length) aviso.textContent = falhas.join(" · ");
  if (notas.length) { atual = Math.min(atual, notas.length - 1); desenhar(); }
}

function desenharNotas() {
  const caixa = $("#caixa-notas");
  caixa.hidden = notas.length < 2;
  $("#qtd-notas").textContent = `${notas.length} notas`;
  $("#tab-notas tbody").innerHTML = notas.map((n, i) => `
    <tr class="${i === atual ? "sel" : ""}"><td>${esc(n.data || "—")}</td><td>${esc(n.numero || "—")}</td><td>${TIPO[n.tipo] || "—"}</td>
    <td class="n ${cls(n.bruto)}">${sinal(n.bruto)}</td><td class="n neg">${sinal(n.custos)}</td><td class="n ${cls(n.liquido)}">${sinal(n.liquido)}</td>
    <td><button type="button" data-ver="${i}" aria-label="Ver a nota ${esc(n.numero || i + 1)}">Ver</button></td></tr>`).join("");
  const soma = (k) => notas.reduce((s, n) => s + (n[k] || 0), 0);
  const mesmoTipo = notas.every((n) => n.tipo === notas[0].tipo);
  $("#tab-notas tfoot").innerHTML = `<tr><td colspan="3">Total</td><td class="n ${mesmoTipo ? cls(soma("bruto")) : ""}">${mesmoTipo ? sinal(soma("bruto")) : "—"}</td>
    <td class="n neg">${sinal(soma("custos"))}</td><td class="n ${cls(soma("liquido"))}">${sinal(soma("liquido"))}</td><td></td></tr>`;
}

function desenharDetalhe() {
  const n = notas[atual];
  $("#det-tit").textContent = `Nota ${n.numero || ""}`.trim();
  $("#det-sub").textContent = [n.data && `Pregão de ${n.data}`, TIPO[n.tipo], `${n.operacoes.length} operações`].filter(Boolean).join(" · ");
  $("#k-bruto-rot").textContent = n.tipo === "futuros" ? "Resultado do dia" : "Compras e vendas (saldo)";
  for (const [id, v] of [["#k-bruto", n.bruto], ["#k-custos", n.custos], ["#k-liq", n.liquido]]) {
    const el = $(id); el.textContent = sinal(v); el.className = cls(v);
  }
  const conf = $("#confere");
  conf.hidden = n.confere == null;
  conf.className = "confere" + (n.confere ? "" : " nao");
  conf.textContent = n.confere ? `✓ O resultado calculado (${sinal(n.calculado)}) bate com o ajuste da nota.`
    : `Atenção: o resultado calculado (${sinal(n.calculado)}) não bate com o ajuste da nota. Pode haver posição de outro dia.`;

  $("#bloco-contratos").hidden = !n.contratos.length;
  $("#tab-contratos tbody").innerHTML = n.contratos.map((c) => `<tr><td><b>${esc(c.ativo)}</b></td><td class="n">${c.compras}</td><td class="n">${c.vendas}</td>
    <td class="n">${numBR(c.pmc)}</td><td class="n">${numBR(c.pmv)}</td><td class="n ${cls(c.pontos)}">${c.pontos == null ? "—" : (c.pontos > 0 ? "+" : "") + numBR(c.pontos)}</td>
    <td class="n ${cls(c.resultado)}"><b>${sinal(c.resultado)}</b>${c.aberto ? ` <span class="mut">(${Math.abs(c.aberto)} em aberto)</span>` : ""}</td></tr>`).join("");

  $("#tab-ops tbody").innerHTML = n.operacoes.map((o) => `<tr><td><span class="cv ${o.cv === "C" ? "c" : "v"}" title="${o.cv === "C" ? "Compra" : "Venda"}">${o.cv}</span></td>
    <td>${esc(o.ativo)}</td><td>${esc(o.tipo.toLowerCase())}</td><td class="n">${o.qtd.toLocaleString("pt-BR")}</td>
    <td class="n">${numBR(o.preco, o.base === "WIN" ? 0 : 2)}</td>
    <td class="n ${o.valor ? (o.dc === "C" ? "pos" : "neg") : ""}">${o.valor ? sinal(o.dc === "D" ? -o.valor : o.valor) : "—"}</td></tr>`).join("");

  const irrf = n.custosDetalhe.filter((c) => c.nome.startsWith("IRRF"));
  const itens = n.custosDetalhe.filter((c) => !c.nome.startsWith("IRRF")).map((c) => `<li><span>${esc(c.nome)}</span><span>${brl(c.valor)}</span></li>`).join("");
  $("#lista-custos").innerHTML = (itens || `<li><span class="mut">Nenhum custo encontrado</span></li>`)
    + `<li class="tot"><span>Total de custos</span><span>${brl(Math.abs(n.custos || 0))}</span></li>`
    + irrf.map((c) => `<li class="mut"><span>${esc(c.nome)} · retido, fora do total</span><span>${brl(c.valor)}</span></li>`).join("");
}

function desenhar() {
  $("#resultado").hidden = false;
  desenharNotas();
  desenharDetalhe();
}

// Planilha (CSV separado por ponto e vírgula, abre direto no Excel).
function baixar() {
  const c = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const nb = (v) => (v == null ? "" : String(v).replace(".", ","));
  const linhas = [["Data", "Nota", "Tipo", "C/V", "Ativo", "Tipo do negócio", "Quantidade", "Preço", "Valor", "D/C"].map(c).join(";")];
  for (const n of notas) for (const o of n.operacoes)
    linhas.push([n.data, n.numero, TIPO[n.tipo], o.cv, o.ativo, o.tipo, o.qtd, nb(o.preco), nb(o.valor), o.dc].map(c).join(";"));
  linhas.push("", ["Data", "Nota", "Resultado bruto", "Custos", "Líquido"].map(c).join(";"));
  for (const n of notas) linhas.push([n.data, n.numero, nb(n.bruto), nb(n.custos), nb(n.liquido)].map(c).join(";"));
  const blob = new Blob(["﻿" + linhas.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "notas-de-corretagem.csv" });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// Entrada de arquivos
const entrada = $("#arquivo"), drop = $("#drop");
const deArquivos = async (files) => receber(await Promise.all([...files].filter((f) => /pdf$/i.test(f.type) || /\.pdf$/i.test(f.name))
  .map(async (f) => ({ nome: f.name, bytes: new Uint8Array(await f.arrayBuffer()) }))));
entrada.addEventListener("change", () => { deArquivos(entrada.files); entrada.value = ""; });
for (const ev of ["dragenter", "dragover"]) drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("sobre"); });
for (const ev of ["dragleave", "drop"]) drop.addEventListener(ev, () => drop.classList.remove("sobre"));
drop.addEventListener("drop", (e) => { e.preventDefault(); deArquivos(e.dataTransfer.files); });

document.querySelectorAll("[data-exemplo]").forEach((b) => b.addEventListener("click", async () => {
  b.disabled = true;
  try {
    const r = await fetch(b.dataset.exemplo);
    await receber([{ nome: b.dataset.exemplo.split("/").pop(), bytes: new Uint8Array(await r.arrayBuffer()) }]);
    atual = notas.length - 1; desenhar();
    $("#detalhe").scrollIntoView({ behavior: "smooth", block: "start" });
  } finally { b.disabled = false; }
}));

$("#tab-notas").addEventListener("click", (e) => {
  const b = e.target.closest("[data-ver]"); if (!b) return;
  atual = +b.dataset.ver; desenhar();
});
$("#baixar").addEventListener("click", baixar);
