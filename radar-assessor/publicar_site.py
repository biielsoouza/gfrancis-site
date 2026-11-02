"""
Monta a pasta do site gfrancis.com.br.

A Netlify roda este arquivo sozinha a cada envio para o GitHub (veja o
netlify.toml na raiz do repositório), depois de passar nos testes. Para
gerar o site no seu computador, rode: python publicar_site.py

    site/
    ├── index.html          página inicial (portfólio)
    └── radar/index.html    demonstração do Radar do Assessor

A versão pública usa um nome de empresa genérico nas mensagens e só dados
fictícios. Para trocar o nome, altere NOME_PUBLICO abaixo.
"""

import os

NOME_PUBLICO = "Sua Corretora"
os.environ["RADAR_EMPRESA"] = NOME_PUBLICO   # precisa vir antes de importar o radar

import shutil                                # noqa: E402
from datetime import date, datetime          # noqa: E402
from pathlib import Path                     # noqa: E402

from app import renderizar_painel            # noqa: E402
from radar.gerador import (gerar_contatos, gerar_followups, gerar_leads,  # noqa: E402
                           gerar_cadastros, gerar_execucoes, gerar_jornadas, gerar_nascimentos, gerar_status_profit)
from radar.metricas import montar_painel     # noqa: E402

PASTA = Path(__file__).parent
SAIDA = PASTA / "site"


def pagina_completa(corpo: str, titulo: str) -> str:
    """O painel é escrito sem <html>/<head>; num site comum ele precisa do esqueleto completo."""
    return ("<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            f"<meta name=\"description\" content=\"{titulo}: demonstração com dados fictícios.\">\n"
            "</head>\n<body>\n" + corpo + "\n</body>\n</html>\n")


if __name__ == "__main__":
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    (SAIDA / "radar").mkdir(parents=True)

    contatos = gerar_contatos(hoje=date.today())
    agora = datetime.now()
    profit = gerar_status_profit(contatos)
    painel = montar_painel(contatos, followups=gerar_followups(contatos, agora=agora),
                           profit=profit, leads=gerar_leads(),
                           nascimentos=gerar_nascimentos(contatos),
                           cadastros=(cad := gerar_cadastros(contatos, profit)),
                           execucoes=gerar_execucoes(cad), jornadas=gerar_jornadas())
    painel["followups_ancorados_em"] = agora.isoformat(timespec="seconds")

    radar = renderizar_painel(painel).replace(
        '<meta name="claude:viewport-fit-sides" content="cover">\n', "")
    (SAIDA / "radar" / "index.html").write_text(pagina_completa(radar, "Radar do Assessor"), encoding="utf-8")
    shutil.copy(PASTA / "templates" / "home.html", SAIDA / "index.html")
    print(f"Site pronto em {SAIDA.resolve()}")
