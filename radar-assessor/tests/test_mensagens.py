"""Testes das sugestões de mensagem."""

import re

import pytest

from radar.mensagens import MODELOS, sugerir_mensagens

# Termos que uma mensagem automática nunca deve conter (risco de compliance).
PROIBIDOS = re.compile(r"garant|rentabilidade|retorno de|lucro|imperd[ií]vel|sem risco", re.I)


@pytest.mark.parametrize("situacao", list(MODELOS))
def test_todos_os_canais_e_variacoes(situacao):
    msgs = sugerir_mensagens("Carla Almeida", "Ana Lima", situacao)
    assert set(msgs) == {"WhatsApp", "E-mail", "Telefone"}
    for variacoes in msgs.values():
        assert len(variacoes) == 5
        assert len({v["rotulo"] for v in variacoes}) == 5  # sem rótulo repetido
        for v in variacoes:
            assert "Carla" in v["texto"] and "Almeida" not in v["texto"]  # só o primeiro nome
            assert "Ana" in v["texto"]
            assert not PROIBIDOS.search(v["texto"])


def test_email_tem_assunto_e_whatsapp_e_curto():
    msgs = sugerir_mensagens("Carla Almeida", "Ana Lima", "esfriando")
    assert all(v["assunto"] for v in msgs["E-mail"])
    assert all(len(v["texto"]) <= 300 for v in msgs["WhatsApp"])


def test_telefone_vira_roteiro():
    roteiro = sugerir_mensagens("Carla Almeida", "Ana Lima", "manter")["Telefone"][0]["texto"]
    assert roteiro.startswith("1. Abertura")
    assert "registre o resultado no CRM" in roteiro


def test_situacao_desconhecida_usa_padrao():
    assert sugerir_mensagens("Carla", "Ana", "inexistente") == sugerir_mensagens("Carla", "Ana", "manter")


# --- Oferta Profit -------------------------------------------------------- #
from radar.mensagens import AVISO_RISCO, OFERTA, sugerir_ofertas  # noqa: E402


def test_toda_oferta_tem_aviso_de_risco_em_todos_os_canais():
    ofertas = sugerir_ofertas("Carla Almeida", "Ana Lima")
    for canal, variacoes in ofertas.items():
        assert len(variacoes) >= 5
        for v in variacoes:
            assert AVISO_RISCO in v["texto"], f"oferta sem aviso de risco no {canal}"
            assert not PROIBIDOS.search(v["texto"])


def test_oferta_usa_os_dados_da_campanha():
    texto = " ".join(v["texto"] for v in sugerir_ofertas("Carla", "Ana")["E-mail"])
    assert OFERTA["plataforma"] in texto and OFERTA["automacao"] in texto
    assert f"{OFERTA['contratos_minimos']} minicontratos" in texto
    assert "R$" not in texto   # "1.000" é o nome do plano, não um preço


def test_roteiro_de_oferta_tem_aviso_antes_do_fechamento():
    roteiro = sugerir_ofertas("Carla", "Ana")["Telefone"][0]["texto"].splitlines()
    assert roteiro[3].startswith("4. Aviso obrigatório")
    assert roteiro[4].startswith("5. Fechamento")


# --- Isenção e leads ------------------------------------------------------ #
from radar.mensagens import sugerir_isencao, sugerir_lead  # noqa: E402


def test_mensagem_de_isencao_mostra_quanto_falta():
    msgs = sugerir_isencao("Carla Almeida", "Ana Lima", "abaixo", operados=4, faltam=6)
    texto = msgs["WhatsApp"][0]["texto"]
    assert "4 minicontratos" in texto and "Faltam 6" in texto
    assert "{" not in texto                      # nenhum marcador sobrando
    assert all(not PROIBIDOS.search(v["texto"]) for c in msgs.values() for v in c)


def test_mensagens_de_isencao_que_citam_operar_tem_aviso():
    for status in ("sem_operar", "abaixo"):
        for v in sugerir_isencao("Carla", "Ana", status, 0, 10)["WhatsApp"]:
            if "minicontratos" in v["texto"]:
                assert AVISO_RISCO in v["texto"]


def test_lead_recebe_interesse_e_aviso_quando_cita_profit():
    msgs = sugerir_lead("João Prado", "Ana Lima", "day trade de WIN")
    assert "day trade de WIN" in msgs["E-mail"][0]["texto"]
    for v in msgs["WhatsApp"]:
        if OFERTA["plataforma"] in v["texto"]:
            assert AVISO_RISCO in v["texto"]
        else:
            assert AVISO_RISCO not in v["texto"]


def test_aniversario_so_parabeniza():
    from radar.mensagens import sugerir_aniversario
    msgs = sugerir_aniversario("Carla Almeida", "Ana Lima")
    for canal, variacoes in msgs.items():
        assert len(variacoes) >= 4
        for v in variacoes:
            texto = v["texto"] + v.get("assunto", "")
            assert "Carla" in texto and "{" not in texto
            assert OFERTA["plataforma"] not in texto and "minicontrato" not in texto
            assert AVISO_RISCO not in texto
    assert "não ofereça produto" in msgs["Telefone"][0]["texto"]


def test_empresa_em_todas_as_mensagens():
    from radar.mensagens import EMPRESA, MODELOS_ISENCAO, sugerir_aniversario
    todas = [sugerir_mensagens("Carla", "Ana", "manter"), sugerir_ofertas("Carla", "Ana"),
             sugerir_lead("Carla", "Ana", "WIN"), sugerir_aniversario("Carla", "Ana"),
             *[sugerir_isencao("Carla", "Ana", st, 1, 9) for st in MODELOS_ISENCAO]]
    for msgs in todas:
        for variacoes in msgs.values():
            assert any(EMPRESA in v["texto"] + v.get("assunto", "") for v in variacoes)


def test_nome_da_empresa_configuravel(tmp_path, monkeypatch):
    import radar.mensagens as m
    monkeypatch.delenv("RADAR_EMPRESA", raising=False)
    monkeypatch.setattr(m, "__file__", str(tmp_path / "radar" / "mensagens.py"))
    assert m._nome_empresa() == m.EMPRESA_PADRAO == "Sua Corretora"      # sem configuração
    (tmp_path / "empresa.txt").write_text("Corretora Exemplo\n", encoding="utf-8")
    assert m._nome_empresa() == "Corretora Exemplo"                       # arquivo local
    monkeypatch.setenv("RADAR_EMPRESA", "Outra Corretora")
    assert m._nome_empresa() == "Outra Corretora"                         # variável tem prioridade
