# Importacao do ChatGPT

O Truth's Forge AI importa historico exportado do ChatGPT sem chamar provedores de LLM.

## Formatos aceitos

- `conversations.json`
- `conversations-000.json`, `conversations-001.json` etc. dentro do ZIP
- `.zip` de exportacao contendo `conversations.json`

Se o ZIP tiver apenas `chat.html`, a importacao sera recusada nesta versao. O parser usa `conversations.json` ou os shards `conversations-*.json` porque eles preservam ids, papeis, ordem e metadados com mais seguranca. `shared_conversations.json` nao e tratado como historico principal.

## Como usar

1. Exporte seus dados no ChatGPT.
2. Baixe o ZIP enviado por email antes do link expirar.
3. Abra a aba `Bases`.
4. Use `Importar ChatGPT`.
5. Selecione o ZIP ou o `conversations.json`.

O upload cria um job local e registra o ZIP na area `Arquivos`. Quando o envio e um ZIP, os assets uteis tambem viram arquivos da plataforma referenciados pelo proprio ZIP (imagens, audio, video e anexos). Arquivos informativos da exportacao como `conversations*.json`, `shared_conversations.json`, `chat.html`, `user.json` e `user_settings.json` nao sao adicionados na biblioteca para reduzir ruido. A tela mostra status, progresso aproximado, tamanho do arquivo e resumo final. As conversas entram no historico do chat com metadata `source=chatgpt_export`.

## Deduplicacao

A importacao usa ids determinicos baseados nos ids originais do ChatGPT. Rodar o mesmo arquivo novamente nao duplica sessoes nem mensagens; o painel mostra quantas mensagens foram ignoradas como duplicadas.

## Limites atuais

- Limite de arquivo: 5 GB por padrão, configurável por `TRUTHS_FORGE_MAX_IMPORT_BYTES`.
- O arquivo é salvo em `.local/imports/` e processado em background.
- `conversations.json` é lido de forma incremental; o backend não carrega o export inteiro em memória.
- ZIPs shardados do ChatGPT sao processados em ordem por `conversations-000.json`, `conversations-001.json` e assim por diante.
- ZIPs são lidos sem extrair tudo para disco e passam por checagem básica contra compressão suspeita.
- Importa historico navegavel e registra os assets do export em `Arquivos`.
- Imagens do export podem ser abertas pela visualizacao de imagens da biblioteca.
- Arquivos uteis podem ser indexados em segundo plano e depois adicionados a bases de conhecimento.
- Conteudos nao textuais sao preservados como marcadores quando o export nao traz texto direto.

## Proximo passo

A evolucao natural e permitir criar bases automaticamente a partir de periodos, tags ou conversas importadas, mantendo revisao manual antes de atrelar essas bases a agentes ou projetos.
