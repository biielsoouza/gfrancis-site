"""
Gerador de dados fictícios no mesmo formato do CRM.

Cada linha é um contato: cliente, assessor, data/hora, canal e resultado.
Nenhum dado real é usado. Os clientes têm "personalidades" escondidas
(canal preferido, horário preferido, quanto respondem) para que as métricas
tenham padrões reais para encontrar — assim dá para conferir se o cálculo
acerta o que foi plantado.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

CANAIS = ["WhatsApp", "Telefone", "E-mail"]

# Faixas de horário usadas em todo o projeto (início inclusivo, fim exclusivo).
FAIXAS = [(8, 10), (10, 12), (12, 14), (14, 16), (16, 18), (18, 20)]

NOMES = [
    "Ana", "Bruno", "Carla", "Diego", "Eduarda", "Felipe", "Gabriela", "Henrique",
    "Isabela", "João", "Karina", "Lucas", "Mariana", "Nicolas", "Olívia", "Pedro",
    "Rafaela", "Samuel", "Tatiana", "Vitor", "Yasmin", "André", "Beatriz", "Caio",
    "Débora", "Enzo", "Fernanda", "Gustavo", "Helena", "Igor", "Júlia", "Leonardo",
]
SOBRENOMES = [
    "Almeida", "Barbosa", "Cardoso", "Duarte", "Esteves", "Ferraz", "Gomes",
    "Holanda", "Lacerda", "Moraes", "Nogueira", "Prado", "Queiroz", "Ramos",
    "Siqueira", "Teixeira", "Vasconcelos", "Xavier",
]
ASSESSORES = [
    "Ana Lima", "Bruno Reis", "Camila Torres", "Daniel Melo", "Elisa Rocha",
    "Fábio Nunes", "Giovana Paz", "Hugo Freitas",
]


@dataclass
class PerfilCliente:
    """Comportamento escondido de um cliente fictício."""
    cliente_id: str
    nome: str
    assessor: str
    canal_preferido: str
    faixa_preferida: int        # índice em FAIXAS
    responsividade: float       # chance base de responder (0 a 1)
    cadencia_dias: int          # de quantos em quantos dias o assessor costuma falar
    esfriando: bool             # passou a responder bem menos no último mês


def _faixa_da_hora(hora: int) -> int:
    for i, (ini, fim) in enumerate(FAIXAS):
        if ini <= hora < fim:
            return i
    return len(FAIXAS) - 1


def gerar_perfis(qtd_clientes: int, rng: random.Random) -> list[PerfilCliente]:
    perfis = []
    for i in range(qtd_clientes):
        perfis.append(PerfilCliente(
            cliente_id=f"C-{i + 1:04d}",
            nome=f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}",
            assessor=rng.choice(ASSESSORES),
            canal_preferido=rng.choices(CANAIS, weights=[6, 3, 1])[0],
            faixa_preferida=rng.choices(range(len(FAIXAS)), weights=[3, 4, 2, 2, 3, 2])[0],
            responsividade=rng.uniform(0.25, 0.8),
            cadencia_dias=rng.choice([5, 7, 7, 10, 14, 14, 21]),
            esfriando=rng.random() < 0.12,
        ))
    return perfis


def _chance_de_resposta(p: PerfilCliente, canal: str, hora: int, dias_atras: int,
                        talento_assessor: float) -> float:
    chance = p.responsividade * talento_assessor
    chance *= 1.35 if canal == p.canal_preferido else 0.55
    distancia = abs(_faixa_da_hora(hora) - p.faixa_preferida)
    chance *= [1.4, 0.85, 0.6, 0.5, 0.45, 0.4][distancia]
    if p.esfriando and dias_atras <= 35:
        chance *= 0.15
    return max(0.02, min(chance, 0.95))


def gerar_contatos(qtd_clientes: int = 200, dias: int = 150,
                   hoje: date | None = None, semente: int = 42) -> pd.DataFrame:
    """Gera o histórico de contatos. Mesma semente = mesmos dados."""
    rng = random.Random(semente)
    hoje = hoje or date.today()
    perfis = gerar_perfis(qtd_clientes, rng)
    talento = {a: rng.uniform(0.8, 1.2) for a in ASSESSORES}

    linhas = []
    for p in perfis:
        dia = hoje - timedelta(days=dias - rng.randint(0, p.cadencia_dias))
        while dia <= hoje:
            if dia.weekday() >= 5:  # fim de semana: o contato vai para segunda-feira
                dia += timedelta(days=7 - dia.weekday())
                continue
            # Assessor tende a usar o canal certo, mas nem sempre acerta.
            canal = p.canal_preferido if rng.random() < 0.5 else rng.choice(CANAIS)
            hora = rng.randint(8, 19)
            momento = datetime(dia.year, dia.month, dia.day, hora, rng.randint(0, 59))
            dias_atras = (hoje - dia).days
            respondeu = rng.random() < _chance_de_resposta(
                p, canal, hora, dias_atras, talento[p.assessor])
            linhas.append({
                "cliente_id": p.cliente_id,
                "cliente": p.nome,
                "assessor": p.assessor,
                "data_hora": momento,
                "canal": canal,
                "resultado": "respondeu" if respondeu else "sem sucesso",
            })
            dia += timedelta(days=max(1, round(rng.gauss(p.cadencia_dias, p.cadencia_dias * 0.3))))

    df = pd.DataFrame(linhas).sort_values("data_hora").reset_index(drop=True)
    return df


OBSERVACOES_FOLLOWUP = [
    "Pediu para retornar sobre a isenção do Profit",
    "Quer entender como funciona a Automação Premium",
    "Interessado em começar a operar WIN",
    "Pediu para ligar depois do almoço",
    "Retornar com simulação de margem para WDO",
    "Cliente pediu para falar no fim do dia",
    "Combinamos de revisar a carteira",
    "Aguardando o cliente confirmar a transferência",
]


def gerar_followups(contatos: pd.DataFrame, agora: datetime | None = None,
                    proporcao: float = 0.08, semente: int = 7) -> pd.DataFrame:
    """
    Clientes com status "followup" no CRM, cada um com data/hora de retorno
    e uma observação. Os horários ficam espalhados em volta de `agora`
    (alguns atrasados, alguns para daqui a pouco, outros mais tarde).
    """
    rng = random.Random(semente)
    agora = (agora or datetime.now()).replace(second=0, microsecond=0)
    clientes = contatos.drop_duplicates("cliente_id")[["cliente_id", "cliente", "assessor"]]
    escolhidos = clientes.sample(frac=proporcao, random_state=semente)

    linhas = []
    for c in escolhidos.itertuples():
        minutos = rng.choice([-180, -90, -40, -10, 0, 2, 5, 15, 30, 60, 120, 240])
        quando = agora + timedelta(minutes=minutos)
        quando = quando.replace(minute=(quando.minute // 5) * 5)
        linhas.append({
            "cliente_id": c.cliente_id, "cliente": c.cliente, "assessor": c.assessor,
            "status": "followup", "followup_em": quando,
            "observacao": rng.choice(OBSERVACOES_FOLLOWUP),
        })
    return pd.DataFrame(linhas).sort_values("followup_em").reset_index(drop=True)


def gerar_status_profit(contatos: pd.DataFrame, hoje: date | None = None,
                        semente: int = 11) -> pd.DataFrame:
    """
    Por cliente: se tem Profit ativo e quantos minicontratos operou no mês.
    Distribuição pensada para ter clientes em todas as situações:
    sem Profit, com Profit sem operar, abaixo da isenção e isentos.
    """
    rng = random.Random(semente)
    hoje = hoje or date.today()
    linhas = []
    for c in contatos.drop_duplicates("cliente_id").itertuples():
        tem_profit = rng.random() < 0.55
        if not tem_profit:
            contratos = 0
        else:
            sorte = rng.random()
            if sorte < 0.25:
                contratos = 0
            elif sorte < 0.50:
                contratos = rng.randint(1, 9)
            else:
                contratos = rng.choice([10, 12, 15, 20, 30, 45, 80, 150])
        linhas.append({"cliente_id": c.cliente_id, "tem_profit": tem_profit,
                       "minicontratos_mes": contratos})
    return pd.DataFrame(linhas)


def gerar_nascimentos(contatos: pd.DataFrame, hoje: date | None = None,
                      semente: int = 31) -> pd.DataFrame:
    """
    Data de nascimento de cada cliente. Garante alguns aniversariantes hoje e
    nos próximos dias, para a demonstração sempre ter o que mostrar.
    """
    rng = random.Random(semente)
    hoje = hoje or date.today()
    linhas = []
    for i, c in enumerate(contatos.drop_duplicates("cliente_id").itertuples()):
        idade = rng.randint(24, 72)
        if i % 50 == 0:                       # alguns fazem aniversário hoje
            dia = hoje
        elif i % 25 == 3:                     # alguns nos próximos 7 dias
            dia = hoje + timedelta(days=rng.randint(1, 7))
        else:
            dia = hoje + timedelta(days=rng.randint(8, 365))
        try:
            nascimento = dia.replace(year=dia.year - idade)
        except ValueError:                    # 29/02 em ano não bissexto
            nascimento = (dia - timedelta(days=1)).replace(year=dia.year - idade)
        linhas.append({"cliente_id": c.cliente_id, "nascimento": nascimento})
    return pd.DataFrame(linhas)


PERFIS_INVESTIDOR = ["Conservador", "Moderado", "Arrojado", "Agressivo"]
DDDS = ["11", "11", "11", "21", "31", "41", "47", "51", "61", "71", "81", "85"]


def _cpf_ficticio(rng: random.Random) -> str:
    """
    CPF no formato 000.000.000-00 com dígitos verificadores ERRADOS de propósito:
    parece real na tela, mas nunca coincide com o CPF válido de alguém.
    """
    base = [rng.randint(0, 9) for _ in range(9)]
    d1 = (sum(n * p for n, p in zip(base, range(10, 1, -1))) * 10) % 11 % 10
    d2 = (sum(n * p for n, p in zip(base + [d1], range(11, 1, -1))) * 10) % 11 % 10
    d2_errado = (d2 + rng.randint(1, 9)) % 10
    n = "".join(map(str, base)) + f"{d1}{d2_errado}"
    return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"


def cpf_valido(cpf: str) -> bool:
    """Confere os dígitos verificadores (usado nos testes)."""
    n = [int(c) for c in cpf if c.isdigit()]
    if len(n) != 11:
        return False
    d1 = (sum(a * b for a, b in zip(n[:9], range(10, 1, -1))) * 10) % 11 % 10
    d2 = (sum(a * b for a, b in zip(n[:10], range(11, 1, -1))) * 10) % 11 % 10
    return n[9] == d1 and n[10] == d2


DOMINIOS_FICTICIOS = ["example.com", "example.net", "example.org"]   # reservados: nunca são de ninguém


def email_ficticio(nome: str, rng: random.Random) -> str:
    """nome.sobrenome + número @ domínio reservado para exemplos (RFC 2606)."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    partes = sem_acento.split()
    return f"{partes[0]}.{partes[-1]}{rng.randint(10, 99)}@{rng.choice(DOMINIOS_FICTICIOS)}"


def gerar_cadastros(contatos: pd.DataFrame, profit: pd.DataFrame | None = None,
                    hoje: date | None = None, semente: int = 41) -> pd.DataFrame:
    """
    Ficha cadastral fictícia de cada cliente: CPF, código, telefone, perfil de
    investidor, cliente desde e minicontratos operados nos últimos 30 dias
    (WIN, WDO e BIT). Quem tem Profit e operou no mês sempre tem pelo menos o
    mesmo volume nos últimos 30 dias.
    """
    rng = random.Random(semente)
    hoje = hoje or date.today()
    status = {} if profit is None else profit.set_index("cliente_id").to_dict("index")
    codigos = rng.sample(range(100_000_000, 999_999_999), contatos["cliente_id"].nunique())
    rng_pat = random.Random(semente + 1000)   # gerador separado: não muda os outros dados fictícios
    linhas = []
    for i, c in enumerate(contatos.drop_duplicates("cliente_id").itertuples()):
        st = status.get(c.cliente_id, {"tem_profit": False, "minicontratos_mes": 0})
        if st["tem_profit"]:
            total = st["minicontratos_mes"] + (rng.choice([0, 0, 2, 5, 10, 20]) if st["minicontratos_mes"] else rng.choice([0, 0, 3]))
        else:
            total = 0
        win = round(total * rng.uniform(0.4, 0.75))
        wdo = round((total - win) * rng.uniform(0.5, 1.0))
        bit = total - win - wdo
        linhas.append({
            "cliente_id": c.cliente_id,
            "cpf": _cpf_ficticio(rng),
            "codigo": str(codigos[i]),
            "telefone": f"({rng.choice(DDDS)}) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
            # Quem já tem Profit tende a ter perfil mais arrojado; alguns casos
            # "conservador" ficam de propósito para o painel alertar a incompatibilidade.
            "perfil_investidor": rng.choices(PERFIS_INVESTIDOR,
                                             weights=[1, 2, 5, 4] if st["tem_profit"] else [3, 4, 3, 1])[0],
            "cliente_desde": (hoje - timedelta(days=rng.randint(60, 2600))).isoformat(),
            "email": email_ficticio(c.cliente, rng),
            "plataforma": (rng.choices(["Profit Ultra + Automação Premium 1.000", "Profit Pro"], weights=[3, 2])[0]
                           if st["tem_profit"] else None),
            "mini_30d_win": win, "mini_30d_wdo": wdo, "mini_30d_bit": bit,
            **_patrimonio_ficticio(rng_pat, st["tem_profit"]),
        })
    return pd.DataFrame(linhas)


CLASSES_PATRIMONIO = ["renda_fixa", "renda_variavel", "fundos", "previdencia", "saldo"]


def _patrimonio_ficticio(rng: random.Random, tem_profit: bool) -> dict:
    """
    Patrimônio fictício na corretora e como ele se divide por classe.
    Distribuição log-normal (muitos clientes médios, poucos muito grandes),
    entre R$ 5 mil e R$ 8 milhões. Quem opera Profit tende a ter mais em renda variável.
    """
    total = min(max(rng.lognormvariate(12.2, 1.1), 5_000), 8_000_000)
    pesos = [rng.uniform(3, 6), rng.uniform(2, 5) if tem_profit else rng.uniform(0.3, 2),
             rng.uniform(1, 3), rng.uniform(0, 2.5), rng.uniform(0.2, 0.8)]
    soma = sum(pesos)
    partes = [round(total * w / soma, 2) for w in pesos]
    partes[0] = round(round(total, 2) - sum(partes[1:]), 2)    # fecha a conta no centavo
    return {"patrimonio": round(sum(partes), 2),
            **{f"patrimonio_{k}": v for k, v in zip(CLASSES_PATRIMONIO, partes)}}


EXPEDIENTE_MIN = 9 * 60   # 9h às 18h


def gerar_jornadas(assessores: list[str] | None = None, pregoes: int = 21, semente: int = 71) -> pd.DataFrame:
    """
    Tempo de cada assessor no sistema, por pregão (0 = hoje), dentro do expediente
    de 9 horas (9h às 18h), em minutos:
        online       logado e disponível
        atendimento  logado e em atendimento (status "Em atendimento")
        ausente      logado, mas marcado como ausente
        offline      fora do sistema
    Cada assessor tem um jeito próprio (mais ou menos tempo logado), para o ranking ter diferenças reais.
    """
    rng = random.Random(semente)
    linhas = []
    for a in assessores or ASSESSORES:
        presenca = rng.uniform(0.72, 0.96)       # parte do expediente logado
        foco = rng.uniform(0.35, 0.6)            # parte do tempo logado em atendimento
        pausa = rng.uniform(0.04, 0.12)          # parte do tempo logado como ausente
        for p in range(pregoes):
            logado = round(EXPEDIENTE_MIN * min(max(rng.gauss(presenca, 0.06), 0.3), 1.0))
            atendimento = round(logado * min(max(rng.gauss(foco, 0.08), 0.05), 0.9))
            ausente = round(logado * min(max(rng.gauss(pausa, 0.03), 0.0), 0.3))
            online = max(logado - atendimento - ausente, 0)
            linhas.append({"assessor": a, "pregoes_atras": p, "online_min": online, "atendimento_min": atendimento,
                           "ausente_min": ausente, "offline_min": EXPEDIENTE_MIN - online - atendimento - ausente})
    return pd.DataFrame(linhas)


ATIVOS_MINI = ["WIN", "WDO", "BIT"]


def gerar_execucoes(cadastros: pd.DataFrame, semente: int = 51) -> pd.DataFrame:
    """
    Execuções fictícias dos últimos 30 dias (≈ 21 pregões).

    Para cada cliente, os minicontratos de 30 dias de cada ativo (mini_30d_win,
    mini_30d_wdo, mini_30d_bit) são quebrados em ordens de 1 a 5 contratos e
    espalhados pelos pregões. Assim, somar as execuções de um cliente dá
    exatamente o que aparece na ficha dele.

    `pregoes_atras`: 0 = pregão mais recente, 1 = o anterior, e assim por diante.
    A data de verdade e o código do vencimento (ex.: WINZ26) são calculados no
    painel, a partir do dia em que ele é aberto.
    """
    rng = random.Random(semente)
    linhas = []
    for c in cadastros.itertuples():
        for ativo in ATIVOS_MINI:
            restante = int(getattr(c, f"mini_30d_{ativo.lower()}"))
            while restante > 0:
                qtd = min(restante, rng.choices([1, 2, 3, 5], weights=[5, 3, 2, 1])[0])
                restante -= qtd
                linhas.append({
                    "cliente_id": c.cliente_id,
                    "pregoes_atras": rng.randint(0, 20),
                    "segundo_do_dia": rng.randint(9 * 3600 + 5 * 60, 17 * 3600 + 50 * 60),
                    "ativo": ativo,
                    "lado": rng.choice(["C", "V"]),
                    "quantidade": qtd,
                })
    df = pd.DataFrame(linhas, columns=["cliente_id", "pregoes_atras", "segundo_do_dia", "ativo", "lado", "quantidade"])
    return df.sort_values(["pregoes_atras", "segundo_do_dia"], ascending=[True, False]).reset_index(drop=True)


def gerar_historico_disparos(semente: int = 61) -> list[dict]:
    """
    Histórico fictício de disparos dos últimos ~45 dias, com taxas plausíveis de
    entrega, abertura e clique. `dias_atras` é contado a partir do dia em que o
    painel é aberto.
    """
    rng = random.Random(semente)
    agenda = [("cobranca_5du", [8, 39]), ("cobranca_vespera", [2, 33]), ("oferta_profit", [0, 31]),
              ("aniversario", list(range(0, 15))), ("boas_vindas", list(range(0, 15, 2)))]
    tamanho = {"cobranca_5du": (35, 60), "cobranca_vespera": (20, 40), "oferta_profit": (40, 70),
               "aniversario": (1, 5), "boas_vindas": (2, 6)}
    abertura = {"cobranca_5du": (0.38, 0.52), "cobranca_vespera": (0.42, 0.58), "oferta_profit": (0.22, 0.34),
                "aniversario": (0.55, 0.75), "boas_vindas": (0.45, 0.65)}
    historico = []
    for campanha, dias in agenda:
        for d in dias:
            enviados = rng.randint(*tamanho[campanha])
            entregues = enviados - (1 if enviados > 20 and rng.random() < 0.4 else 0)
            abertos = round(entregues * rng.uniform(*abertura[campanha]))
            cliques = round(abertos * rng.uniform(0.08, 0.22))
            historico.append({"campanha": campanha, "dias_atras": d, "enviados": enviados,
                              "entregues": entregues, "aberturas": abertos, "cliques": cliques})
    return sorted(historico, key=lambda h: h["dias_atras"])


ORIGENS_LEAD = ["Site", "Indicação", "Instagram", "Webinar de day trade", "Profit Summit", "Google"]
INTERESSES_LEAD = ["day trade de WIN", "day trade de WDO", "automação de estratégias",
                   "começar na renda variável", "minicontratos de índice e dólar"]


def gerar_leads(qtd: int = 26, hoje: date | None = None, semente: int = 21) -> pd.DataFrame:
    """Leads distribuídos aos assessores que ainda não receberam nenhum contato."""
    rng = random.Random(semente)
    hoje = hoje or date.today()
    linhas = []
    for i in range(qtd):
        entrou = hoje - timedelta(days=rng.choice([0, 0, 1, 1, 2, 3, 4, 6, 8, 12, 15]))
        linhas.append({
            "lead_id": f"L-{i + 1:04d}",
            "nome": f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}",
            "assessor": rng.choice(ASSESSORES),
            "origem": rng.choice(ORIGENS_LEAD),
            "interesse": rng.choice(INTERESSES_LEAD),
            "entrou_em": entrou,
        })
        linhas[-1]["email"] = email_ficticio(linhas[-1]["nome"], rng)
    return pd.DataFrame(linhas).sort_values("entrou_em").reset_index(drop=True)


def gerar_perfis_publicos(qtd_clientes: int = 200, semente: int = 42) -> list[PerfilCliente]:
    """Devolve os perfis escondidos (usado só nos testes, para conferir as métricas)."""
    return gerar_perfis(qtd_clientes, random.Random(semente))


if __name__ == "__main__":
    contatos = gerar_contatos()
    contatos.to_csv("dados_ficticios.csv", index=False)
    print(f"{len(contatos)} contatos gerados em dados_ficticios.csv")
