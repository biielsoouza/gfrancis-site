# gfrancis.com.br

Site pessoal de Gabriel Francis e os projetos publicados nele.

| Pasta | Projeto | No site |
|---|---|---|
| [`radar-assessor/`](radar-assessor/) | Radar do Assessor: quem chamar hoje, por qual canal, em que horário e com qual mensagem | `/radar/` |

## Como o site é publicado

A cada envio para a branch `main`, a hospedagem publica sozinha: instala as dependências, roda os testes e monta o site. Se algum teste falhar, a publicação é cancelada e o site continua na versão anterior.

- **Cloudflare** (destino): configuração em [`wrangler.jsonc`](wrangler.jsonc). Os arquivos do site são servidos direto e o Worker [`radar-assessor/cloudflare/worker.mjs`](radar-assessor/cloudflare/worker.mjs) atende `/api/cotacoes`. O token da brapi fica no segredo `BRAPI_TOKEN` do Worker.
- **Netlify** (em desligamento): configuração em [`netlify.toml`](netlify.toml).

A busca das cotações é a mesma nas duas: [`radar-assessor/cotacoes/nucleo.mjs`](radar-assessor/cotacoes/nucleo.mjs).

Todos os dados dos projetos são fictícios.

<sub>By **trops**</sub>
