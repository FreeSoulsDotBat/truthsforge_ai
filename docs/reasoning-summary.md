# Resumo oficial de raciocinio

O atalho `Resumo oficial` no composer do chat solicita `reasoning.summary=auto` para modelos OpenAI compatíveis com a Responses API.

Esse recurso nao mostra cadeia de pensamento bruta. Ele exibe somente o resumo autorizado pelo provedor quando o modelo envia eventos de summary no stream.

## Custo

O atalho fica desligado por padrao porque o resumo entra como saida adicional da chamada. A estimativa pratica usada para o MVP:

- resumo curto, cerca de 100 tokens: custo extra muito baixo por chat;
- resumo medio, cerca de 250 tokens: custo extra baixo, mas acumulavel;
- resumo detalhado, cerca de 750 tokens: pode pesar em volume alto ou modelos caros.

O backend inclui o resumo na estimativa de `tokens_out` da auditoria quando ele estiver presente.

## Bloqueio de seguranca

O Cost Governor bloqueia o envio antes de chamar o provedor quando `Resumo oficial` estiver ativo e o modelo do agente nao tiver:

- `input_token_cost_per_million` positivo;
- `output_token_cost_per_million` positivo.

Na UI, isso aparece como `preço obrigatório`.

## Compatibilidade

Nesta versao, o atalho fica disponivel apenas para chat em texto com modelos OpenAI. Ele e desligado automaticamente quando `Pesquisa OpenAI` ou `Imagem` entram em uso.
