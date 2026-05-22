# Tarefas: Custo, Auditoria e Observabilidade

**Entrada**: `specs/060-cost-audit-governance/spec.md` + `plan.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md` consolidando custo+auditoria+golden paths
- [x] T002 [P0] [claude-code] Migrar `observability-quality` e arquivar em `specs/_legacy/`
- [x] T003 [P0] [claude-code] Registrar dívida DT-001..003

## Fase 2 — Implementação (futuro; herdada do legado + dívida)

- [ ] T010 [P1] [any] Mapear lacunas de auditoria por evento obrigatório (matriz evento→código→teste) (DT-002)
- [ ] T011 [P1] [any] Criar golden paths: chat, RAG, upload/indexação, agente restrito, 3D, mobile (DT-003)
- [ ] T012 [P2] [any] Padronizar schema de auditoria e consolidar retenção (DT-001)

## Notas

- Fase 2 herda tarefas do legado `observability-quality`; iniciar após decisão do dono.
