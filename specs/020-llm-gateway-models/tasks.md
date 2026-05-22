# Tarefas: LLM Gateway e Registry de Modelos

**Entrada**: `specs/020-llm-gateway-models/spec.md` + `plan.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md` do gateway/registry em `specs/020-llm-gateway-models/spec.md`
- [x] T002 [P0] [claude-code] Registrar dívida DT-001..003

## Fase 2 — Dívida de código (futuro; não executar nesta frente)

- [ ] T010 [P2] [any] Dividir `backend/app/llm_gateway/providers.py` em `providers/<provider>.py` mantendo fachada `gateway.py` (DT-001)
- [ ] T011 [P2] [any] Consolidar fonte única de pricing (registry + `model_pricing.json`) com IDs/custos reais (DT-002)
- [ ] T012 [P2] [any] Adicionar testes de contrato por provider (stream/imagem/deep research) em `backend/tests` (DT-003)

## Notas

- Fase 2 só inicia após decisão do dono; preservar contrato público de `LLMGateway`.
