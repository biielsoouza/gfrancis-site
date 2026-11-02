"""
Integração com o HubSpot.

Como funciona:
    1. O Radar calcula, para cada cliente, os dados que os e-mails usam
       (plataforma, mínimo de isenção, quanto falta, data da cobrança...) e em
       quais campanhas ele entra hoje.
    2. Esses dados vão para os contatos do HubSpot como propriedades
       personalizadas (prefixo "radar_"), em lotes de até 100, pela API:
           POST https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert
       O contato é encontrado pelo e-mail (idProperty = "email"); se não existir, é criado.
    3. No HubSpot, um Workflow por campanha inscreve quem tem a campanha em
       "radar_campanhas" e envia o e-mail marketing, usando as propriedades como
       tokens de personalização. Enviar e-mail por Workflow exige o
       Marketing Hub Professional ou Enterprise.

    4. Envio manual: o assessor seleciona os destinatários no painel e o Radar
       inscreve só esses contatos no Workflow da campanha (inscrever_selecionados).

Nesta demonstração NADA é enviado: `enviar_lotes` só faz a chamada de verdade se
receber um token de aplicativo privado do HubSpot e `simular=False`.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date

URL_UPSERT = "https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert"
URL_INSCRICAO = "https://api.hubapi.com/automation/v2/workflows/{workflow_id}/enrollments/contacts/{email}"
TAMANHO_LOTE = 100   # limite da API do HubSpot por chamada

# Propriedades personalizadas que precisam existir no HubSpot (Configurações > Propriedades > Contato).
PROPRIEDADES = [
    {"name": "radar_assessor", "label": "Radar: assessor", "type": "string", "fieldType": "text"},
    {"name": "radar_plataforma", "label": "Radar: plataforma", "type": "string", "fieldType": "text"},
    {"name": "radar_minimo_isencao", "label": "Radar: mínimo de isenção", "type": "number", "fieldType": "number"},
    {"name": "radar_minicontratos_mes", "label": "Radar: minicontratos no mês", "type": "number", "fieldType": "number"},
    {"name": "radar_faltam_isencao", "label": "Radar: faltam para isenção", "type": "number", "fieldType": "number"},
    {"name": "radar_data_cobranca", "label": "Radar: data da cobrança", "type": "date", "fieldType": "date"},
    {"name": "radar_perfil_compativel", "label": "Radar: perfil compatível com derivativos", "type": "enumeration",
     "fieldType": "booleancheckbox"},
    {"name": "radar_campanhas", "label": "Radar: campanhas de hoje", "type": "enumeration", "fieldType": "checkbox"},
]


def campanhas_do_cliente(c: dict) -> list[str]:
    """Públicos em que o cliente entra hoje (mesma regra da tela de disparos)."""
    compativel = bool(c.get("perfil_compativel_derivativos"))
    publicos = []
    if c.get("tem_profit") and c.get("status_profit") in ("sem_operar", "abaixo") and compativel:
        publicos.append("cobranca")
    if not c.get("tem_profit") and compativel:
        publicos.append("oferta")
    if c.get("dias_ate_aniversario") == 0:
        publicos.append("aniversario")
    return publicos


def payload_contato(c: dict, data_cobranca: date) -> dict:
    """Um contato no formato do batch/upsert do HubSpot."""
    return {
        "idProperty": "email",
        "id": c["email"],
        "properties": {
            "email": c["email"],
            "firstname": str(c["cliente"]).split()[0],
            "lastname": " ".join(str(c["cliente"]).split()[1:]),
            "phone": c.get("telefone") or "",
            "radar_assessor": c["assessor"],
            "radar_plataforma": c.get("plataforma") or "",
            "radar_minimo_isencao": c.get("minimo_isencao") or "",
            "radar_minicontratos_mes": c.get("minicontratos_mes", 0),
            "radar_faltam_isencao": c.get("faltam_isencao", 0),
            "radar_data_cobranca": data_cobranca.isoformat(),
            "radar_perfil_compativel": "true" if c.get("perfil_compativel_derivativos") else "false",
            "radar_campanhas": ";".join(campanhas_do_cliente(c)),   # vários valores: separados por ";"
        },
    }


def montar_lotes(clientes: list[dict], data_cobranca: date, tamanho: int = TAMANHO_LOTE) -> list[dict]:
    """Divide os contatos em lotes de no máximo 100, no formato {"inputs": [...]}."""
    contatos = [payload_contato(c, data_cobranca) for c in clientes if c.get("email")]
    return [{"inputs": contatos[i:i + tamanho]} for i in range(0, len(contatos), tamanho)]


def enviar_lotes(lotes: list[dict], token: str | None = None, simular: bool = True) -> list[dict]:
    """
    Envia os lotes para o HubSpot. Com simular=True (padrão), não chama a API:
    só devolve o que SERIA enviado. O token é de um aplicativo privado do HubSpot
    com o escopo crm.objects.contacts.write.
    """
    resultados = []
    for lote in lotes:
        if simular or not token:
            resultados.append({"simulado": True, "contatos": len(lote["inputs"])})
            continue
        req = urllib.request.Request(URL_UPSERT, data=json.dumps(lote).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            resultados.append({"simulado": False, "status": resp.status, "contatos": len(lote["inputs"])})
    return resultados


def inscrever_selecionados(emails: list[str], workflow_id: int, token: str | None = None,
                           simular: bool = True) -> list[dict]:
    """
    Envio manual: o assessor escolhe os destinatários no painel e o Radar inscreve
    cada um no Workflow da campanha (API de Workflows do HubSpot). O Workflow envia o
    e-mail na hora. Com simular=True (padrão), só devolve o que SERIA feito.
    """
    resultados = []
    for email in emails:
        url = URL_INSCRICAO.format(workflow_id=workflow_id, email=urllib.parse.quote(email))
        if simular or not token:
            resultados.append({"simulado": True, "email": email, "url": url})
            continue
        req = urllib.request.Request(url, method="POST", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            resultados.append({"simulado": False, "email": email, "status": resp.status})
    return resultados
