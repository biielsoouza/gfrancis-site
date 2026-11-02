"""Testes das campanhas de e-mail e da integração com o HubSpot."""

import re
from datetime import date

import pytest

from radar.emails import CAMPANHAS, TOKENS_HUBSPOT, html_hubspot, para_hubspot
from radar.hubspot import TAMANHO_LOTE, campanhas_do_cliente, enviar_lotes, montar_lotes, payload_contato
from radar.mensagens import AVISO_RISCO, OFERTA, REGRAS_ISENCAO, minimo_isencao

PROIBIDOS = re.compile(r"garant|rentabilidade|retorno de|lucro|imperd[ií]vel|sem risco", re.I)


def _textos(c):
    return [c["assunto"], c["preheader"]] + [b.get("texto", "") for b in c["blocos"]] + \
        [i for b in c["blocos"] for i in b.get("itens", [])]


@pytest.mark.parametrize("campanha", CAMPANHAS, ids=lambda c: c["id"])
def test_campanha_completa_e_sem_promessa(campanha):
    for t in _textos(campanha):
        assert not PROIBIDOS.search(t)
        for marcador in re.findall(r"\{(\w+)\}", t):
            assert marcador in TOKENS_HUBSPOT, f"marcador sem token do HubSpot: {marcador}"
    html = html_hubspot(campanha)
    assert "{{ unsubscribe_link }}" in html                     # descadastro obrigatório
    assert (AVISO_RISCO in html) == campanha["risco"]
    assert "{" not in re.sub(r"\{\{ [\w.]+ \}\}", "", html)      # só tokens do HubSpot sobram


def test_aviso_de_cobranca_tem_as_regras():
    c = next(c for c in CAMPANHAS if c["id"] == "cobranca_5du")
    texto = " ".join(_textos(c))
    assert "último dia útil de todos os meses" in texto
    assert "só é feita se o requisito mínimo não for atingido" in texto
    for plataforma, minimo in REGRAS_ISENCAO.items():
        assert f"{plataforma}: {minimo} minicontratos" in texto
    assert c["risco"] and c["publico"] == "cobranca"


def test_aniversario_nao_vende():
    c = next(c for c in CAMPANHAS if c["id"] == "aniversario")
    texto = " ".join(_textos(c))
    assert not c["risco"] and OFERTA["plataforma"] not in texto and "minicontrato" not in texto


def test_tokens_hubspot():
    assert para_hubspot("Olá, {nome}! Faltam {faltam}.") == \
        "Olá, {{ contact.firstname }}! Faltam {{ contact.radar_faltam_isencao }}."


def test_minimo_por_plataforma():
    assert minimo_isencao("Profit Pro") == REGRAS_ISENCAO["Profit Pro"]
    assert minimo_isencao(None) == OFERTA["contratos_minimos"]


def _cliente(**extra):
    base = {"cliente": "Carla Almeida", "email": "carla.almeida10@example.com", "assessor": "Ana Lima",
            "telefone": "(11) 91234-5678", "tem_profit": True, "status_profit": "abaixo", "plataforma": "Profit Pro",
            "minimo_isencao": 10, "minicontratos_mes": 4, "faltam_isencao": 6,
            "perfil_compativel_derivativos": True, "dias_ate_aniversario": 40}
    return {**base, **extra}


def test_publicos_do_cliente():
    assert campanhas_do_cliente(_cliente()) == ["cobranca"]
    assert campanhas_do_cliente(_cliente(perfil_compativel_derivativos=False)) == []   # suitability manda
    assert campanhas_do_cliente(_cliente(status_profit="isento")) == []
    assert campanhas_do_cliente(_cliente(tem_profit=False, status_profit="sem_profit")) == ["oferta"]
    assert "aniversario" in campanhas_do_cliente(_cliente(dias_ate_aniversario=0))


def test_payload_no_formato_do_hubspot():
    p = payload_contato(_cliente(), date(2026, 11, 30))
    assert p["idProperty"] == "email" and p["id"] == "carla.almeida10@example.com"
    props = p["properties"]
    assert props["firstname"] == "Carla" and props["lastname"] == "Almeida"
    assert props["radar_faltam_isencao"] == 6 and props["radar_data_cobranca"] == "2026-11-30"
    assert props["radar_campanhas"] == "cobranca"


def test_lotes_de_no_maximo_100_e_simulacao():
    clientes = [_cliente(email=f"c{i}@example.com") for i in range(230)]
    lotes = montar_lotes(clientes, date(2026, 11, 30))
    assert [len(l["inputs"]) for l in lotes] == [100, 100, 30] and TAMANHO_LOTE == 100
    assert all(r["simulado"] for r in enviar_lotes(lotes))       # sem token: nada sai


def test_emails_ficticios_em_dominios_reservados():
    from app import PAINEL
    emails = [c["email"] for c in PAINEL["clientes"].values()] + [l["email"] for l in PAINEL["leads"]]
    assert all(re.fullmatch(r"[a-z]+\.[a-z]+\d{2}@example\.(com|net|org)", e) for e in emails)


def test_rotas_de_campanhas_e_hubspot():
    from app import app
    cli = app.test_client()
    camps = cli.get("/api/campanhas").get_json()
    assert {c["id"] for c in camps} == {c["id"] for c in CAMPANHAS}
    previa = cli.get("/api/hubspot/previa").get_json()
    assert previa["contatos"] == 200 and previa["lotes"] == 2
