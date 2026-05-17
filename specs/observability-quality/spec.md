# spec.md

## Título

Observabilidade, auditoria, qualidade e golden paths

## Status

Decisões de produto aprovadas; implementação contínua.

## Objetivo

Garantir que todos os fluxos críticos sejam auditáveis e que mudanças relevantes sejam validadas por gates automáticos e golden paths visuais/e2e.

## Eventos auditáveis obrigatórios

- Chamadas LLM.
- Custo e uso.
- Tool calls.
- Acesso a documentos e uso em contexto.
- Exportações e deleções.
- Pareamento mobile.
- Falhas de indexação.

## Golden paths obrigatórios

- Chat básico.
- RAG com base de conhecimento.
- Upload e indexação.
- Agente restrito por projeto.
- Fluxo 3D.
- Fluxo mobile.

## Fontes

- `docs/delivery-checklist.md`
- `docs/implementation-plan.md`
- `specs/repo-foundation/spec.md`
