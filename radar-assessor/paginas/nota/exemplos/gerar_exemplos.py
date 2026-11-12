"""Gera notas de corretagem FICTÍCIAS no layout padrão (BM&F e Bovespa) para testar o leitor."""
import sys
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

saida = sys.argv[1] if len(sys.argv) > 1 else "."
W, H = A4


def cab(c, titulo, nr, data):
    c.setFont("Helvetica-Bold", 13); c.drawString(30, H - 40, "NOTA DE CORRETAGEM")
    c.setFont("Helvetica", 8)
    c.drawString(30, H - 58, f"Nr. nota {nr}     Folha 1     Data pregão {data}")
    c.drawString(30, H - 70, "CORRETORA EXEMPLO S.A. (dados fictícios)")
    c.drawString(30, H - 82, "Cliente 000123 - CLIENTE DE DEMONSTRACAO     C.P.F./C.N.P.J ***.***.***-**")
    c.setFont("Helvetica-Bold", 9); c.drawString(30, H - 104, titulo)


def linha(c, y, cols, xs, bold=False):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", 8)
    for t, x in zip(cols, xs):
        c.drawString(x, y, t)


def bmf(path):
    c = canvas.Canvas(path, pagesize=A4)
    cab(c, "Negócios realizados - BM&F", "48213", "10/11/2026")
    xs = [30, 55, 110, 175, 240, 300, 375, 465, 490]
    y = H - 124
    linha(c, y, ["C/V", "Mercadoria", "Vencimento", "Quantidade", "Preço/Ajuste", "Tipo Negócio",
                 "Vlr de Operação/Ajuste", "D/C", "Taxa Operacional"], xs, True)
    ops = [
        ["C", "WIN Z26", "16/12/2026", "2", "128.450,0000", "DAY TRADE", "0,00", "D", "0,00"],
        ["V", "WIN Z26", "16/12/2026", "2", "128.780,0000", "DAY TRADE", "132,00", "C", "0,00"],
        ["V", "WIN Z26", "16/12/2026", "1", "128.900,0000", "DAY TRADE", "0,00", "C", "0,00"],
        ["C", "WIN Z26", "16/12/2026", "1", "128.610,0000", "DAY TRADE", "58,00", "C", "0,00"],
        ["C", "WDO Z26", "01/12/2026", "1", "5.432,5000", "DAY TRADE", "0,00", "D", "0,00"],
        ["V", "WDO Z26", "01/12/2026", "1", "5.428,0000", "DAY TRADE", "45,00", "D", "0,00"],
    ]
    for o in ops:
        y -= 14; linha(c, y, o, xs)
    y -= 34
    c.setFont("Helvetica-Bold", 9); c.drawString(30, y, "Resumo dos Negócios"); y -= 16
    pares = [("Venda disponível", "0,00"), ("Compra disponível", "0,00"), ("Venda Opções", "0,00"),
             ("Compra Opções", "0,00"), ("Valor dos negócios", "0,00"),
             ("IRRF", "0,00"), ("IRRF Day Trade (Projeção)", "1,45"), ("Taxa operacional", "0,00"),
             ("Taxa registro BM&F", "1,92"), ("Taxas BM&F (emol+f.gar)", "3,30"),
             ("Outros Custos", "0,00"), ("Impostos", "0,00"), ("Ajuste de posição", "0,00"),
             ("Ajuste day trade", "145,00 C"), ("Total das despesas", "5,22 D"),
             ("Total Conta Normal", "139,78 C"), ("Total líquido #", "139,78 C"),
             ("Total líquido da nota", "139,78 C")]
    for i, (k, v) in enumerate(pares):
        col = i % 3; x = 30 + col * 185
        c.setFont("Helvetica", 8); c.drawString(x, y, k); c.drawRightString(x + 170, y, v)
        if col == 2: y -= 13
    c.save()


def bovespa(path):
    c = canvas.Canvas(path, pagesize=A4)
    cab(c, "Negócios realizados", "77105", "10/11/2026")
    xs = [30, 85, 100, 165, 260, 290, 340, 395, 470]
    y = H - 124
    linha(c, y, ["Q Negociação", "C/V", "Tipo mercado", "Especificação do título", "Obs. (*)",
                 "Quantidade", "Preço / Ajuste", "Valor Operação / Ajuste", "D/C"], xs, True)
    ops = [
        ["1-BOVESPA", "C", "VISTA", "PETROBRAS PN N2", "", "100", "38,50", "3.850,00", "D"],
        ["1-BOVESPA", "C", "VISTA", "VALE ON NM", "", "50", "61,20", "3.060,00", "D"],
        ["1-BOVESPA", "V", "VISTA", "ITAUUNIBANCO PN N1", "", "200", "35,10", "7.020,00", "C"],
        ["1-BOVESPA", "C", "FRACIONARIO", "WEG ON NM", "", "7", "52,30", "366,10", "D"],
    ]
    for o in ops:
        y -= 14; linha(c, y, o, xs)
    y -= 34
    c.setFont("Helvetica-Bold", 9); c.drawString(30, y, "Resumo dos Negócios"); y -= 16
    pares = [("Debêntures", "0,00"), ("Vendas à vista", "7.020,00"), ("Compras à vista", "7.276,10"),
             ("Opções - compras", "0,00"), ("Opções - vendas", "0,00"), ("Operações à termo", "0,00"),
             ("Valor das oper. c/ títulos públ. (v. nom.)", "0,00"), ("Valor das operações", "14.296,10"), ("", ""),
             ("Valor líquido das operações", "256,10 D"), ("Taxa de liquidação", "3,57 D"), ("Taxa de Registro", "0,00 D"),
             ("Total CBLC", "259,67 D"), ("Taxa de termo/opções", "0,00 D"), ("Taxa A.N.A.", "0,00 D"),
             ("Emolumentos", "0,71 D"), ("Total Bovespa / Soma", "0,71 D"), ("Taxa Operacional", "0,00 D"),
             ("Execução", "0,00"), ("Taxa de Custódia", "0,00"), ("Impostos", "0,00"),
             ("I.R.R.F. s/ operações, base R$7.020,00", "0,35"), ("Outros", "0,00 D"),
             ("Total Custos / Despesas", "4,28 D"), ("Líquido para 12/11/2026", "260,38 D")]
    for i, (k, v) in enumerate(pares):
        col = i % 3; x = 30 + col * 185
        c.setFont("Helvetica", 8); c.drawString(x, y, k); c.drawRightString(x + 170, y, v)
        if col == 2: y -= 13
    c.save()


bmf(f"{saida}/nota-exemplo-futuros.pdf")
bovespa(f"{saida}/nota-exemplo-acoes.pdf")
print("ok")
