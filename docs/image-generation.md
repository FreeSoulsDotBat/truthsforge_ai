# Geracao de imagem

O atalho `Imagem` no composer troca o envio atual para `response_mode="image"` e chama `LLMGateway.generate_image`.

## Como usar

1. Configure uma chave OpenAI em `Configurações > Provedores`.
2. Garanta que exista um modelo com capacidade `image_generation` no registry. O dev store ja cria entradas OpenAI como `openai/default-image` e modelos `gpt-image-*`.
3. No composer, abra o menu de execucao, ative `Imagem` e escolha o modelo de imagem quando houver mais de uma opcao.
4. Envie o briefing visual em portugues BR.

## Compatibilidade

- A implementacao real existe no `OpenAIProvider` via `POST https://api.openai.com/v1/images/generations`.
- Anthropic e Google estao no gateway para chat, mas ainda nao implementam `generate_image`. O dev store chega a semear uma entrada `google/default-image` no registry, porem selecionar qualquer modelo Anthropic/Google para imagem retorna erro de configuracao (o provider nao sobrescreve `generate_image`).
- O frontend desliga `Pesquisa OpenAI` e `Resumo oficial` quando `Imagem` e ativado, porque esses modos sao mutuamente exclusivos no contrato `ChatStreamRequest`.
- O backend bloqueia imagem quando o modelo selecionado nao tem `ModelCapability.image_generation`.

## Arquivos gerados

O provider pode devolver URL remota ou `b64_json`. O backend baixa/persiste a imagem em `.local/files`, cria um `PlatformFile` com `source="generated"` e tags `generated`, `image`, substitui o Markdown por uma URL local `/api/files/{id}/content` e adiciona `generated_file_ids` na metadata da mensagem.

Esses arquivos aparecem na aba `Arquivos`, entram no status de indexacao e podem ser associados a bases quando fizer sentido.

## Custo

Imagem passa pelo Cost Governor antes da chamada. Se `input_token_cost_per_million` ou `output_token_cost_per_million` do modelo de imagem estiverem ausentes, a UI mostra `preço obrigatório` e o backend bloqueia o envio.
