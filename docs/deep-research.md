# Deep Research

O atalho `Pesquisa OpenAI` no composer do chat usa um modelo dedicado do registry:

- Modelo interno: `openai/deep-research`
- Modelo do provedor: `o4-mini-deep-research`
- Fonte habilitada: `web_search_preview`
- Execucao: Responses API em `background=true`
- Controle de custo/latencia: campo `Chamadas`, enviado como `max_tool_calls`

## Como usar

1. Abra `http://127.0.0.1:5173`.
2. Escolha o agente ativo no composer.
3. Ative `Pesquisa OpenAI`.
4. Ajuste `Chamadas` se quiser reduzir ou ampliar a busca.
5. Envie uma pergunta bem especifica, com objetivo, recorte temporal e formato esperado.

Enquanto a tarefa roda, o chat mostra mensagens de progresso. Ao finalizar, a resposta e salva no historico como qualquer mensagem da JUDITE.

## Configuracao

A API key da OpenAI deve estar configurada no backend, via `backend/.env` ou pela tela de configuracao do app. A chave nunca deve ser enviada pelo frontend diretamente ao provedor.

O modelo fica em `GET /api/models` e pode ser editado pela aba de configuracao de modelos. Deep Research fica bloqueado enquanto `input_token_cost_per_million` e `output_token_cost_per_million` nao estiverem preenchidos com valores positivos no registry. Isso impede pesquisa externa cara sem rastreio minimo de custo.

Se o atalho `Pesquisa OpenAI` mostrar `preço obrigatório`, configure os dois campos de custo do modelo `openai/deep-research` antes de usar.

## Notas de implementacao

Deep Research e separado do modelo normal do agente. Quando o atalho esta ativo, a mensagem usa `openai/deep-research` apenas naquele envio; a configuracao padrao do agente continua intacta.

Se `Imagem` for ativado, o modo Deep Research e desligado no frontend para evitar modos conflitantes.
