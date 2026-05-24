# Micro-plano — Fase 5: Superfícies (NURBS)

**Fase**: 5 | **Spec**: [`../spec.md`](../spec.md) (RF-016 superfície) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 4. Onda de cobertura.

## Objetivo

Cobrir o workspace **Surface** do Fusion: criação e edição de superfícies NURBS (loft, sweep, patch, revolve de superfície, trim, extend, offset, thicken, stitch/unstitch), com selectors de arestas/superfícies e verificação adaptada (área, fechamento, sólido resultante quando espessada).

## Estado atual (ponto de partida)

- Cobertura de superfície inexistente/parcial no adapter (workspace Sólido foi o foco do v3).
- Selectors estáveis e verificação geométrica disponíveis (Fases 2 e 4).

## Decisões-chave

1. **Conjunto de tools de superfície** priorizado (loft/sweep/patch/trim/extend/offset/thicken/stitch).
2. **Verificação**: além de bbox/volume, métricas de superfície (área, número de superfícies, se a costura fecha um sólido).
3. **Transição superfície → sólido** (thicken/stitch) tratada como ponte para o pipeline de sólido existente.

## Tarefas atômicas

- **T5.1** — Implementar tools de criação de superfície (loft/sweep/patch/revolve).
- **T5.2** — Implementar edição de superfície (trim/extend/offset/thicken/stitch/unstitch).
- **T5.3** — Selectors de aresta/superfície e verificação adaptada (área/fechamento).
- **T5.4** — Testes por tool (mock) + asserções; atualizar roadmap de cobertura.

## Contratos / invariantes

- Allowlist de fonte única; sem script livre; verificação obrigatória por passo dimensional.

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- **Gate do dono (Fusion real)**: peça **Nível 2** (carenagem/shell por superfície NURBS, espessada em sólido) modelada por chat.

## Riscos

- **Geometria NURBS sensível** (auto-interseção, falha de costura) → erros difíceis. Mitigação: verificação de fechamento + mensagens de erro claras + loop de correção.

## Definição de pronto (Fase 5)

- [ ] Criação e edição de superfície cobertas.
- [ ] Verificação adaptada a superfície.
- [ ] Testes verdes; gate do dono (Nível 2) aprovado.
