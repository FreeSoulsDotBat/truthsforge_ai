# Micro-plano — Fase 7: Sculpt / T-Spline

**Fase**: 7 | **Spec**: [`../spec.md`](../spec.md) (RF-016 sculpt) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 6. Onda de cobertura. É a de **verificação mais difícil** (forma orgânica).

## Objetivo

Cobrir o workspace **Sculpt** (T-Spline) do Fusion: criar primitivas T-Spline, editar (inserir/extrudar/mover faces e arestas), simetria, e converter para BRep (sólido), com verificação por topologia + apoio do dono onde a métrica numérica não basta.

## Estado atual (ponto de partida)

- Cobertura de sculpt inexistente no adapter.
- Verificação geométrica (Fase 2) é dimensional; sculpt exige métricas topológicas e mais peso na revisão do dono.

## Decisões-chave

1. **Tools**: primitivas T-Spline (box/plane/sphere/cylinder/torus/quadball), editar faces/arestas (insert edge, extrude, weld, crease), simetria, converter para BRep.
2. **Verificação**: contagens topológicas (faces/arestas/vértices T-Spline), bbox, e validade na conversão para BRep; para fidelidade de forma orgânica, **peso maior na confirmação do dono** (RF-012 com oráculo parcial declarado).
3. **Symmetry/repair** como high-risk coberto pela aprovação do plano.

## Tarefas atômicas

- **T7.1** — Primitivas T-Spline + simetria.
- **T7.2** — Edição de faces/arestas (insert/extrude/move/weld/crease).
- **T7.3** — Conversão T-Spline → BRep com verificação de validade.
- **T7.4** — Verificação topológica + testes (mock).

## Contratos / invariantes

- Allowlist de fonte única; conversão/reparo high-risk sob aprovação do plano; sem script livre.

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- **Gate do dono (Fusion real)**: peça **Nível 4** (forma orgânica via T-Spline, convertida em sólido) modelada por chat.

## Riscos

- **Oráculo de verificação fraco** para forma orgânica. Mitigação: declarar verificação parcial (topologia + bbox + validade) e elevar o papel da revisão do dono no gate.

## Definição de pronto (Fase 7)

- [ ] Primitivas + edição + simetria + conversão BRep.
- [ ] Verificação topológica + validade de conversão.
- [ ] Testes verdes; gate do dono (Nível 4) aprovado.
