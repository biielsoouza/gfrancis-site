"""
Métricas do Radar do Assessor.

Entrada: um DataFrame com as colunas do CRM
    cliente_id, cliente, assessor, data_hora, canal, resultado

Decisão importante — suavização (média bayesiana):
    Um cliente com 2 contatos e 2 respostas teria "100%", o que não quer dizer
    nada. Por isso toda taxa é calculada como

        (respostas + PESO * taxa_de_referência) / (contatos + PESO)

    Com poucos contatos, o número fica perto da referência (a média geral).
    Conforme o histórico cresce, o comportamento real do cliente domina.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from .emails import campanhas_para_painel
from .gerador import CANAIS, FAIXAS, gerar_historico_disparos
from .hubspot import PROPRIEDADES
from .mensagens import (EMPRESA, MODELOS, MODELOS_ISENCAO, OFERTA, REGRAS_ISENCAO, minimo_isencao, sugerir_aniversario, sugerir_isencao,
                        sugerir_lead, sugerir_mensagens, sugerir_ofertas)

PESO_SUAVIZACAO = 5          # "contatos imaginários" na média de referência
DIAS_SEM_CONTATO_ALERTA = 21
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex"]


# --------------------------------------------------------------------------- #
# Preparação
# --------------------------------------------------------------------------- #
def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Valida colunas e acrescenta campos derivados (faixa, dia da semana...)."""
    obrigatorias = {"cliente_id", "cliente", "assessor", "data_hora", "canal", "resultado"}
    faltando = obrigatorias - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas faltando: {sorted(faltando)}")

    df = df.copy()
    df["data_hora"] = pd.to_datetime(df["data_hora"])
    df["sucesso"] = (df["resultado"] == "respondeu").astype(int)
    df["faixa"] = df["data_hora"].dt.hour.map(faixa_da_hora)
    df["dia_semana"] = df["data_hora"].dt.weekday
    return df


def faixa_da_hora(hora: int) -> int:
    for i, (ini, fim) in enumerate(FAIXAS):
        if ini <= hora < fim:
            return i
    return 0 if hora < FAIXAS[0][0] else len(FAIXAS) - 1


def rotulo_faixa(i: int) -> str:
    ini, fim = FAIXAS[i]
    return f"{ini}h–{fim}h"


def taxa_suavizada(sucessos, tentativas, referencia: float, peso: float = PESO_SUAVIZACAO):
    """Média bayesiana. Funciona com números ou com colunas do pandas."""
    return (sucessos + peso * referencia) / (tentativas + peso)


# --------------------------------------------------------------------------- #
# Melhor janela por cliente
# --------------------------------------------------------------------------- #
def mapa_cliente(df: pd.DataFrame, cliente_id: str) -> dict:
    """
    Chance estimada de resposta de um cliente em cada combinação canal x faixa.

    Um cliente tem poucos contatos para preencher 18 células (3 canais x 6 faixas)
    sozinho. Então o canal e o horário são estimados SEPARADAMENTE (cada um com
    bem mais dados) e depois combinados:

        chance(canal, faixa) = taxa_cliente x efeito_do_canal x efeito_da_faixa
    """
    taxa_global = df["sucesso"].mean()
    do_cliente = df[df["cliente_id"] == cliente_id]
    taxa_cliente = float(taxa_suavizada(do_cliente["sucesso"].sum(), len(do_cliente), taxa_global))

    def efeitos(coluna: str, valores) -> dict:
        g = do_cliente.groupby(coluna)["sucesso"].agg(["sum", "count"])
        out = {}
        for v in valores:
            s, n = g.loc[v] if v in g.index else (0, 0)
            # Teto de 1,5x por efeito: dois efeitos fortes multiplicados
            # inflariam a chance além do que o histórico sustenta.
            out[v] = min(float(taxa_suavizada(s, n, taxa_cliente, peso=4)) / taxa_cliente, 1.5)
        return out

    ef_canal = efeitos("canal", CANAIS)
    ef_faixa = efeitos("faixa", range(len(FAIXAS)))
    contagem = do_cliente.groupby(["canal", "faixa"]).size()

    matriz = []
    for canal in CANAIS:
        linha = []
        for f in range(len(FAIXAS)):
            chance = min(taxa_cliente * ef_canal[canal] * ef_faixa[f], 0.85)
            linha.append({"taxa": round(chance, 3),
                          "contatos": int(contagem.get((canal, f), 0))})
        matriz.append(linha)
    return {"canais": CANAIS, "faixas": [rotulo_faixa(i) for i in range(len(FAIXAS))],
            "matriz": matriz}


def melhor_janela(mapa: dict) -> dict:
    melhor = max(
        ((c, f, cel) for c, linha in enumerate(mapa["matriz"]) for f, cel in enumerate(linha)),
        key=lambda x: x[2]["taxa"],
    )
    c, f, cel = melhor
    return {"canal": mapa["canais"][c], "faixa": mapa["faixas"][f], "taxa": cel["taxa"]}


# --------------------------------------------------------------------------- #
# Esfriamento e prioridade
# --------------------------------------------------------------------------- #
def resumo_clientes(df: pd.DataFrame, hoje: date | None = None) -> pd.DataFrame:
    """Uma linha por cliente com ritmo normal, esfriamento e nota de prioridade."""
    hoje_ts = pd.Timestamp(hoje or date.today())
    taxa_global = df["sucesso"].mean()
    linhas = []

    for cid, g in df.groupby("cliente_id"):
        g = g.sort_values("data_hora")
        respostas = g.loc[g["sucesso"] == 1, "data_hora"]

        # Ritmo normal = intervalo médio entre respostas ANTES da última (mínimo 3 dias).
        # Média e não mediana: a mediana subestima o ritmo de quem responde pouco.
        if len(respostas) >= 3:
            ritmo = max(3.0, (respostas.iloc[-1] - respostas.iloc[0]).days / (len(respostas) - 1))
        else:
            ritmo = 30.0  # sem histórico suficiente: assume mensal
        dias_sem_resposta = (hoje_ts - respostas.iloc[-1]).days if len(respostas) else 999
        dias_sem_contato = (hoje_ts - g["data_hora"].iloc[-1]).days

        recentes = g[g["data_hora"] >= hoje_ts - pd.Timedelta(days=30)]
        antigos = g[g["data_hora"] < hoje_ts - pd.Timedelta(days=30)]
        taxa_hist = float(taxa_suavizada(antigos["sucesso"].sum(), len(antigos), taxa_global))
        taxa_rec = float(taxa_suavizada(recentes["sucesso"].sum(), len(recentes), taxa_hist, peso=2))

        mapa = mapa_cliente(df, cid)
        janela = melhor_janela(mapa)

        atraso = dias_sem_resposta / ritmo                       # 1 = normal; 3 = 3x mais tempo
        queda = max(0.0, (taxa_hist - taxa_rec) / taxa_hist) if taxa_hist else 0.0

        # Só conta como "esfriando" com sinal forte: muito além do ritmo E há
        # um bom tempo, ou uma queda grande com contatos recentes suficientes.
        # Quem quase nunca respondeu não está "esfriando" — sempre foi frio.
        sinal_atraso = (atraso >= 3 and dias_sem_resposta >= 21 and len(recentes) >= 1
                        and len(respostas) >= 3)
        sinal_queda = queda >= 0.4 and len(recentes) >= 3
        esfriando = sinal_atraso or sinal_queda

        motivos = []
        if sinal_atraso:
            motivos.append(f"Sem resposta há {dias_sem_resposta} dias (normal: ~{ritmo:.0f})")
        if sinal_queda:
            motivos.append(f"Taxa de resposta caiu {queda:.0%} no último mês")
        responde_pouco = len(respostas) < 3 and len(g) >= 6
        if responde_pouco:
            motivos.append(f"Responde pouco ({len(respostas)} de {len(g)} contatos) — "
                           f"testar {janela['canal']}")
        sem_contato = dias_sem_contato >= DIAS_SEM_CONTATO_ALERTA
        if sem_contato:
            motivos.append(f"Sem contato há {dias_sem_contato} dias")

        # Situação principal: decide qual mensagem sugerir (a mais grave vence).
        situacao = ("esfriando" if esfriando else "responde_pouco" if responde_pouco
                    else "sem_contato" if sem_contato else "manter")

        # Nota 0–100: urgência (atraso, queda, tempo sem contato) + chance de dar certo.
        urgencia = (min(atraso, 5) / 5) * 0.45 + min(queda, 1) * 0.25 \
            + min(dias_sem_contato / 30, 1) * 0.15
        chance = janela["taxa"] * 0.15
        nota = round(100 * min(urgencia + chance, 1))

        linhas.append({
            "cliente_id": cid,
            "cliente": g["cliente"].iloc[0],
            "assessor": g["assessor"].iloc[0],
            "contatos": len(g),
            "taxa_resposta": round(float(taxa_suavizada(g["sucesso"].sum(), len(g), taxa_global)), 3),
            "ritmo_dias": round(ritmo),
            "dias_sem_resposta": dias_sem_resposta,
            "dias_sem_contato": dias_sem_contato,
            "esfriando": bool(esfriando),
            "situacao": situacao,
            "melhor_canal": janela["canal"],
            "melhor_faixa": janela["faixa"],
            "chance_na_janela": janela["taxa"],
            "nota": nota,
            "motivos": motivos or ["Manter relacionamento em dia"],
        })

    return pd.DataFrame(linhas).sort_values("nota", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Visão geral (KPIs e gráficos)
# --------------------------------------------------------------------------- #
def mapa_calor_semana(df: pd.DataFrame) -> dict:
    """Taxa de resposta por dia da semana x faixa de horário."""
    taxa_global = df["sucesso"].mean()
    g = df.groupby(["dia_semana", "faixa"])["sucesso"].agg(["sum", "count"])
    matriz = []
    for d in range(5):
        linha = []
        for f in range(len(FAIXAS)):
            s, n = g.loc[(d, f)] if (d, f) in g.index else (0, 0)
            linha.append(round(float(taxa_suavizada(s, n, taxa_global)), 3))
        matriz.append(linha)
    return {"dias": DIAS_SEMANA, "faixas": [rotulo_faixa(i) for i in range(len(FAIXAS))],
            "matriz": matriz}


def por_canal(df: pd.DataFrame) -> list[dict]:
    g = df.groupby("canal")["sucesso"].agg(["mean", "count"]).reindex(CANAIS).fillna(0)
    return [{"canal": c, "taxa": round(float(r["mean"]), 3), "contatos": int(r["count"])}
            for c, r in g.iterrows()]


def evolucao_semanal(df: pd.DataFrame, semanas: int = 16) -> list[dict]:
    s = (df.set_index("data_hora")["sucesso"].resample("W-SUN").agg(["mean", "count"])
         .tail(semanas))
    return [{"semana": (i - pd.Timedelta(days=6)).strftime("%d/%m"), "taxa": round(float(r["mean"]), 3),
             "contatos": int(r["count"])} for i, r in s.iterrows()]


def insights(df: pd.DataFrame) -> list[str]:
    """Frases curtas em linguagem de assessor, não de estatístico."""
    out = []
    canais = sorted(por_canal(df), key=lambda x: x["taxa"], reverse=True)
    if len(canais) >= 2 and canais[-1]["taxa"] > 0:
        mult = canais[0]["taxa"] / canais[-1]["taxa"]
        out.append(f"{canais[0]['canal']} rende {mult:.1f}x mais respostas que {canais[-1]['canal']}.")

    faixa = df.groupby("faixa")["sucesso"].mean()
    out.append(f"O melhor horário da carteira é {rotulo_faixa(int(faixa.idxmax()))} "
               f"({faixa.max():.0%} de resposta); o pior é {rotulo_faixa(int(faixa.idxmin()))} "
               f"({faixa.min():.0%}).")

    # Quanto a carteira acerta o canal preferido de cada cliente.
    pref = (df[df["sucesso"] == 1].groupby("cliente_id")["canal"]
            .agg(lambda s: s.value_counts().idxmax()))
    ult30 = df[df["data_hora"] >= df["data_hora"].max() - pd.Timedelta(days=30)]
    acerto = (ult30["canal"] == ult30["cliente_id"].map(pref)).mean()
    if not np.isnan(acerto):
        out.append(f"Nos últimos 30 dias, {acerto:.0%} dos contatos usaram o canal que o "
                   f"cliente mais responde.")
    return out


def visao_geral(df: pd.DataFrame, clientes: pd.DataFrame, hoje: date | None = None) -> dict:
    hoje_ts = pd.Timestamp(hoje or date.today())
    ult30 = df[df["data_hora"] >= hoje_ts - pd.Timedelta(days=30)]
    ant30 = df[(df["data_hora"] < hoje_ts - pd.Timedelta(days=30))
               & (df["data_hora"] >= hoje_ts - pd.Timedelta(days=60))]
    faixa = df.groupby("faixa")["sucesso"].mean()
    return {
        "kpis": {
            "taxa_30d": round(float(ult30["sucesso"].mean() if len(ult30) else 0), 3),
            "taxa_30d_anterior": round(float(ant30["sucesso"].mean() if len(ant30) else 0), 3),
            "contatos_30d": int(len(ult30)),
            "clientes": int(len(clientes)),
            "esfriando": int(clientes["esfriando"].sum()),
            "melhor_faixa": rotulo_faixa(int(faixa.idxmax())),
        },
        "calor": mapa_calor_semana(df),
        "canais": por_canal(df),
        "evolucao": evolucao_semanal(df),
        "insights": insights(df),
    }


def historico_cliente(df: pd.DataFrame, cliente_id: str, limite: int = 8) -> list[dict]:
    g = df[df["cliente_id"] == cliente_id].sort_values("data_hora", ascending=False).head(limite)
    return [{"quando": r.data_hora.strftime("%d/%m %H:%M"), "canal": r.canal,
             "resultado": r.resultado} for r in g.itertuples()]


# --------------------------------------------------------------------------- #
# Pacote completo para o painel
# --------------------------------------------------------------------------- #
def classificar_profit(tem_profit: bool, minicontratos: int,
                       minimo: int = OFERTA["contratos_minimos"]) -> str:
    """sem_profit | sem_operar (tem Profit, 0 no mês) | abaixo (1 a minimo-1) | isento."""
    if not tem_profit:
        return "sem_profit"
    if minicontratos <= 0:
        return "sem_operar"
    return "abaixo" if minicontratos < minimo else "isento"


def proximo_aniversario(nascimento: date, hoje: date) -> tuple[date, int, int]:
    """(data do próximo aniversário, dias até lá, idade que vai fazer). 29/02 vira 28/02."""
    def no_ano(ano: int) -> date:
        try:
            return nascimento.replace(year=ano)
        except ValueError:
            return date(ano, 2, 28)
    prox = no_ano(hoje.year)
    if prox < hoje:
        prox = no_ano(hoje.year + 1)
    return prox, (prox - hoje).days, prox.year - nascimento.year


def ultimo_dia_util(ano: int, mes: int) -> date:
    """Último dia útil do mês (sem feriados): é quando a plataforma é cobrada."""
    d = (pd.Timestamp(ano, mes, 1) + pd.offsets.MonthEnd(0)).date()
    while d.weekday() >= 5:
        d -= pd.Timedelta(days=1)
    return d


def dias_uteis_restantes(hoje: date) -> int:
    """Dias úteis do mês a partir de hoje (inclusive). Não considera feriados."""
    fim = (pd.Timestamp(hoje) + pd.offsets.MonthEnd(0)).date()
    return int(np.busday_count(hoje, fim + pd.Timedelta(days=1)))


def compactar_execucoes(execucoes: pd.DataFrame | None) -> dict:
    """
    Milhares de execuções viram listas curtas de números, para o painel continuar leve:
    linhas = [índice do cliente, pregões atrás, segundo do dia, índice do ativo, lado (0=C, 1=V), quantidade].
    """
    if execucoes is None or not len(execucoes):
        return {"clientes": [], "ativos": [], "linhas": []}
    clientes = sorted(execucoes["cliente_id"].unique())
    ic = {c: i for i, c in enumerate(clientes)}
    ativos = ["WIN", "WDO", "BIT"]
    linhas = [[ic[r.cliente_id], int(r.pregoes_atras), int(r.segundo_do_dia), ativos.index(r.ativo),
               0 if r.lado == "C" else 1, int(r.quantidade)] for r in execucoes.itertuples()]
    return {"clientes": clientes, "ativos": ativos, "linhas": linhas}


def pregoes_recentes(hoje: date, n: int = 21) -> list[date]:
    """Os últimos n dias úteis até hoje (o mais recente primeiro)."""
    dias, d = [], hoje
    while len(dias) < n:
        if d.weekday() < 5:
            dias.append(d)
        d -= timedelta(days=1)
    return dias


def metricas_equipe(df: pd.DataFrame, clientes: pd.DataFrame, hoje: date,
                    jornadas: pd.DataFrame | None = None, execucoes: pd.DataFrame | None = None,
                    followups: pd.DataFrame | None = None, leads: pd.DataFrame | None = None,
                    pregoes: int = 21) -> dict:
    """
    Visão do gestor: por assessor, séries diárias (índice 0 = hoje) e números da carteira.
    O painel soma as séries no período escolhido (hoje, 7, 15 ou 30 dias).
    """
    dias = pregoes_recentes(hoje, pregoes)
    indice = {d: i for i, d in enumerate(dias)}
    recentes = df[df["data_hora"].dt.date.isin(indice)].copy()
    recentes["p"] = recentes["data_hora"].dt.date.map(indice)
    dono = dict(zip(clientes["cliente_id"], clientes["assessor"]))
    ex = None
    if execucoes is not None and len(execucoes):
        ex = execucoes[execucoes["pregoes_atras"] < pregoes].assign(assessor=lambda e: e["cliente_id"].map(dono))

    def serie(dados: pd.DataFrame, coluna_p: str, valor=None) -> list[int]:
        cont = (dados.groupby(coluna_p).size() if valor is None else dados.groupby(coluna_p)[valor].sum())
        return [int(cont.get(i, 0)) for i in range(pregoes)]

    saida = []
    for a in sorted(clientes["assessor"].unique()):
        c = clientes[clientes["assessor"] == a]
        r = recentes[recentes["assessor"] == a]
        item = {
            "nome": a,
            "clientes": int(len(c)),
            "patrimonio": round(float(pd.to_numeric(c.get("patrimonio", pd.Series(dtype=float))).fillna(0).sum()), 2),
            "com_profit": int(c["tem_profit"].astype(bool).sum()),
            "isentos": int((c["status_profit"] == "isento").sum()),
            "sem_isencao": int(c["status_profit"].isin(["sem_operar", "abaixo"]).sum()),
            "esfriando": int(c["esfriando"].astype(bool).sum()) if "esfriando" in c else 0,
            "followups": int((followups["assessor"] == a).sum()) if followups is not None and len(followups) else 0,
            "leads": int((leads["assessor"] == a).sum()) if leads is not None and len(leads) else 0,
            "contatos": serie(r, "p"),
            "respostas": serie(r[r["sucesso"] == 1], "p"),
            "contratos": serie(ex[ex["assessor"] == a], "pregoes_atras", "quantidade") if ex is not None else [0] * pregoes,
        }
        for k in ("online", "atendimento", "ausente", "offline"):
            if jornadas is not None and len(jornadas):
                j = jornadas[jornadas["assessor"] == a].set_index("pregoes_atras")[f"{k}_min"]
                item[k] = [int(j.get(i, 0)) for i in range(pregoes)]
            else:
                item[k] = [0] * pregoes
        saida.append(item)
    return {"pregoes": pregoes, "expediente_min": 540, "assessores": saida}


def montar_painel(df_bruto: pd.DataFrame, hoje: date | None = None, tamanho_lista: int = 15,
                  followups: pd.DataFrame | None = None, profit: pd.DataFrame | None = None,
                  leads: pd.DataFrame | None = None,
                  nascimentos: pd.DataFrame | None = None,
                  cadastros: pd.DataFrame | None = None,
                  execucoes: pd.DataFrame | None = None,
                  jornadas: pd.DataFrame | None = None) -> dict:
    """
    Tudo o que o painel precisa, por assessor (e 'Todos').
    `followups`: clientes com status "followup" (cliente_id, followup_em, observacao).
    `profit`:    por cliente, tem_profit e minicontratos_mes.
    `leads`:     leads sem nenhum contato (lead_id, nome, assessor, origem, interesse, entrou_em).
    `nascimentos`: data de nascimento por cliente.
    `cadastros`: ficha cadastral (cpf, codigo, telefone, perfil, operações 30 dias...).
    `execucoes`: ordens executadas nos últimos pregões (ver gerador.gerar_execucoes).
    `jornadas`:  tempo online/em atendimento/ausente/offline de cada assessor por pregão (visão do gestor).
    """
    df = preparar(df_bruto)
    hoje = hoje or df["data_hora"].max().date()
    clientes = resumo_clientes(df, hoje)

    minimo = OFERTA["contratos_minimos"]
    if profit is not None:
        clientes = clientes.merge(profit, on="cliente_id", how="left")
    else:
        clientes = clientes.assign(tem_profit=False, minicontratos_mes=0)
    clientes["tem_profit"] = clientes["tem_profit"].fillna(False).astype(bool)
    clientes["minicontratos_mes"] = clientes["minicontratos_mes"].fillna(0).astype(int)
    clientes["status_profit"] = [classificar_profit(t, n, minimo) for t, n in
                                 zip(clientes["tem_profit"], clientes["minicontratos_mes"])]
    clientes["faltam_isencao"] = np.where(clientes["tem_profit"],
                                          (minimo - clientes["minicontratos_mes"]).clip(lower=0), 0)

    # Aniversários: data do próximo, em quantos dias e a idade que o cliente vai fazer.
    clientes["aniversario"] = None
    clientes["dias_ate_aniversario"] = None
    clientes["idade_no_aniversario"] = None
    if nascimentos is not None and len(nascimentos):
        nasc = dict(zip(nascimentos["cliente_id"], pd.to_datetime(nascimentos["nascimento"]).dt.date))
        for i, cid in clientes["cliente_id"].items():
            if cid in nasc:
                prox, dias, idade = proximo_aniversario(nasc[cid], hoje)
                clientes.at[i, "aniversario"] = prox.isoformat()
                clientes.at[i, "dias_ate_aniversario"] = dias
                clientes.at[i, "idade_no_aniversario"] = idade

    if cadastros is not None and len(cadastros):
        clientes = clientes.merge(cadastros, on="cliente_id", how="left")
        for col in ("mini_30d_win", "mini_30d_wdo", "mini_30d_bit"):
            clientes[col] = clientes[col].fillna(0).astype(int)
        clientes["mini_30d_total"] = clientes["mini_30d_win"] + clientes["mini_30d_wdo"] + clientes["mini_30d_bit"]
        # Cada plataforma tem o seu mínimo de isenção: refaz a situação de cada cliente.
        clientes["minimo_isencao"] = clientes["plataforma"].map(minimo_isencao)
        clientes["status_profit"] = [classificar_profit(t, n, m) for t, n, m in
                                     zip(clientes["tem_profit"], clientes["minicontratos_mes"], clientes["minimo_isencao"])]
        clientes["faltam_isencao"] = np.where(clientes["tem_profit"],
                                              (clientes["minimo_isencao"] - clientes["minicontratos_mes"]).clip(lower=0), 0)
        # Derivativos para perfil conservador: o painel avisa antes de oferecer.
        clientes["perfil_compativel_derivativos"] = clientes["perfil_investidor"].isin(["Arrojado", "Agressivo"])
        clientes = clientes.astype(object).where(clientes.notna(), None)

    lista_leads = []
    if leads is not None and len(leads):
        for l in leads.sort_values("entrou_em").itertuples():
            lista_leads.append({
                "lead_id": l.lead_id, "nome": l.nome, "assessor": l.assessor,
                "email": getattr(l, "email", None),
                "origem": l.origem, "interesse": l.interesse,
                "entrou_em": pd.Timestamp(l.entrou_em).strftime("%d/%m/%Y"),
                "dias_sem_contato": (pd.Timestamp(hoje) - pd.Timestamp(l.entrou_em)).days,
            })

    detalhes = {}
    for c in clientes.itertuples():
        detalhes[c.cliente_id] = {
            "mapa": mapa_cliente(df, c.cliente_id),
            "historico": historico_cliente(df, c.cliente_id),
        }

    lista_followups = []
    if followups is not None and len(followups):
        for f in followups.sort_values("followup_em").itertuples():
            lista_followups.append({
                "id": f"{f.cliente_id}@{pd.Timestamp(f.followup_em):%Y%m%d%H%M}",
                "cliente_id": f.cliente_id, "cliente": f.cliente, "assessor": f.assessor,
                "quando": pd.Timestamp(f.followup_em).isoformat(timespec="minutes"),
                "observacao": f.observacao,
            })

    visoes = {}
    for assessor in ["Todos"] + sorted(df["assessor"].unique()):
        d = df if assessor == "Todos" else df[df["assessor"] == assessor]
        c = clientes if assessor == "Todos" else clientes[clientes["assessor"] == assessor]
        visoes[assessor] = {
            **visao_geral(d, c, hoje),
            "lista_do_dia": c.head(tamanho_lista).to_dict(orient="records"),
        }

    return {
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "referencia": hoje.strftime("%d/%m/%Y"),
        "assessores": list(visoes.keys()),
        "visoes": visoes,
        "detalhes": detalhes,
        "clientes": {r["cliente_id"]: r for r in clientes.to_dict(orient="records")},
        "followups": lista_followups,
        # Modelos com marcadores {cliente}/{assessor}; o navegador preenche os nomes.
        # Enviar uma vez em vez de 30 textos prontos por cliente reduz muito o tamanho.
        "modelos_mensagem": {sit: sugerir_mensagens("{cliente}", "{assessor}", sit) for sit in MODELOS},
        "modelos_oferta": sugerir_ofertas("{cliente}", "{assessor}"),
        "modelos_isencao": {st: sugerir_isencao("{cliente}", "{assessor}", st) for st in MODELOS_ISENCAO},
        "modelos_lead": sugerir_lead("{cliente}", "{assessor}"),
        "modelos_aniversario": sugerir_aniversario("{cliente}", "{assessor}"),
        "execucoes": compactar_execucoes(execucoes),
        "equipe": metricas_equipe(df, clientes, hoje, jornadas, execucoes, followups, leads),
        "campanhas": campanhas_para_painel(),
        "empresa": EMPRESA,
        "historico_disparos": gerar_historico_disparos(),
        "hubspot": {"propriedades": PROPRIEDADES},
        "leads": lista_leads,
        "isencao": {"minimo": minimo, "dias_uteis_restantes": dias_uteis_restantes(hoje),
                    "regras": REGRAS_ISENCAO,
                    "data_cobranca": ultimo_dia_util(hoje.year, hoje.month).isoformat(),
                    "plataforma": OFERTA["plataforma"], "automacao": OFERTA["automacao"]},
    }
