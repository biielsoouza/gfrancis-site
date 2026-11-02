"""
Testes do Radar do Assessor.

Além de testar o cálculo em si, os testes conferem se as métricas encontram
os padrões que o gerador PLANTOU nos clientes fictícios (canal preferido,
horário preferido, clientes esfriando). É a forma de provar que a lógica
funciona sem usar nenhum dado real.
"""

from datetime import date

import pandas as pd
import pytest

from radar.gerador import FAIXAS, gerar_contatos, gerar_perfis_publicos
from radar.metricas import (montar_painel, preparar, resumo_clientes,
                            rotulo_faixa, taxa_suavizada)

HOJE = date(2026, 10, 30)


@pytest.fixture(scope="module")
def contatos():
    return gerar_contatos(hoje=HOJE)


@pytest.fixture(scope="module")
def clientes(contatos):
    return resumo_clientes(preparar(contatos), HOJE)


@pytest.fixture(scope="module")
def perfis():
    return {p.cliente_id: p for p in gerar_perfis_publicos()}


# --- Cálculo básico ------------------------------------------------------- #
def test_suavizacao_puxa_poucos_contatos_para_a_media():
    # 2 de 2 não pode virar 100%
    assert taxa_suavizada(2, 2, referencia=0.4) == pytest.approx((2 + 5 * 0.4) / 7)
    assert taxa_suavizada(2, 2, referencia=0.4) < 0.6


def test_suavizacao_respeita_historico_grande():
    assert taxa_suavizada(90, 100, referencia=0.4) == pytest.approx(0.876, abs=0.01)


def test_preparar_recusa_colunas_faltando():
    with pytest.raises(ValueError, match="Colunas faltando"):
        preparar(pd.DataFrame({"cliente_id": ["C-1"]}))


def test_gerador_e_reprodutivel():
    a = gerar_contatos(qtd_clientes=20, hoje=HOJE, semente=7)
    b = gerar_contatos(qtd_clientes=20, hoje=HOJE, semente=7)
    pd.testing.assert_frame_equal(a, b)


def test_contatos_so_em_dias_uteis_e_horario_comercial(contatos):
    dt = pd.to_datetime(contatos["data_hora"])
    assert (dt.dt.weekday < 5).all()
    assert dt.dt.hour.between(8, 19).all()


# --- As métricas acham o que foi plantado --------------------------------- #
def test_acerta_canal_preferido(clientes, perfis):
    acerto = (clientes["melhor_canal"] == clientes["cliente_id"].map(
        lambda c: perfis[c].canal_preferido)).mean()
    assert acerto >= 0.65, f"acertou o canal de só {acerto:.0%} dos clientes"


def test_acerta_horario_com_margem_de_uma_faixa(clientes, perfis):
    rotulos = [rotulo_faixa(i) for i in range(len(FAIXAS))]
    distancia = clientes.apply(
        lambda r: abs(rotulos.index(r["melhor_faixa"]) - perfis[r["cliente_id"]].faixa_preferida),
        axis=1)
    assert (distancia <= 1).mean() >= 0.6


def test_esfriando_sobe_na_lista(clientes, perfis):
    """Clientes que de fato esfriaram devem ter nota maior que a média."""
    clientes = clientes.assign(planted=clientes["cliente_id"].map(lambda c: perfis[c].esfriando))
    assert clientes.loc[clientes["planted"], "nota"].mean() > clientes.loc[~clientes["planted"], "nota"].mean()


def test_lista_ordenada_e_com_motivo(clientes):
    assert clientes["nota"].is_monotonic_decreasing
    assert clientes["motivos"].map(len).min() >= 1
    assert clientes["nota"].between(0, 100).all()


# --- Painel e API --------------------------------------------------------- #
def test_painel_tem_todas_as_carteiras(contatos):
    painel = montar_painel(contatos, hoje=HOJE)
    assert painel["assessores"][0] == "Todos"
    for nome, visao in painel["visoes"].items():
        assert visao["lista_do_dia"], f"lista vazia para {nome}"
        assert len(visao["calor"]["matriz"]) == 5


def test_rotas_da_api():
    from app import app
    cliente = app.test_client()
    assert cliente.get("/").status_code == 200
    dados = cliente.get("/api/painel").get_json()
    um_id = dados["visoes"]["Todos"]["lista_do_dia"][0]["cliente_id"]
    assert cliente.get(f"/api/clientes/{um_id}").status_code == 200
    assert cliente.get("/api/clientes/NAO-EXISTE").status_code == 404


# --- Follow-ups ----------------------------------------------------------- #
def test_followups_espalhados_em_volta_de_agora(contatos):
    from datetime import datetime
    from radar.gerador import gerar_followups
    agora = datetime(2026, 10, 30, 15, 0)
    fu = gerar_followups(contatos, agora=agora)
    assert len(fu) > 0 and (fu["status"] == "followup").all()
    assert fu["followup_em"].is_monotonic_increasing
    assert (fu["followup_em"] < agora).any() and (fu["followup_em"] > agora).any()
    assert set(fu["cliente_id"]) <= set(contatos["cliente_id"])


def test_painel_leva_followups_e_modelos(contatos):
    from datetime import datetime
    from radar.gerador import gerar_followups
    painel = montar_painel(contatos, hoje=HOJE, followups=gerar_followups(contatos, agora=datetime(2026, 10, 30, 15)))
    assert painel["followups"] and all(f["cliente_id"] in painel["clientes"] for f in painel["followups"])
    assert "{cliente}" in painel["modelos_oferta"]["WhatsApp"][0]["texto"]
    assert set(painel["modelos_mensagem"]) == {"esfriando", "responde_pouco", "sem_contato", "manter"}


def test_rota_de_followups():
    from app import app
    resposta = app.test_client().get("/api/followups")
    assert resposta.status_code == 200 and isinstance(resposta.get_json(), list)


# --- Carteira Profit e leads ---------------------------------------------- #
from radar.metricas import classificar_profit, dias_uteis_restantes  # noqa: E402


@pytest.mark.parametrize("tem,n,esperado", [
    (False, 0, "sem_profit"), (True, 0, "sem_operar"), (True, 1, "abaixo"),
    (True, 9, "abaixo"), (True, 10, "isento"), (True, 80, "isento"),
])
def test_classificar_profit(tem, n, esperado):
    assert classificar_profit(tem, n, minimo=10) == esperado


def test_dias_uteis_restantes():
    assert dias_uteis_restantes(date(2026, 10, 30)) == 1     # sexta, último dia útil de outubro
    assert dias_uteis_restantes(date(2026, 10, 1)) == 22


def test_painel_com_profit_e_leads(contatos):
    from radar.gerador import gerar_leads, gerar_status_profit
    painel = montar_painel(contatos, hoje=HOJE, profit=gerar_status_profit(contatos, hoje=HOJE),
                           leads=gerar_leads(hoje=HOJE))
    status = {c["status_profit"] for c in painel["clientes"].values()}
    assert status == {"sem_profit", "sem_operar", "abaixo", "isento"}
    for c in painel["clientes"].values():
        if c["status_profit"] == "abaixo":
            assert c["faltam_isencao"] == 10 - c["minicontratos_mes"] > 0
        if not c["tem_profit"]:
            assert c["faltam_isencao"] == 0
    assert painel["leads"] and all(l["dias_sem_contato"] >= 0 for l in painel["leads"])
    assert set(painel["modelos_isencao"]) == {"sem_operar", "abaixo"}


def test_rotas_de_leads_e_segmentos():
    from app import app
    cli = app.test_client()
    assert cli.get("/api/leads").status_code == 200
    seg = cli.get("/api/segmentos").get_json()
    assert seg["leads_sem_contato"] > 0 and seg["abaixo"] > 0


# --- Aniversários --------------------------------------------------------- #
from radar.metricas import proximo_aniversario  # noqa: E402


def test_proximo_aniversario():
    assert proximo_aniversario(date(1990, 10, 30), HOJE) == (date(2026, 10, 30), 0, 36)
    assert proximo_aniversario(date(1990, 11, 2), HOJE) == (date(2026, 11, 2), 3, 36)
    assert proximo_aniversario(date(1990, 10, 29), HOJE) == (date(2027, 10, 29), 364, 37)  # já passou
    assert proximo_aniversario(date(1992, 2, 29), HOJE)[0] == date(2027, 2, 28)            # bissexto


def test_painel_tem_aniversariantes(contatos):
    from radar.gerador import gerar_nascimentos
    painel = montar_painel(contatos, hoje=HOJE, nascimentos=gerar_nascimentos(contatos, hoje=HOJE))
    dias = [c["dias_ate_aniversario"] for c in painel["clientes"].values()]
    assert 0 in dias and any(1 <= d <= 7 for d in dias)
    assert all(0 <= d <= 365 for d in dias)


def test_rota_de_aniversarios():
    from app import app
    lista = app.test_client().get("/api/aniversarios").get_json()
    assert lista and lista[0]["dias_ate_aniversario"] == 0
    assert all(c["dias_ate_aniversario"] <= 7 for c in lista)


# --- Cadastro fictício ----------------------------------------------------- #
def test_cadastros_ficticios(contatos):
    import re
    from radar.gerador import cpf_valido, gerar_cadastros, gerar_status_profit
    profit = gerar_status_profit(contatos, hoje=HOJE)
    cad = gerar_cadastros(contatos, profit, hoje=HOJE).merge(profit, on="cliente_id")
    assert cad["cpf"].str.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}").all()
    assert not cad["cpf"].map(cpf_valido).any()          # nunca é o CPF válido de alguém
    assert cad["codigo"].str.fullmatch(r"\d{9}").all() and cad["codigo"].is_unique
    assert cad["telefone"].str.fullmatch(r"\(\d{2}\) 9\d{4}-\d{4}").all()
    total = cad["mini_30d_win"] + cad["mini_30d_wdo"] + cad["mini_30d_bit"]
    assert (total[cad["tem_profit"]] >= cad.loc[cad["tem_profit"], "minicontratos_mes"]).all()
    assert (total[~cad["tem_profit"]] == 0).all() and cad.loc[~cad["tem_profit"], "plataforma"].isna().all()
    assert re.match(r"\d{4}-\d{2}-\d{2}", cad["cliente_desde"].iloc[0])


def test_cpf_valido_reconhece_cpf_correto():
    from radar.gerador import cpf_valido
    assert cpf_valido("529.982.247-25")       # exemplo clássico de CPF válido usado em testes
    assert not cpf_valido("529.982.247-26")


def test_rota_sem_isencao():
    from app import app
    lista = app.test_client().get("/api/sem-isencao").get_json()
    assert lista and all(c["status_profit"] in ("sem_operar", "abaixo") for c in lista)
    assert [c["faltam_isencao"] for c in lista] == sorted(c["faltam_isencao"] for c in lista)


# --- Execuções -------------------------------------------------------------- #
def test_execucoes_batem_com_a_ficha(contatos):
    from radar.gerador import gerar_cadastros, gerar_execucoes, gerar_status_profit
    from radar.metricas import compactar_execucoes
    profit = gerar_status_profit(contatos, hoje=HOJE)
    cad = gerar_cadastros(contatos, profit, hoje=HOJE)
    ex = gerar_execucoes(cad)
    soma = ex.pivot_table(index="cliente_id", columns="ativo", values="quantidade", aggfunc="sum", fill_value=0)
    for c in cad.itertuples():
        for ativo in ("WIN", "WDO", "BIT"):
            esperado = getattr(c, f"mini_30d_{ativo.lower()}")
            obtido = soma.loc[c.cliente_id, ativo] if c.cliente_id in soma.index and ativo in soma.columns else 0
            assert obtido == esperado, (c.cliente_id, ativo)
    assert ex["pregoes_atras"].between(0, 20).all()
    assert ex["segundo_do_dia"].between(9 * 3600, 18 * 3600).all()
    assert set(ex["lado"]) == {"C", "V"} and ex["quantidade"].between(1, 5).all()
    comp = compactar_execucoes(ex)
    assert len(comp["linhas"]) == len(ex) and all(len(l) == 6 for l in comp["linhas"])


def test_rota_execucoes():
    from app import app
    dados = app.test_client().get("/api/execucoes").get_json()
    assert dados["ativos"] == ["WIN", "WDO", "BIT"] and dados["linhas"]


# --- Patrimônio ------------------------------------------------------------- #
def test_patrimonio_ficticio(contatos):
    from radar.gerador import CLASSES_PATRIMONIO, gerar_cadastros, gerar_status_profit
    cad = gerar_cadastros(contatos, gerar_status_profit(contatos, hoje=HOJE), hoje=HOJE)
    assert cad["patrimonio"].between(5_000, 8_000_000).all()
    soma = sum(cad[f"patrimonio_{k}"] for k in CLASSES_PATRIMONIO)
    assert (abs(soma - cad["patrimonio"]) < 0.011).all()                 # as classes fecham o total
    assert all((cad[f"patrimonio_{k}"] >= 0).all() for k in CLASSES_PATRIMONIO)
    assert cad["patrimonio"].median() < cad["patrimonio"].mean()           # poucos clientes muito grandes
    painel = montar_painel(contatos, hoje=HOJE, cadastros=cad)
    assert all(c["patrimonio"] > 0 for c in painel["clientes"].values())


# --- Equipe (visão do gestor) ----------------------------------------------- #
def test_jornadas_fecham_o_expediente():
    from radar.gerador import ASSESSORES, EXPEDIENTE_MIN, gerar_jornadas
    j = gerar_jornadas(pregoes=21)
    assert len(j) == len(ASSESSORES) * 21
    total = j["online_min"] + j["atendimento_min"] + j["ausente_min"] + j["offline_min"]
    assert (total == EXPEDIENTE_MIN).all()
    assert (j[["online_min", "atendimento_min", "ausente_min", "offline_min"]] >= 0).all().all()
    media = j.groupby("assessor")["offline_min"].mean()
    assert media.max() - media.min() > 30          # assessores diferentes de verdade


def test_pregoes_recentes_pula_fim_de_semana():
    from radar.metricas import pregoes_recentes
    dias = pregoes_recentes(date(2026, 11, 2), 3)     # segunda-feira
    assert dias == [date(2026, 11, 2), date(2026, 10, 30), date(2026, 10, 29)]


def test_metricas_da_equipe(contatos):
    from radar.gerador import gerar_cadastros, gerar_execucoes, gerar_jornadas, gerar_status_profit
    profit = gerar_status_profit(contatos, hoje=HOJE)
    cad = gerar_cadastros(contatos, profit, hoje=HOJE)
    ex = gerar_execucoes(cad)
    painel = montar_painel(contatos, hoje=HOJE, profit=profit, cadastros=cad, execucoes=ex, jornadas=gerar_jornadas())
    eq = painel["equipe"]
    assert {a["nome"] for a in eq["assessores"]} == set(contatos["assessor"])
    for a in eq["assessores"]:
        for k in ("contatos", "respostas", "contratos", "online", "atendimento", "ausente", "offline"):
            assert len(a[k]) == eq["pregoes"]
        assert all(r <= c for r, c in zip(a["respostas"], a["contatos"]))
    # Os contratos da equipe somam exatamente as execuções dos clientes.
    assert sum(sum(a["contratos"]) for a in eq["assessores"]) == int(ex["quantidade"].sum())
    assert sum(a["clientes"] for a in eq["assessores"]) == len(painel["clientes"])
    assert sum(sum(a["contatos"]) for a in eq["assessores"]) > 0


def test_rota_equipe():
    from app import app
    dados = app.test_client().get("/api/equipe").get_json()
    assert dados["assessores"] and dados["pregoes"] == 21
