# Radar do Assessor

Painel que diz ao assessor **quem chamar hoje, por qual canal, em que horário e com qual mensagem**, a partir do histórico de contatos do CRM. O objetivo comercial é ativar clientes em renda variável, principalmente minicontratos de índice (WIN) e dólar (WDO).

> Protótipo. Todos os dados são **fictícios**, gerados por código. Nenhum dado de cliente real foi usado.

---

## O problema

O CRM já registra cada contato com data, hora, canal (WhatsApp, telefone, e-mail) e resultado (respondeu / sem sucesso). Essa informação fica parada. O assessor decide quem chamar e quando de cabeça, e acaba ligando para quem não atende naquele horário, ou deixando esfriar quem costumava responder rápido.

## O que o painel faz

| Funcionalidade | Como é calculada |
|---|---|
| **Lista do dia** | Nota de 0 a 100 que combina urgência (atraso em relação ao ritmo normal, queda na taxa de resposta, tempo sem contato) com a chance de dar certo na melhor janela. |
| **Melhor janela por cliente** | Chance estimada de resposta em cada combinação de canal × faixa de horário. |
| **Clientes esfriando** | Cliente que está 3x além do seu ritmo normal de resposta, ou cuja taxa caiu 40%+ no último mês. |
| **Mapa de calor da carteira** | Taxa de resposta por dia da semana × faixa de horário. |
| **Sugestão de mensagem** | Texto pronto conforme a situação do cliente (esfriando, responde pouco, sem contato, em dia) e o canal: mensagem curta no WhatsApp, e-mail com assunto, roteiro de ligação no telefone. Cinco abordagens por situação, com botão de copiar. |
| **Oferta Profit** | Seis abordagens para a campanha vigente: Profit Ultra (versão mais completa do ProfitChart, da Nelogica) com Automação Premium 1.000 (plano de automação com limite de até 1.000 minicontratos), isentos com 10 minicontratos operados no mês, em todos os canais, sempre com aviso de risco. A campanha fica em um único lugar: `OFERTA` em `radar/mensagens.py`. |
| **Carteira Profit** | Quatro abas: **Tem Profit?** (com filtro sim/não e situação de cada cliente), **Falta operar** (tem Profit, 0 minicontratos no mês), **Abaixo da isenção** (1 a 9 minicontratos, os mais perto da meta primeiro, com quanto falta) e **Leads sem contato** (leads distribuídos ao assessor que nunca receberam contato, os mais antigos primeiro). Mostra quantos dias úteis faltam para fechar o mês. Cada situação tem mensagens próprias: lembrete de isenção com o número exato que falta, apoio na plataforma, e primeiro contato com leads usando o interesse que eles informaram. |
| **Aniversariantes** | Cartão com quem faz aniversário hoje e nos próximos 7 dias (data, idade e assessor), aviso ao abrir o app e banner no detalhe do cliente. A aba "Aniversário" traz quatro mensagens de parabéns, sem nenhuma oferta: mensagem comercial no aniversário soa oportunista. A contagem de dias é refeita no navegador, então continua certa dias depois. |
| **Menu lateral e login** | Menu fixo com as seções do painel (destaca a seção que está na tela) e, no celular, menu que abre pelo botão do topo. Tela de entrada de demonstração: o assessor informa nome e função, e o menu mostra o perfil com status (Online, Em atendimento, Ausente). Não há autenticação real: a sessão fica só no navegador. |
| **Clientes (cadastro)** | Busca por nome, e-mail, CPF ou código e ficha completa de cada cliente: nome, código, e-mail, CPF (mascarado, com botão para mostrar), telefone (com botão de copiar), perfil de investidor, cliente desde, plataforma e minicontratos operados nos últimos 30 dias por ativo (WIN, WDO, BIT). Setas na ficha (ou ← →) passam de um cliente para o próximo. Os CPFs fictícios têm dígitos verificadores errados de propósito, então nunca coincidem com o CPF de alguém. |
| **Plataformas sem isenção** | Clientes com Profit Ultra + Automação Premium 1.000 que ainda não chegaram a 10 minicontratos no mês, com quantos estão perto da meta, quantos minicontratos faltam no total e quantos têm perfil incompatível com derivativos. |
| **Operação em tempo real (beta)** | Fluxo de ordens no formato "Comprou 1 WINZ26 / Vendeu 2 WDOX26", com o código de vencimento calculado pela data (WIN: meses pares, quarta-feira mais próxima do dia 15; WDO: 1º dia útil do mês; BIT: última sexta-feira; sem considerar feriados), contadores do dia e aviso quando um cliente atinge a isenção. Na demonstração as ordens são simuladas; em produção viriam da corretora. |
| **Execuções** | Histórico de ordens dos últimos 30 dias com filtros de período (Hoje, Ontem, 7, 15, 30 dias ou datas no calendário), ativo, compra/venda e cliente. Gráfico de minicontratos por dia (WIN, WDO, BIT) e tabela no formato "Comprou 2 WINZ26". As execuções de cada cliente somam exatamente os minicontratos de 30 dias da ficha dele (há teste para isso). |
| **Disparos de e-mail (HubSpot)** | Cinco campanhas automáticas: aviso de cobrança do Profit (5 dias úteis e 1 dia útil antes do último dia útil do mês), oferta para quem não tem Profit, aniversário e boas-vindas a leads. Cada uma mostra público do dia, próximo disparo e pré-visualização do e-mail com os dados de um cliente ou com as variáveis do HubSpot. O assessor pode enviar para o público todo ou marcar destinatários específicos (com busca e "selecionar todos") e enviar só para eles. Quem tem perfil incompatível com derivativos fica fora das campanhas que falam de operar. O Radar envia os dados para o HubSpot (`radar/hubspot.py`) e os Workflows de lá fazem o envio. Na demonstração, nada é enviado. |
| **Alertas de follow-up** | Clientes com status "followup" no CRM aparecem no sino do topo. Ao abrir, um resumo (atrasados, para agora, mais tarde). Depois, um pop-up na hora de cada retorno, com opção de abrir o cliente, adiar 15 minutos ou marcar como feito. Com permissão, também chega como notificação do navegador quando o app está em segundo plano. |
| **Insights** | Frases curtas em linguagem de assessor ("WhatsApp rende 1,3x mais respostas que e-mail"). |

Filtro por assessor no topo. Clique em qualquer cliente para ver o detalhe.

---

## Decisões técnicas

### 1. Suavização (média bayesiana)
Um cliente com 2 contatos e 2 respostas teria "100% de resposta", o que é estatisticamente sem sentido. Toda taxa é calculada como:

```
(respostas + PESO × taxa_de_referência) / (contatos + PESO)
```

Com pouco histórico, o número fica perto da média. Com muito histórico, o comportamento real do cliente domina.

### 2. Canal e horário estimados separadamente
Um cliente tem em média ~15 contatos. Isso não basta para preencher 18 células (3 canais × 6 faixas) com confiança. Então o efeito do canal e o efeito do horário são estimados **cada um com todos os contatos do cliente**, e depois combinados:

```
chance(canal, faixa) = taxa_do_cliente × efeito_do_canal × efeito_da_faixa
```

Cada efeito tem teto de 1,5x, para dois efeitos fortes não inflarem a chance além do que o histórico sustenta.

### 3. "Esfriando" ≠ "sempre foi frio"
Quem quase nunca respondeu não é marcado como esfriando. Recebe outro aviso ("Responde pouco — testar outro canal"), porque a ação certa é diferente.

### 4. Mensagens por modelo, não por IA
As sugestões de texto saem de modelos fixos (`radar/mensagens.py`), e não de uma IA escrevendo texto livre. Num ambiente regulado, todo texto que pode chegar ao cliente precisa ser conhecido de antemão e revisável pelo compliance. Os modelos nunca falam de produto, rentabilidade ou promessa de resultado, e um teste automático barra termos proibidos.

### 5. Oferta de derivativos com aviso de risco
WIN e WDO são derivativos. Toda mensagem de oferta sai com aviso de risco (no WhatsApp, no e-mail e como passo obrigatório no roteiro de ligação), e o painel lembra o assessor de conferir o perfil de investidor antes de enviar. Um teste garante que nenhuma oferta sai sem o aviso. Próximo passo natural: ler o suitability do CRM e esconder a oferta para perfis incompatíveis.

### 6. Um ponto único de entrada de dados
Toda a leitura de dados passa por sete funções em `app.py`: `carregar_contatos()`, `carregar_followups()`, `carregar_profit()`, `carregar_leads()`, `carregar_nascimentos()`, `carregar_cadastros()` e `carregar_execucoes()`. Para plugar no CRM real, basta trocar cada uma por uma consulta que devolva as mesmas colunas. O resto do código não muda.

---

## Validação

O gerador "planta" comportamentos escondidos em cada cliente fictício (canal preferido, horário preferido, se esfriou). Os testes conferem se as métricas **reencontram** esses padrões:

| O que foi plantado | Resultado |
|---|---|
| Canal preferido | acerta **~76%** dos clientes |
| Horário preferido (exato) | acerta **~40%** (6 faixas possíveis; o acaso daria 17%) |
| Horário preferido (±1 faixa) | acerta **~73%** |
| Clientes que esfriaram | têm nota média maior que os demais |

O horário exato é o ponto mais fraco, por falta de dados por cliente. Com histórico real mais longo, tende a melhorar.

---

## Estrutura

```
radar-assessor/
├── app.py               servidor web (Flask) e rotas da API
├── exportar.py          gera o painel como um único .html, sem servidor
├── iniciar.bat          abre o painel com dois cliques (Windows)
├── radar/
│   ├── gerador.py       dados fictícios no formato do CRM
│   ├── metricas.py      todos os cálculos
│   └── mensagens.py     modelos de mensagem por situação e canal
├── templates/
│   └── painel.html      interface (HTML/CSS/JS puro, sem framework)
└── tests/
    ├── test_metricas.py
    └── test_mensagens.py
```

### API

| Rota | Retorno |
|---|---|
| `GET /` | painel |
| `GET /api/painel` | todos os dados em JSON |
| `GET /api/followups` | clientes com status "followup" |
| `GET /api/leads` | leads ainda sem contato |
| `GET /api/segmentos` | contagem por situação no Profit |
| `GET /api/sem-isencao` | plataformas ainda não isentas no mês |
| `GET /api/execucoes` | execuções dos últimos 30 dias (formato compacto) |
| `GET /api/aniversarios` | aniversariantes de hoje e dos próximos 7 dias |
| `GET /api/clientes/<id>` | detalhe de um cliente, com mensagens e ofertas |

---

## Como rodar

**Windows, sem terminal:** dê dois cliques em `iniciar.bat`. Na primeira vez ele instala o que precisa. O painel abre no navegador.

**Pelo terminal:**

```bash
pip install -r requirements.txt
python app.py          # abre http://127.0.0.1:5000
python -m pytest       # roda os testes
python exportar.py     # gera radar_do_assessor.html
```

---

## Integração com o HubSpot

1. Crie as propriedades de contato listadas em `PROPRIEDADES` (`radar/hubspot.py`) no HubSpot.
2. Crie um aplicativo privado no HubSpot com o escopo `crm.objects.contacts.write` e guarde o token.
3. Para cada campanha de `radar/emails.py`, crie um e-mail marketing (a rota `/api/campanhas` entrega assunto e HTML já com as variáveis do HubSpot) e um Workflow que inscreve os contatos com a campanha marcada em `radar_campanhas`.
4. Para envios manuais, `inscrever_selecionados(emails, workflow_id, token, simular=False)` inscreve só os contatos escolhidos no Workflow da campanha.
5. Uma vez por dia, rode `montar_lotes(...)` e `enviar_lotes(lotes, token, simular=False)`: os contatos são atualizados em lotes de 100 pela API `crm/v3/objects/contacts/batch/upsert`.

Os e-mails dos clientes fictícios usam os domínios `example.com`, `example.net` e `example.org`, reservados para exemplos: nenhum deles pertence a alguém.

## Nome da empresa nas mensagens

O padrão é genérico ("Sua Corretora"). Para usar o nome da sua empresa no seu computador, crie um arquivo `empresa.txt` nesta pasta com o nome dentro. Ele está no `.gitignore`, então nunca vai para o GitHub nem para o site público.

---

## Publicar no site (gfrancis.com.br)

O site é publicado sozinho pela Netlify a cada mudança enviada ao GitHub (veja o `netlify.toml` na raiz do repositório). A cada publicação ela:

1. instala as dependências (`requirements.txt`);
2. roda os testes, e **se algum falhar, a publicação é cancelada** e o site continua na versão anterior;
3. roda `publicar_site.py`, que monta a pasta `site/` com a página inicial e o Radar.

A versão pública usa sempre o nome genérico (`NOME_PUBLICO`) e só dados fictícios. Na demonstração, as datas acompanham o dia em que a página é aberta.

---

## Próximos passos

- Ligar `carregar_contatos()` a uma consulta (somente leitura) do CRM.
- Registrar se o assessor seguiu a sugestão, para medir se a lista aumenta a taxa de resposta.
- Ler o perfil de investidor (suitability) do CRM e só sugerir a oferta para perfis compatíveis.
- Marcar o follow-up como feito direto no CRM, em vez de só no navegador.
- Levar os modelos de mensagem para revisão do compliance e deixar o time sugerir novos.
- Considerar eventos de carteira (vencimentos, aportes, saldo parado) na nota de prioridade.

---

<sub>By **trops**</sub>
