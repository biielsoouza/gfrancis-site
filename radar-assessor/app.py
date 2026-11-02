"""
Radar do Assessor — servidor web (Flask).

Rotas:
    /                       painel
    /api/painel             todos os dados do painel em JSON
    /api/followups          clientes com status "followup"
    /api/leads              leads ainda sem contato
    /api/segmentos          contagem por situação no Profit
    /api/aniversarios       aniversariantes de hoje e dos próximos 7 dias
    /api/sem-isencao        plataformas ainda não isentas no mês
    /api/execucoes          execuções dos últimos 30 dias (formato compacto)
    /api/campanhas          campanhas de e-mail com HTML pronto para o HubSpot
    /api/hubspot/previa     prévia do que seria enviado ao HubSpot (simulação)
    /api/clientes/<id>      detalhe de um cliente em JSON

Os dados vêm do gerador fictício. Para plugar no CRM de verdade, basta trocar
a função `carregar_contatos()` por uma consulta que devolva as mesmas colunas.
"""

from __future__ import annotations

import json
import webbrowser
from datetime import date, datetime
from pathlib import Path
from threading import Timer

from flask import Flask, Response, abort, jsonify

from radar.gerador import gerar_contatos, gerar_followups, gerar_leads, gerar_cadastros, gerar_execucoes, gerar_nascimentos, gerar_status_profit
from radar.mensagens import sugerir_isencao, sugerir_mensagens, sugerir_ofertas
from radar.metricas import montar_painel

PASTA = Path(__file__).parent
app = Flask(__name__)


def carregar_contatos():
    """Ponto único de entrada dos dados. Hoje: fictícios. Amanhã: o CRM."""
    return gerar_contatos(hoje=date.today())


def carregar_followups(contatos):
    """Clientes com status "followup" no CRM. Hoje: fictícios."""
    return gerar_followups(contatos, agora=datetime.now())


def carregar_profit(contatos):
    """Por cliente: tem Profit? e minicontratos operados no mês. Hoje: fictícios."""
    return gerar_status_profit(contatos, hoje=date.today())


def carregar_nascimentos(contatos):
    """Data de nascimento por cliente. Hoje: fictícias."""
    return gerar_nascimentos(contatos, hoje=date.today())


def carregar_leads():
    """Leads distribuídos aos assessores, ainda sem contato. Hoje: fictícios."""
    return gerar_leads(hoje=date.today())


def renderizar_painel(painel: dict) -> str:
    """Injeta os dados no HTML. Usado pelo servidor e pela exportação estática."""
    modelo = (PASTA / "templates" / "painel.html").read_text(encoding="utf-8")
    dados = json.dumps(painel, ensure_ascii=False, default=str).replace("</", "<\\/")
    return modelo.replace("__DADOS__", dados)


def carregar_cadastros(contatos, profit):
    """Ficha cadastral por cliente (CPF, código, telefone, perfil...). Hoje: fictícios."""
    return gerar_cadastros(contatos, profit, hoje=date.today())


def carregar_execucoes(cadastros):
    """Ordens executadas nos últimos 30 dias. Hoje: fictícias, coerentes com a ficha de cada cliente."""
    return gerar_execucoes(cadastros)


_CONTATOS = carregar_contatos()
_PROFIT = carregar_profit(_CONTATOS)
_CADASTROS = carregar_cadastros(_CONTATOS, _PROFIT)
PAINEL = montar_painel(_CONTATOS, followups=carregar_followups(_CONTATOS),
                       profit=_PROFIT, leads=carregar_leads(),
                       nascimentos=carregar_nascimentos(_CONTATOS),
                       cadastros=_CADASTROS, execucoes=carregar_execucoes(_CADASTROS))


@app.get("/")
def painel():
    return Response(renderizar_painel(PAINEL), mimetype="text/html")


@app.get("/api/painel")
def api_painel():
    return jsonify(PAINEL)


@app.get("/api/followups")
def api_followups():
    return jsonify(PAINEL["followups"])


@app.get("/api/leads")
def api_leads():
    return jsonify(PAINEL["leads"])


@app.get("/api/aniversarios")
def api_aniversarios():
    """Clientes que fazem aniversário hoje e nos próximos 7 dias."""
    lista = [c for c in PAINEL["clientes"].values()
             if c["dias_ate_aniversario"] is not None and c["dias_ate_aniversario"] <= 7]
    return jsonify(sorted(lista, key=lambda c: c["dias_ate_aniversario"]))


@app.get("/api/sem-isencao")
def api_sem_isencao():
    """Clientes com plataforma ainda não isenta no mês (sem operar ou abaixo do mínimo)."""
    lista = [c for c in PAINEL["clientes"].values() if c["status_profit"] in ("sem_operar", "abaixo")]
    return jsonify(sorted(lista, key=lambda c: c["faltam_isencao"]))


@app.get("/api/execucoes")
def api_execucoes():
    """Execuções dos últimos 30 dias, no formato compacto usado pelo painel."""
    return jsonify(PAINEL["execucoes"])


@app.get("/api/campanhas")
def api_campanhas():
    """Campanhas de e-mail, com o HTML pronto para o HubSpot (tokens de personalização)."""
    from radar.emails import CAMPANHAS, html_hubspot, para_hubspot
    return jsonify([{"id": c["id"], "nome": c["nome"], "agenda": c["agenda"],
                     "assunto": para_hubspot(c["assunto"]), "preheader": para_hubspot(c["preheader"]),
                     "html": html_hubspot(c)} for c in CAMPANHAS])


@app.get("/api/hubspot/previa")
def api_hubspot_previa():
    """O que seria enviado ao HubSpot (simulação: nada sai daqui)."""
    from radar.hubspot import montar_lotes
    from radar.metricas import ultimo_dia_util
    hoje = date.today()
    lotes = montar_lotes(list(PAINEL["clientes"].values()), ultimo_dia_util(hoje.year, hoje.month))
    return jsonify({"lotes": len(lotes), "contatos": sum(len(l["inputs"]) for l in lotes),
                    "exemplo": lotes[0]["inputs"][:3] if lotes else []})


@app.get("/api/segmentos")
def api_segmentos():
    """Contagem de clientes por situação no Profit (sem_profit, sem_operar, abaixo, isento)."""
    contagem: dict[str, int] = {}
    for c in PAINEL["clientes"].values():
        contagem[c["status_profit"]] = contagem.get(c["status_profit"], 0) + 1
    return jsonify({**contagem, "leads_sem_contato": len(PAINEL["leads"])})


@app.get("/api/clientes/<cliente_id>")
def api_cliente(cliente_id: str):
    detalhe = PAINEL["detalhes"].get(cliente_id)
    if detalhe is None:
        abort(404, description="Cliente não encontrado")
    resumo = PAINEL["clientes"][cliente_id]
    return jsonify({
        "cliente_id": cliente_id, "resumo": resumo, **detalhe,
        "mensagens": sugerir_mensagens(resumo["cliente"], resumo["assessor"], resumo["situacao"]),
        "ofertas": sugerir_ofertas(resumo["cliente"], resumo["assessor"]),
        "isencao": (sugerir_isencao(resumo["cliente"], resumo["assessor"], resumo["status_profit"],
                                    resumo["minicontratos_mes"], resumo["faltam_isencao"])
                    if resumo["status_profit"] in ("sem_operar", "abaixo") else None),
    })


if __name__ == "__main__":
    Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(port=5000, debug=False)
