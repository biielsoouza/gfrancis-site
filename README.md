# gfrancis.com.br

Site pessoal de Gabriel Francis e os projetos publicados nele.

| Pasta | Projeto | No site |
|---|---|---|
| [`radar-assessor/`](radar-assessor/) | Radar do Assessor: quem chamar hoje, por qual canal, em que horário e com qual mensagem | `/radar/` |

## Como o site é publicado

A Netlify publica sozinha a cada envio para a branch `main` (configuração em [`netlify.toml`](netlify.toml)): instala as dependências, roda os testes e monta o site. Se algum teste falhar, a publicação é cancelada e o site continua na versão anterior.

Todos os dados dos projetos são fictícios.

<sub>By **trops**</sub>
