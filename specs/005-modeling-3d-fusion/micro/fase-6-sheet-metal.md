# Micro-plano — Fase 6: Sheet metal

**Fase**: 6 | **Spec**: [`../spec.md`](../spec.md) (RF-016 sheet metal) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 5. Onda de cobertura.

## Objetivo

Cobrir o workspace **Sheet Metal** do Fusion: regras de chapa (espessura, raio de dobra, alívios), flanges, dobras, conversão para chapa, e planificação (flat pattern), com verificação dimensional adequada.

## Estado atual (ponto de partida)

- Cobertura de sheet metal inexistente no adapter.
- Pipeline de sólido + selectors + verificação disponíveis.

## Decisões-chave

1. **Regra de chapa** (sheet metal rule) como entidade do plano: espessura, raio de dobra, tipo de alívio.
2. **Tools**: criar face base, flange, dobra (bend), unfold/refold, flat pattern; conversão de sólido para sheet metal quando aplicável.
3. **Verificação**: espessura constante, ângulos de dobra, e flat pattern gerado.
4. **Export**: flat pattern para DXF como artifact quando o destino for fabricação (liga com RF-026/artifacts).

## Tarefas atômicas

- **T6.1** ✅ — `fusion.convert_to_sheet_metal` (`ConvertToSheetMetalFeatures.createInput(bodies)`) com `thickness_mm` opcional (usa SheetMetalRule default se omitido). Marca `is_sheet_metal: true` no output.
- **T6.2** ✅ — `fusion.flange_edge` (`FlangeFeatures.createInput(edges)` + `inp.height`/`inp.angle`). Aceita `edge_ids` (de query_geometry) OU `edge_selector` semântico. Height/angle paramétricos (G1.1).
- **T6.3** ✅ — `fusion.bend_edge` (`BendFeatures.createInput(edges, angle, radius)`) — aplica bend em aresta interior; complementa flange (que cria material novo).
- **T6.4** ✅ — `fusion.unbend` (`UnbendFeatures.createInput(faces, isRoot=true)`) — achata para flat pattern. Sem `face_ids` o handler escolhe a primeira face planar do body.
- **T6.5** ✅ — `fusion.rebend` (`RebendFeatures.createInput(faces)`) — restaura geometria 3D após unbend.
- **T6.6** (pendente) — Flat pattern + export DXF como artifact (RF-026). Não bloqueia o gate base; entra como follow-up se o gate exigir.

## Contratos / invariantes

- Allowlist de fonte única; verificação por passo; artifacts/printability conforme contrato (P8).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- **Gate do dono (Fusion real)**: peça **Nível 3** (chapa dobrada com flanges e alívios + flat pattern) modelada por chat.

## Riscos

- **Regras de chapa específicas** (material/processo) → parametrização extensa. Mitigação: começar com regra default + override; expandir conforme demanda do dono.

## Definição de pronto (Fase 6)

- [x] **T6.1–T6.5** — 5 tools de sheet metal (convert_to_sheet_metal, flange_edge, bend_edge, unbend, rebend) registradas, schemas, dispatch, e teste `test_sheet_metal_tools_registered_and_compile` verde.
- [ ] **T6.6** — Flat pattern + export DXF (follow-up demanda-dirigido).
- [~] **Gate do dono (Fusion real)** — chapa dobrada Nível 3 (pendente — código+testes mock prontos).
