# spec.md

## Título

RAG, dados sensíveis e uso de provedores externos

## Status

Decisões de produto aprovadas; implementação futura.

## Objetivo

Evoluir o pipeline de arquivos, documentos e bases mantendo escopo por projeto/agente, classificação sensível manual e heurística, e uso rastreável de provedores externos.

## Requisitos funcionais

- QUANDO um arquivo for processado, O SISTEMA DEVE diferenciar upload, parsing, chunking, indexação, vinculação a bases e recuperação.
- QUANDO conteúdo sensível for detectado ou marcado, O SISTEMA DEVE registrar a classificação sensível.
- QUANDO documentos indexados forem usados em prompt para OpenAI, Anthropic ou Google, O SISTEMA PODE enviá-los conforme bases ativas e escopo permitido.
- QUANDO RAG montar contexto, O SISTEMA DEVE respeitar projeto ativo, agente ativo, bases ativas e limites da base.
- QUANDO uma busca acessar documentos, O SISTEMA DEVE registrar evento auditável.

## Fora do escopo imediato

- Fluxo automático assistido para transformar importação do ChatGPT em bases revisadas.
- Backup local.

## Fontes

- `docs/knowledge-bases.md`
- `docs/decisions.md`
- `specs/000-repo-foundation/spec.md`
