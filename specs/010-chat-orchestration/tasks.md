# Tarefas: Orquestração de Chat (núcleo)

**Entrada**: `specs/010-chat-orchestration/spec.md` + `plan.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md` cobrindo o contrato atual do chat em `specs/010-chat-orchestration/spec.md`
- [x] T002 [P0] [claude-code] Registrar dívida DT-001..003 em `spec.md`
- [x] T003 [P1] [any] Referenciar este domínio a partir de `docs/application-map.md` na atualização de docs (retro-fit final)

## Fase 2 — Dívida de código (futuro; não executar nesta frente)

- [ ] T010 [P2] [any] Extrair service layer de `backend/app/api/routes/chat.py` → `backend/app/chat/` (orquestração, contexto/RAG, SSE, modos especiais) preservando o contrato SSE (DT-001)
- [ ] T011 [P2] [any] Injetar store via `Depends()` em vez de `get_store()` direto (DT-002)
- [ ] T012 [P2] [any] Mover glue de 3D inline de `chat.py` para a fronteira do bounded context 3D (DT-003)
- [ ] T013 [P2] [human] Avaliar ADR de "padrão service layer" cobrindo chat + demais domínios

## Notas

- Tarefas da Fase 2 são de refactor de código e exigem testes de regressão do contrato SSE; só iniciam após decisão do dono.
