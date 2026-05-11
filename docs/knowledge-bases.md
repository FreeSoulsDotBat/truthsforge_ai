# Bases de conhecimento

## Modelo mental

`Arquivos` e a biblioteca bruta da plataforma. Todo arquivo enviado, recebido, importado ou gerado deve aparecer ali, com deduplicacao e pre-visualizacao quando aplicavel.

`Documentos indexados` sao a representacao tecnica desses arquivos para busca: texto extraido, chunks, metadados e vetores no Qdrant.

`Bases de conhecimento` sao colecoes curadas desses documentos. Uma base define escopo, tags, prioridade e limites de recuperacao, como `top documentos por busca` e `chunks por documento`.

`Projetos` organizam chats, pastas e contexto humano. Um projeto pode ter bases atreladas, mas nao precisa ter. Pastas continuam como organizacao visual e filtro opcional quando o usuario cita uma pasta com autocomplete.

`Agentes` podem ter bases proprias. Na hora do chat, o backend usa a uniao das bases do agente ativo com as bases do projeto atual.

## O que entra na chamada da LLM

Uma base pode ter muitos arquivos. O limite importante nao e o numero bruto de arquivos da base, mas quanto dela entra em cada chamada.

No MVP, cada base controla:

- quantos documentos podem ser recuperados por pergunta;
- quantos chunks de cada documento podem entrar no prompt;
- se a base esta habilitada;
- prioridade e pinagem por documento dentro da base.

Isso permite manter uma base grande sem mandar tudo para a LLM.

## Ranqueamento por relevancia

O ranqueamento inicial e interno e nao usa uma segunda chamada de LLM.

1. O backend transforma a pergunta atual em embedding.
2. O Qdrant compara esse embedding com os chunks indexados e retorna os mais proximos semanticamente.
3. O backend filtra os resultados pelas bases habilitadas do agente/projeto.
4. Se o usuario citou uma pasta, o backend usa essa pasta como filtro opcional de escopo.
5. O backend aplica pequenos boosts baratos: prioridade da base, prioridade do documento e documentos fixados.
6. O prompt final recebe apenas os snippets melhor ranqueados dentro dos limites da base.

A inteligencia contextual vem da combinacao de embeddings + metadados + regras de escopo. Uma LLM reranker pode ser adicionada depois, mas ficara opt-in porque gera custo adicional.

## Importacao do ChatGPT

Ao importar um export do ChatGPT, as conversas entram no historico e os assets uteis entram em `Arquivos`. Arquivos informativos do proprio export, como `conversations.json`, `shared_conversations.json`, `user.json` e `user_settings.json`, nao viram arquivos de biblioteca para evitar ruido.

Arquivos uteis ficam disponiveis para indexacao em segundo plano. Conforme forem indexados, podem ser adicionados em bases de conhecimento.

## Fluxo recomendado

1. Envie ou importe arquivos.
2. Confirme que eles aparecem em `Arquivos`.
3. Abra `Bases`.
4. Crie uma base com nome, escopo e tags claras.
5. Adicione arquivos/documentos a essa base.
6. Atrele a base a um projeto ou agente.
7. No chat, use `Editar bases de conhecimento atreladas` para mudar o conjunto daquela conversa quando precisar.

