"""
Campanhas de e-mail marketing automáticas do Radar.

Cada campanha diz PARA QUEM vai (público), QUANDO vai (agenda) e O QUE diz
(assunto, pré-cabeçalho e blocos do corpo). Os textos usam marcadores como
{nome} e {faltam}:
    - no painel, eles são preenchidos com os dados do cliente (pré-visualização);
    - no HubSpot, viram tokens de personalização, como {{ contact.firstname }}.

Quem envia de fato é o HubSpot (Workflows). O Radar calcula quem está em cada
público e atualiza os contatos lá (ver radar/hubspot.py).

Regras de compliance que valem para todas:
    - nada de promessa de resultado ou rentabilidade;
    - campanhas que falam de operar derivativos levam aviso de risco e só vão
      para clientes com perfil de investidor compatível;
    - todo e-mail tem link de descadastro (exigência do HubSpot e da LGPD).
"""

from __future__ import annotations

from .mensagens import AVISO_RISCO, EMPRESA, OFERTA, REGRAS_ISENCAO

# Marcador do painel -> token de personalização do HubSpot.
TOKENS_HUBSPOT = {
    "nome": "{{ contact.firstname }}",
    "assessor": "{{ contact.radar_assessor }}",
    "plataforma": "{{ contact.radar_plataforma }}",
    "minimo": "{{ contact.radar_minimo_isencao }}",
    "operados": "{{ contact.radar_minicontratos_mes }}",
    "faltam": "{{ contact.radar_faltam_isencao }}",
    "data_cobranca": "{{ contact.radar_data_cobranca }}",
    "interesse": "{{ contact.radar_interesse }}",
}

RODAPE = (f"Você recebe este e-mail por ser cliente da {EMPRESA}. "
          "Para não receber mais comunicações como esta, descadastre-se aqui: {{ unsubscribe_link }}")

_REQUISITOS = [f"{plataforma}: {minimo} minicontratos no mês" for plataforma, minimo in REGRAS_ISENCAO.items()]

CAMPANHAS: list[dict] = [
    {
        "id": "cobranca_5du",
        "nome": "Aviso de cobrança do Profit",
        "descricao": "Avisa quem ainda não atingiu o mínimo de isenção que a plataforma pode ser cobrada.",
        "publico": "cobranca",
        "agenda": "5 dias úteis antes do último dia útil do mês, às 9h",
        "dias_uteis_antes": 5,
        "risco": True,
        "assunto": "{nome}, a cobrança do {plataforma} pode acontecer em {data_cobranca}",
        "preheader": "A cobrança só acontece se o mínimo de {minimo} minicontratos no mês não for atingido.",
        "blocos": [
            {"tipo": "p", "texto": "Olá, {nome},"},
            {"tipo": "p", "texto": "Você está próximo de ter a cobrança do {plataforma} na sua conta, "
                                   "porque ainda não atingiu o requisito mínimo para a isenção neste mês."},
            {"tipo": "destaque", "texto": "Você operou {operados} de {minimo} minicontratos "
                                          "necessários para a isenção deste mês."},
            {"tipo": "p", "texto": "Como funciona: a cobrança acontece no último dia útil de todos os meses "
                                   "(neste mês, {data_cobranca}) e só é feita se o requisito mínimo não for atingido."},
            {"tipo": "lista", "titulo": "Requisitos mínimos para isenção", "itens": _REQUISITOS},
            {"tipo": "p", "texto": "Se tiver qualquer dúvida sobre a sua plataforma ou quiser conversar sobre "
                                   "a sua estratégia, fale com {assessor}, seu assessor."},
            {"tipo": "botao", "texto": "Falar com meu assessor"},
        ],
    },
    {
        "id": "cobranca_vespera",
        "nome": "Último aviso antes da cobrança",
        "descricao": "Segundo aviso, na véspera do último dia útil, para quem continua abaixo do mínimo.",
        "publico": "cobranca",
        "agenda": "1 dia útil antes do último dia útil do mês, às 9h",
        "dias_uteis_antes": 1,
        "risco": True,
        "assunto": "Amanhã é o último dia útil do mês: isenção do {plataforma}",
        "preheader": "Veja quanto falta para a isenção da sua plataforma neste mês.",
        "blocos": [
            {"tipo": "p", "texto": "Olá, {nome},"},
            {"tipo": "p", "texto": "Amanhã, {data_cobranca}, é o último dia útil do mês. É nesse dia que a "
                                   "cobrança do {plataforma} acontece para quem não atingiu o requisito mínimo."},
            {"tipo": "destaque", "texto": "Você operou {operados} de {minimo} minicontratos este mês."},
            {"tipo": "lista", "titulo": "Requisitos mínimos para isenção", "itens": _REQUISITOS},
            {"tipo": "p", "texto": "Qualquer dúvida, {assessor} está à disposição."},
            {"tipo": "botao", "texto": "Falar com meu assessor"},
        ],
    },
    {
        "id": "oferta_profit",
        "nome": "Profit isento para quem ainda não tem",
        "descricao": "Apresenta a plataforma e a regra de isenção para clientes que ainda não usam o Profit.",
        "publico": "oferta",
        "agenda": "Todo primeiro dia útil do mês, às 10h",
        "dias_uteis_antes": None,
        "risco": True,
        "assunto": "{nome}, conheça o " + OFERTA["produto"],
        "preheader": f"Plataforma isenta a partir de {OFERTA['contratos_minimos']} minicontratos no mês.",
        "blocos": [
            {"tipo": "p", "texto": "Olá, {nome},"},
            {"tipo": "p", "texto": f"O {OFERTA['plataforma']} com a {OFERTA['automacao']} reúne leitura de "
                                   "fluxo, automação de estratégias e ferramentas de estudo em uma única plataforma."},
            {"tipo": "destaque", "texto": f"A plataforma fica isenta para quem opera pelo menos "
                                          f"{OFERTA['contratos_minimos']} minicontratos no mês."},
            {"tipo": "p", "texto": "Se quiser entender se faz sentido para o seu perfil, {assessor} pode "
                                   "te mostrar como funciona."},
            {"tipo": "botao", "texto": "Quero conhecer"},
        ],
    },
    {
        "id": "aniversario",
        "nome": "Feliz aniversário",
        "descricao": "Parabéns no dia do aniversário. Sem oferta de produto.",
        "publico": "aniversario",
        "agenda": "Todos os dias, às 8h, para os aniversariantes do dia",
        "dias_uteis_antes": None,
        "risco": False,
        "assunto": "Feliz aniversário, {nome}!",
        "preheader": "Um abraço de toda a equipe.",
        "blocos": [
            {"tipo": "p", "texto": "Olá, {nome},"},
            {"tipo": "p", "texto": "Hoje o dia é seu! Em nome de toda a equipe, desejamos um feliz "
                                   "aniversário e um novo ano com muita saúde e realizações."},
            {"tipo": "p", "texto": "Um abraço,\n{assessor}"},
        ],
    },
    {
        "id": "boas_vindas",
        "nome": "Boas-vindas a novos leads",
        "descricao": "Primeiro contato com leads que ainda não foram atendidos.",
        "publico": "leads",
        "agenda": "1 hora depois que o lead entra, se ainda não houver contato",
        "dias_uteis_antes": None,
        "risco": False,
        "assunto": "Boas-vindas, {nome}",
        "preheader": "Seu assessor vai te ajudar com os primeiros passos.",
        "blocos": [
            {"tipo": "p", "texto": "Olá, {nome},"},
            {"tipo": "p", "texto": "Recebemos o seu cadastro com interesse em {interesse}. Sou {assessor} e "
                                   "vou acompanhar o seu atendimento."},
            {"tipo": "p", "texto": "Antes de qualquer recomendação, quero entender os seus objetivos e a sua "
                                   "experiência no mercado. Qual o melhor horário para conversarmos?"},
            {"tipo": "botao", "texto": "Agendar uma conversa"},
        ],
    },
]

PUBLICOS = {
    "cobranca": "Clientes com plataforma abaixo do mínimo de isenção no mês e perfil compatível com derivativos",
    "oferta": "Clientes sem Profit, com perfil compatível com derivativos",
    "aniversario": "Clientes que fazem aniversário no dia",
    "leads": "Leads que ainda não receberam nenhum contato",
}


def campanhas_para_painel() -> list[dict]:
    """Campanhas com os marcadores {..} (o painel preenche) e os textos fixos já resolvidos."""
    saida = []
    for c in CAMPANHAS:
        saida.append({**c, "publico_descricao": PUBLICOS[c["publico"]],
                      "aviso_risco": AVISO_RISCO if c["risco"] else None, "rodape": RODAPE,
                      "assunto_hubspot": para_hubspot(c["assunto"]), "preheader_hubspot": para_hubspot(c["preheader"]),
                      "html_hubspot": html_hubspot(c)})
    return saida


def para_hubspot(texto: str) -> str:
    """Troca os marcadores {nome}, {faltam}... pelos tokens de personalização do HubSpot."""
    for chave, token in TOKENS_HUBSPOT.items():
        texto = texto.replace("{" + chave + "}", token)
    return texto


def html_hubspot(campanha: dict) -> str:
    """HTML do corpo do e-mail, já com os tokens do HubSpot, pronto para colar no editor."""
    partes = []
    for b in campanha["blocos"]:
        if b["tipo"] == "p":
            partes.append("<p>" + para_hubspot(b["texto"]).replace("\n", "<br>") + "</p>")
        elif b["tipo"] == "destaque":
            partes.append('<p style="padding:12px 16px;background:#EEF4FF;border-radius:8px;"><strong>'
                          + para_hubspot(b["texto"]) + "</strong></p>")
        elif b["tipo"] == "lista":
            itens = "".join(f"<li>{i}</li>" for i in b["itens"])
            partes.append(f"<p><strong>{b['titulo']}</strong></p><ul>{itens}</ul>")
        elif b["tipo"] == "botao":
            partes.append(f'<p><a href="#" style="background:#0066F0;color:#FFFFFF;padding:12px 20px;'
                          f'border-radius:999px;text-decoration:none;font-weight:700;">{b["texto"]}</a></p>')
    if campanha["risco"]:
        partes.append(f'<p style="font-size:12px;color:#6B7280;"><em>{AVISO_RISCO}</em></p>')
    partes.append(f'<p style="font-size:12px;color:#6B7280;">{RODAPE}</p>')
    return "\n".join(partes)


__all__ = ["CAMPANHAS", "PUBLICOS", "TOKENS_HUBSPOT", "campanhas_para_painel", "html_hubspot", "para_hubspot",
           "OFERTA"]
