"""
Sugestões de mensagem para o assessor enviar ao cliente.

A mensagem depende de duas coisas que o Radar já calcula:
    - a SITUAÇÃO do cliente (esfriando, responde pouco, sem contato, em dia)
    - o CANAL (WhatsApp = curto; e-mail = assunto + corpo; telefone = roteiro)

Há dois tipos de mensagem:
    - RELACIONAMENTO: reaproximar o cliente, sem falar de produto.
    - OFERTA: apresentar a condição comercial vigente da plataforma.

Decisão: modelos fixos, sem IA gerando texto livre. Assim todo texto que pode
chegar ao cliente é conhecido de antemão, pode ser revisado pelo compliance e
nunca fala de rentabilidade ou promessa de resultado. Toda oferta de
derivativos sai com aviso de risco.
"""

from __future__ import annotations

import os
from pathlib import Path

# Como a empresa aparece em todas as mensagens.
# O padrão é genérico. Para usar o nome da sua empresa no seu computador, crie um
# arquivo "empresa.txt" na pasta do projeto com o nome dentro (ex.: Minha Corretora).
# Esse arquivo fica fora do GitHub (.gitignore), então o nome nunca vai para o site público.
EMPRESA_PADRAO = "Sua Corretora"


def _nome_empresa() -> str:
    if os.environ.get("RADAR_EMPRESA"):
        return os.environ["RADAR_EMPRESA"]
    arquivo = Path(__file__).resolve().parent.parent / "empresa.txt"
    if arquivo.exists():
        nome = arquivo.read_text(encoding="utf-8").strip()
        if nome:
            return nome
    return EMPRESA_PADRAO


EMPRESA = _nome_empresa()

# Oferta vigente. Mudou a campanha? Altere só aqui.
# Fonte dos nomes e recursos: site da Nelogica (Profit Ultra e NeloStore).
OFERTA = {
    "plataforma": "Profit Ultra",              # versão mais completa do ProfitChart
    "automacao": "Automação Premium 1.000",    # plano do Módulo de Automação de Estratégias
    "limite_automacao": "até 1.000 minicontratos",  # o "1.000" do nome é esse limite
    "contratos_minimos": 10,                   # minicontratos no mês para isentar
    "ativos": "minicontratos de índice (WIN) e dólar (WDO)",
}
OFERTA["produto"] = f"{OFERTA['plataforma']} + {OFERTA['automacao']}"

AVISO_RISCO = ("Operações com derivativos envolvem riscos e podem não ser adequadas "
               "ao seu perfil de investidor.")

# Cada situação tem cinco abordagens. "motivo" explica o contato; "pergunta"
# termina com algo fácil de responder (aumenta a chance de resposta).
MODELOS: dict[str, list[dict]] = {
    "esfriando": [
        {"rotulo": "Retomar contato",
         "assunto": "Vamos colocar a conversa em dia?",
         "motivo": "Faz um tempo que não conversamos e queria saber como estão as coisas.",
         "pergunta": "Você teria 10 minutos esta semana para atualizarmos sua carteira?"},
        {"rotulo": "Novidades do mês",
         "assunto": "Um resumo do mês para você",
         "motivo": "Separei alguns pontos do mercado deste mês que podem fazer sentido para os seus objetivos.",
         "pergunta": "Posso te mandar um resumo rápido?"},
        {"rotulo": "Café ou reunião",
         "assunto": "Que tal um café?",
         "motivo": "Gostaria de te ouvir sobre como estão seus planos para os próximos meses.",
         "pergunta": "Prefere um café presencial ou uma chamada rápida por vídeo?"},
        {"rotulo": "Pedido de feedback",
         "assunto": "Queria ouvir sua opinião",
         "motivo": "Quero ter certeza de que nosso atendimento está do jeito que você precisa.",
         "pergunta": "Tem algo que eu possa fazer diferente para te atender melhor?"},
        {"rotulo": "Sem pressão",
         "assunto": "Quando for um bom momento",
         "motivo": "Sei que a rotina é corrida, então sem pressa nenhuma.",
         "pergunta": "Quando fizer sentido, me avisa um bom dia para conversarmos?"},
    ],
    "responde_pouco": [
        {"rotulo": "Testar novo canal",
         "assunto": "Qual o melhor jeito de falar com você?",
         "motivo": "Tentei falar com você por outros canais e achei que por aqui pode ser mais prático.",
         "pergunta": "Qual o melhor horário para conversarmos rapidinho?"},
        {"rotulo": "Pergunta simples",
         "assunto": "Uma pergunta rápida",
         "motivo": "Quero acompanhar sua carteira do jeito que for mais confortável para você.",
         "pergunta": "Você prefere receber as atualizações por mensagem, e-mail ou ligação?"},
        {"rotulo": "Resposta em uma palavra",
         "assunto": "Responda só com sim ou não",
         "motivo": "Sei que o dia a dia é corrido, então vou ser breve.",
         "pergunta": "Posso te mandar uma atualização da sua carteira por aqui? Um sim já basta."},
        {"rotulo": "Escolha o horário",
         "assunto": "Manhã ou tarde?",
         "motivo": "Quero marcar uma conversa rápida no horário que for melhor para você.",
         "pergunta": "Fica melhor de manhã ou à tarde?"},
        {"rotulo": "Confirmar contato",
         "assunto": "Confirmando seus dados de contato",
         "motivo": "Estou atualizando os contatos dos meus clientes para não deixar ninguém sem atendimento.",
         "pergunta": "Este ainda é o melhor jeito de falar com você?"},
    ],
    "sem_contato": [
        {"rotulo": "Revisão da carteira",
         "assunto": "Revisão da sua carteira",
         "motivo": "Já faz algumas semanas desde nossa última conversa.",
         "pergunta": "Quer marcar uma revisão rápida da sua carteira?"},
        {"rotulo": "Mudança de planos",
         "assunto": "Algo mudou nos seus planos?",
         "motivo": "Gosto de checar de tempos em tempos se seus objetivos continuam os mesmos.",
         "pergunta": "Teve alguma mudança desde que conversamos?"},
        {"rotulo": "Agenda da semana",
         "assunto": "Tenho horários livres esta semana",
         "motivo": "Abri alguns horários na agenda para conversar com meus clientes nesta semana.",
         "pergunta": "Quer que eu reserve um para você?"},
        {"rotulo": "Próximos objetivos",
         "assunto": "Seus próximos objetivos",
         "motivo": "Estou ajudando meus clientes a se organizar para os próximos meses.",
         "pergunta": "Tem algum objetivo novo, como uma viagem, compra ou reserva, que eu deva considerar?"},
        {"rotulo": "Check-in rápido",
         "assunto": "Um check-in rápido",
         "motivo": "Passando para fazer um check-in rápido.",
         "pergunta": "Está tudo certo com seus investimentos ou ficou alguma dúvida?"},
    ],
    "manter": [
        {"rotulo": "Estou à disposição",
         "assunto": "Passando para dar um oi",
         "motivo": "Só passando para lembrar que estou à disposição.",
         "pergunta": "Ficou alguma dúvida sobre seus investimentos?"},
        {"rotulo": "Resumo do mês",
         "assunto": "Resumo mensal da sua carteira",
         "motivo": "Estou preparando os resumos do mês dos meus clientes.",
         "pergunta": "Quer receber o seu?"},
        {"rotulo": "Agradecimento",
         "assunto": "Obrigado pela confiança",
         "motivo": "Queria agradecer pela confiança no nosso trabalho.",
         "pergunta": "Se tiver alguém próximo que também queira organizar os investimentos, posso ajudar?"},
        {"rotulo": "Conteúdo útil",
         "assunto": "Um conteúdo que pode te interessar",
         "motivo": "Temos alguns conteúdos educativos sobre planejamento financeiro que costumam ser úteis.",
         "pergunta": "Quer que eu te envie?"},
        {"rotulo": "Próxima revisão",
         "assunto": "Agendando sua próxima revisão",
         "motivo": "Gosto de manter uma revisão periódica da carteira com cada cliente.",
         "pergunta": "Podemos já deixar a próxima marcada?"},
    ],
}


def _modelos_oferta() -> list[dict]:
    """Abordagens da oferta vigente, montadas a partir de OFERTA."""
    o = OFERTA
    pl, au, n = o["plataforma"], o["automacao"], o["contratos_minimos"]
    return [
        {"rotulo": "Plataforma isenta",
         "assunto": f"{pl} com {au} sem custo para você",
         "motivo": (f"Estamos com uma condição especial: o {pl}, a versão mais completa do "
                    f"ProfitChart, junto com a {au}, fica isento para quem operar pelo menos "
                    f"{n} minicontratos no mês."),
         "pergunta": "Quer que eu te explique como funciona?"},
        {"rotulo": "Para quem opera WIN/WDO",
         "assunto": "Opera WIN ou WDO? Veja esta condição",
         "motivo": (f"Se você opera ou tem interesse em {o['ativos']}, a partir de {n} "
                    f"minicontratos no mês você usa o {pl} com a {au} sem pagar pela plataforma."),
         "pergunta": "Posso te mostrar como ativar?"},
        {"rotulo": "Automação de estratégias",
         "assunto": f"Automatize suas estratégias com a {au}",
         "motivo": (f"Com a {au} você automatiza suas estratégias no {pl}, com capacidade para "
                    f"{o['limite_automacao']}, backtest tick a tick e otimizador de parâmetros. "
                    f"Operando {n} minicontratos no mês, fica tudo isento."),
         "pergunta": "Quer ver uma demonstração rápida?"},
        {"rotulo": "Leitura de fluxo",
         "assunto": f"Tape Reading e Motion Tracker no {pl}",
         "motivo": (f"O {pl} traz Tape Reading, Motion Tracker e Replay Multi para acompanhar e "
                    f"estudar o fluxo do mercado. Com {n} minicontratos no mês, você usa sem custo, "
                    f"com a {au} inclusa."),
         "pergunta": "Quer conhecer?"},
        {"rotulo": "Primeiros passos",
         "assunto": "Quer começar a operar minicontratos?",
         "motivo": (f"Se quiser começar a operar {o['ativos']}, posso te acompanhar nos primeiros "
                    f"passos no {pl}: configuração, tamanho de posição e controle de risco. "
                    f"A plataforma fica isenta a partir de {n} minicontratos no mês."),
         "pergunta": "Topa uma conversa de 15 minutos?"},
        {"rotulo": "Lembrete curto",
         "assunto": f"Lembrete: isenção do {pl}",
         "motivo": f"Lembrete rápido: operando {n} minicontratos no mês, o {pl} com a {au} fica isento.",
         "pergunta": "Quer que eu ative para você?"},
    ]


def primeiro_nome(nome: str) -> str:
    return nome.strip().split()[0] if nome.strip() else ""


def _whatsapp(cliente: str, assessor: str, m: dict, aviso: str = "") -> dict:
    texto = (f"Oi, {cliente}! Tudo bem? Aqui é {assessor}, da {EMPRESA}. "
             f"{m['motivo']} {m['pergunta']}")
    if aviso:
        texto += f"\n\n_{aviso}_"   # itálico no WhatsApp
    return {"texto": texto}


def _email(cliente: str, assessor: str, m: dict, aviso: str = "") -> dict:
    texto = (f"Olá, {cliente},\n\n{m['motivo']}\n\n{m['pergunta']}\n\n"
             f"Um abraço,\n{assessor}\n{EMPRESA}")
    if aviso:
        texto += f"\n\n—\n{aviso}"
    return {"assunto": m["assunto"], "texto": texto}


def _telefone(cliente: str, assessor: str, m: dict, aviso: str = "") -> dict:
    passos = [
        f"1. Abertura: \"Oi, {cliente}, aqui é {assessor}, da {EMPRESA}. Tudo bem? É um bom momento?\"",
        f"2. Motivo: \"{m['motivo']}\"",
        f"3. Pergunta: \"{m['pergunta']}\"",
    ]
    if aviso:
        passos.append(f"4. Aviso obrigatório: \"{aviso}\"")
    passos.append(f"{len(passos) + 1}. Fechamento: combine o próximo passo e registre o resultado no CRM.")
    return {"texto": "\n".join(passos)}


FORMATOS = {"WhatsApp": _whatsapp, "E-mail": _email, "Telefone": _telefone}


def _formatar_todos(modelos: list[dict], cliente: str, assessor: str, aviso: str = "",
                    extras: dict | None = None) -> dict:
    """
    Formata cada modelo em cada canal.
    - Modelos com "risco": True recebem o aviso de risco mesmo sem `aviso`.
    - `extras` preenche marcadores como {faltam}; sem ele, o marcador fica no texto
      (o painel preenche no navegador).
    """
    nome_cliente, nome_assessor = primeiro_nome(cliente), primeiro_nome(assessor)

    def preencher(v: dict) -> dict:
        for k, val in (extras or {}).items():
            v = {c: (t.replace("{" + k + "}", str(val)) if isinstance(t, str) else t) for c, t in v.items()}
        return v

    return {
        canal: [preencher({"rotulo": m["rotulo"],
                           **formatar(nome_cliente, nome_assessor, m,
                                      aviso or (AVISO_RISCO if m.get("risco") else ""))})
                for m in modelos]
        for canal, formatar in FORMATOS.items()
    }


def sugerir_ofertas(cliente: str, assessor: str) -> dict:
    """Mensagens da oferta vigente, sempre com aviso de risco. Mesmo formato de sugerir_mensagens."""
    return _formatar_todos(_modelos_oferta(), cliente, assessor, aviso=AVISO_RISCO)


# Clientes que JÁ TÊM Profit e ainda não chegaram ao mínimo do mês.
# Marcadores: {operados}, {faltam}, {minimo}. Tom de lembrete e apoio, nunca de
# pressão para operar só por causa da isenção.
MODELOS_ISENCAO: dict[str, list[dict]] = {
    "sem_operar": [
        {"rotulo": "Lembrete da isenção", "risco": True,
         "assunto": f"Sua isenção do {OFERTA['plataforma']} este mês",
         "motivo": (f"Vi que você ainda não operou minicontratos este mês. A isenção do "
                    f"{OFERTA['produto']} vale para quem opera pelo menos {{minimo}} minicontratos no mês."),
         "pergunta": "Posso te ajudar com algo para os próximos pregões?"},
        {"rotulo": "Ajuda com a plataforma",
         "assunto": f"Precisa de ajuda com o {OFERTA['plataforma']}?",
         "motivo": (f"Se estiver com alguma dificuldade no {OFERTA['plataforma']} ou na "
                    f"{OFERTA['automacao']}, posso te ajudar a configurar."),
         "pergunta": "Quer marcar 15 minutos para vermos juntos?"},
        {"rotulo": "Plano de trade", "risco": True,
         "assunto": "Vamos montar seu plano de trade?",
         "motivo": (f"O {OFERTA['plataforma']} tem uma ferramenta de plano de trade para organizar "
                    f"metas, limites e acompanhar seus resultados."),
         "pergunta": "Quer que eu te mostre como usar?"},
    ],
    "abaixo": [
        {"rotulo": "Quanto falta", "risco": True,
         "assunto": "Faltam {faltam} minicontratos para sua isenção",
         "motivo": (f"Você já operou {{operados}} minicontratos este mês. Faltam {{faltam}} para "
                    f"manter o {OFERTA['plataforma']} e a {OFERTA['automacao']} isentos."),
         "pergunta": "Posso te ajudar com algo?"},
        {"rotulo": "Reta final do mês", "risco": True,
         "assunto": "Reta final do mês",
         "motivo": (f"Estamos chegando ao fim do mês e faltam {{faltam}} minicontratos para a sua "
                    f"isenção do {OFERTA['plataforma']}."),
         "pergunta": "Quer conversar sobre seu plano para os próximos pregões?"},
        {"rotulo": "Automação", "risco": True,
         "assunto": f"Sua estratégia na {OFERTA['automacao']}",
         "motivo": (f"Se fizer sentido para a sua estratégia, a {OFERTA['automacao']} executa suas "
                    f"operações no {OFERTA['plataforma']} seguindo as regras e limites que você definir."),
         "pergunta": "Quer ver como configurar?"},
    ],
}

# Primeiro contato com leads. Marcador: {interesse}.
MODELOS_LEAD: list[dict] = [
    {"rotulo": "Boas-vindas",
     "assunto": f"Boas-vindas à {EMPRESA}",
     "motivo": ("Vi que você se cadastrou com interesse em {interesse}. Sou o assessor responsável "
                "pelo seu atendimento e quero te ajudar a dar os primeiros passos."),
     "pergunta": "Qual o melhor horário para conversarmos?"},
    {"rotulo": "Conhecer seu perfil",
     "assunto": "Vamos conversar sobre seus objetivos?",
     "motivo": "Antes de qualquer recomendação, quero entender seus objetivos e sua experiência no mercado.",
     "pergunta": "Podemos marcar 15 minutos esta semana?"},
    {"rotulo": f"{OFERTA['plataforma']} isento", "risco": True,
     "assunto": f"{OFERTA['produto']} sem custo",
     "motivo": (f"Para quem quer operar {OFERTA['ativos']}, temos o {OFERTA['plataforma']} com a "
                f"{OFERTA['automacao']} isentos a partir de {OFERTA['contratos_minimos']} "
                f"minicontratos no mês."),
     "pergunta": "Quer que eu te explique como funciona?"},
    {"rotulo": "Mensagem curta",
     "assunto": f"Seu cadastro na {EMPRESA}",
     "motivo": "Recebi seu cadastro e fiquei responsável pelo seu atendimento.",
     "pergunta": "Prefere conversar por aqui ou por ligação?"},
]


def sugerir_isencao(cliente: str, assessor: str, status: str,
                    operados: int | None = None, faltam: int | None = None) -> dict:
    """Mensagens para quem tem Profit e está sem operar ('sem_operar') ou abaixo do mínimo ('abaixo')."""
    extras = {"minimo": OFERTA["contratos_minimos"]}
    if operados is not None:
        extras["operados"] = operados
    if faltam is not None:
        extras["faltam"] = faltam
    return _formatar_todos(MODELOS_ISENCAO.get(status, MODELOS_ISENCAO["sem_operar"]),
                           cliente, assessor, extras=extras)


def sugerir_lead(nome: str, assessor: str, interesse: str | None = None) -> dict:
    """Primeiro contato com um lead."""
    return _formatar_todos(MODELOS_LEAD, nome, assessor,
                           extras={"interesse": interesse} if interesse else None)


# Aniversário: só parabéns, sem produto. Mensagem comercial no aniversário
# soa oportunista e queima o relacionamento.
MODELOS_ANIVERSARIO: list[dict] = [
    {"rotulo": "Parabéns",
     "assunto": "Feliz aniversário, {cliente}!",
     "motivo": "Passando para te desejar um feliz aniversário! Muita saúde, paz e conquistas neste novo ano.",
     "pergunta": "Aproveite muito o seu dia!"},
    {"rotulo": "Curta e calorosa",
     "assunto": "Parabéns pelo seu dia",
     "motivo": "Hoje o dia é seu! Parabéns e muitas felicidades.",
     "pergunta": "Um ótimo dia para você!"},
    {"rotulo": "Com agradecimento",
     "assunto": "Feliz aniversário e obrigado pela confiança",
     "motivo": ("Feliz aniversário! Aproveito para agradecer pela confiança no nosso trabalho. "
                "É um prazer acompanhar você."),
     "pergunta": "Que este ano seja de muitas realizações!"},
    {"rotulo": "Mais formal",
     "assunto": "Votos de feliz aniversário",
     "motivo": ("Em nome da equipe, desejo um feliz aniversário e um novo ano repleto de "
                "saúde e realizações."),
     "pergunta": "Conte sempre conosco."},
]


def _telefone_aniversario(cliente: str, assessor: str, m: dict, aviso: str = "") -> dict:
    """No telefone, aniversário não precisa de roteiro comercial: só abertura e parabéns."""
    texto = "\n".join([
        f"1. Abertura: \"Oi, {cliente}, aqui é {assessor}, da {EMPRESA}!\"",
        f"2. Parabéns: \"{m['motivo']} {m['pergunta']}\"",
        "3. Fechamento: não ofereça produto hoje. Registre o contato no CRM.",
    ])
    return {"texto": texto}


def sugerir_aniversario(cliente: str, assessor: str) -> dict:
    """Mensagens de parabéns. Sem oferta e sem aviso de risco (não falam de produto)."""
    out = _formatar_todos(MODELOS_ANIVERSARIO, cliente, assessor)
    nome_c, nome_a = primeiro_nome(cliente), primeiro_nome(assessor)
    out["Telefone"] = [{"rotulo": m["rotulo"], **_telefone_aniversario(nome_c, nome_a, m)}
                       for m in MODELOS_ANIVERSARIO]
    # o assunto do e-mail usa {cliente}: preenche com o primeiro nome
    for v in out["E-mail"]:
        v["assunto"] = v["assunto"].replace("{cliente}", nome_c)
    return out


def sugerir_mensagens(cliente: str, assessor: str, situacao: str) -> dict:
    """
    Devolve {canal: [variação, variação]} para todos os canais.
    Cada variação: {"rotulo", "texto"} e, no e-mail, também "assunto".
    """
    return _formatar_todos(MODELOS.get(situacao, MODELOS["manter"]), cliente, assessor)
