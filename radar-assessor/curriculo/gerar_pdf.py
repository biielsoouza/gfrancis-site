"""Gera os PDFs do currículo (português e inglês) a partir dos HTML desta pasta.

Uso: python curriculo/gerar_pdf.py   (precisa do Playwright com Chromium)
Saída: portfolio/curriculo-gabriel-francis.pdf e portfolio/resume-gabriel-francis.pdf
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA.parent / "portfolio"
ARQUIVOS = {"curriculo-pt.html": "curriculo-gabriel-francis.pdf", "curriculo-en.html": "resume-gabriel-francis.pdf"}


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch()
        pagina = await nav.new_page()
        for html, pdf in ARQUIVOS.items():
            await pagina.goto((PASTA / html).as_uri())
            await pagina.wait_for_timeout(400)
            estouro = await pagina.evaluate("[...document.querySelectorAll('main')].map(m => m.scrollHeight - m.clientHeight)")
            if any(e > 2 for e in estouro):
                raise SystemExit(f"{html}: o conteúdo passou do tamanho da página ({estouro})")
            await pagina.pdf(path=str(SAIDA / pdf), prefer_css_page_size=True, print_background=True)
            print("ok", pdf)
        await nav.close()


if __name__ == "__main__":
    asyncio.run(main())
