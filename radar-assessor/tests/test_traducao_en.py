"""A versão em inglês (gfrancis.com.br/en/) é gerada do home.html: todo trecho da lista precisa existir."""
from pathlib import Path

from templates.traducao_en import traduzir

PASTA = Path(__file__).resolve().parent.parent


def test_home_em_ingles_sem_trechos_faltando():
    en = traduzir((PASTA / "templates" / "home.html").read_text(encoding="utf-8"))
    assert '<html lang="en">' in en
    assert "/portfolio/resume-gabriel-francis.pdf" in en
    for pt in ["Ver projetos", "Baixar currículo", "Quem eu sou", "Vamos conversar?", "Trajetória"]:
        assert pt not in en, pt


def test_curriculo_em_ingles_existe():
    assert (PASTA / "portfolio" / "resume-gabriel-francis.pdf").stat().st_size > 50_000
