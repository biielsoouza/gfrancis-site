"""
Gera uma versão estática do painel (um único arquivo .html, sem servidor).
Útil para mandar o protótipo para alguém olhar sem instalar nada.
"""

from datetime import date, datetime
from pathlib import Path

from app import renderizar_painel
from radar.gerador import gerar_contatos, gerar_followups, gerar_leads, gerar_cadastros, gerar_execucoes, gerar_jornadas, gerar_nascimentos, gerar_status_profit
from radar.metricas import montar_painel

if __name__ == "__main__":
    contatos = gerar_contatos(hoje=date.today())
    agora = datetime.now()
    profit = gerar_status_profit(contatos)
    painel = montar_painel(contatos, followups=gerar_followups(contatos, agora=agora),
                           profit=profit, leads=gerar_leads(),
                           nascimentos=gerar_nascimentos(contatos),
                           cadastros=(cad := gerar_cadastros(contatos, profit)),
                           execucoes=gerar_execucoes(cad), jornadas=gerar_jornadas())
    # Demo: o painel desloca os follow-ups para o horário em que for aberto.
    painel["followups_ancorados_em"] = agora.isoformat(timespec="seconds")
    saida = Path("radar_do_assessor.html")
    saida.write_text(renderizar_painel(painel), encoding="utf-8")
    print(f"Painel exportado em {saida.resolve()}")
