# <img title="" src="logo.png" alt="" align="left" height="80"> Questionário Bot

Bot questionário utilizado para permitir os usuários avaliarem meus bots no Telegram.

<img src='output_hZtnxI.gif' alt="" align="center" height="400"/>

## Template

Esse bot permite três tipos de perguntas:

- Pergunta que permite a seleção de múltiplas escolhas
- Pergunda que permite a seleção de no máximo uma das opções
- Pergunta que permite o usuário responder com suas próprias palavras.
  - Apenas uma mensagem por resposta.

As perguntas são lidas a partir de um arquivo JSON no padrão `survey_{nome_do_bot}.json`, as respostas são salvas no bando de dados PostgreSQL.


### Requisitos
Instalar os requirements.txt, definir as variáveis de ambiente contendo o TOKEN e DATABASE_URL.
