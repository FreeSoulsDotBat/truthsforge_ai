# plan.md

## Estratégia

Endurecer classificação e auditoria sem bloquear o uso normal de bases em provedores configurados.

## Sequência

1. Adicionar metadados de sensibilidade manual em arquivos, documentos e bases.
2. Criar heurística inicial de detecção sensível.
3. Expor classificação e filtros na UI.
4. Auditar uso de documentos em prompts externos.
5. Revisar limites por base/projeto/agente.

## Validação

- Testes de classificação manual.
- Testes de heurística sensível.
- Testes de escopo RAG por projeto/agente/base.
- Golden path de upload, indexação, base e chat com RAG.
