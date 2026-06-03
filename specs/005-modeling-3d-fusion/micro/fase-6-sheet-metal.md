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

> ⛔ **T6.1–T6.5: implementadas então REMOVIDAS (DT-011, commit `877ac23`).** A
> API Python do Fusion **não expõe** sheet metal (ver "ACHADO DE GATE" abaixo):
> os métodos invocados não existem. As tools saíram da allowlist/dispatch/schemas;
> `test_sheet_metal_tools_are_removed` impede reintrodução. **Não estão mais
> registradas.** Detalhe histórico mantido para rastreabilidade.

- **T6.1** ⛔ (removida) — `fusion.convert_to_sheet_metal` (`ConvertToSheetMetalFeatures.createInput(bodies)`) com `thickness_mm` opcional. *Método inexistente na API.*
- **T6.2** ⛔ (removida) — `fusion.flange_edge` (`FlangeFeatures.createInput(edges)` + `inp.height`/`inp.angle`). *`FlangeFeatures` é coleção read-only (sem `createInput`/`add`).*
- **T6.3** ⛔ (removida) — `fusion.bend_edge` (`BendFeatures.createInput(...)`). *`bendFeatures` inexistente.*
- **T6.4** ⛔ (removida) — `fusion.unbend` (`UnbendFeatures.createInput(...)`). *`unbendFeatures` inexistente.*
- **T6.5** ⛔ (removida) — `fusion.rebend` (`RebendFeatures.createInput(...)`). *`rebendFeatures` inexistente.*
- **T6.6** (pendente) — Flat pattern + export DXF como artifact (RF-026). Não bloqueia o gate base; entra como follow-up se o gate exigir.

## Contratos / invariantes

- Allowlist de fonte única; verificação por passo; artifacts/printability conforme contrato (P8).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- **Gate do dono (Fusion real)**: peça **Nível 3** (chapa dobrada com flanges e alívios + flat pattern) modelada por chat.

## Riscos

- **Regras de chapa específicas** (material/processo) → parametrização extensa. Mitigação: começar com regra default + override; expandir conforme demanda do dono.

## ⛔ ACHADO DE GATE (2026-05-29): API do Fusion NÃO suporta sheet metal

Validação autônoma no Fusion real (introspecção via probe direto no adapter)
revelou que a **API Python do Fusion 360 (versão do dono) não expõe o workflow
de sheet metal**:

- `rootComponent.features` → **só `flangeFeatures`** (sheet metal). E
  `FlangeFeatures` é uma **coleção read-only**: métodos `cast/count/isValid/
  item/itemByName/objectType` — **sem `add` nem `createInput`**. Não dá pra
  *criar* flange via API.
- **Não existem** `convertToSheetMetalFeatures`, `bendFeatures`,
  `unbendFeatures`, `rebendFeatures`.
- `design` expõe só `designSheetMetalRules`/`librarySheetMetalRules`;
  `rootComponent` só `activeSheetMetalRule`. Nada de criar base/flat-pattern.
- `features` de criação disponíveis: `baseFeatures`, `meshConvertFeatures` —
  nenhuma serve para sheet metal.

**Conclusão:** as 5 tools T6.1–T6.5 (convert/flange/bend/unbend/rebend) foram
implementadas contra métodos **inexistentes** na API. Sheet metal é
majoritariamente **UI-only** no Fusion; não há workaround dentro da allowlist
(ADR-019) porque a plataforma não oferece os métodos. **DT-011** (nova): Fase 6
bloqueada por teto da plataforma.

**Decisão do dono pendente** (opções):
1. **Remover** as 5 tools da allowlist (`tool_registry`/`tool_schemas`/dispatch)
   — não expor ao planner o que sempre falha (evita planos mortos). Marcar Fase 6
   como bloqueada no roadmap.
2. **Reescopar** Fase 6 para "chapa dobrada aproximada via sólido" (extrude +
   chanfros/dobras manuais como sólido comum) — não é sheet metal verdadeiro
   (sem flat-pattern/DXF), mas cobre impressão 3D de peças tipo chapa.
3. **Adiar** Fase 6 indefinidamente e seguir para Fase 7/8.

Recomendação: (1) + documentar; reescopo (2) só se o dono tiver caso real.

**DECISÃO DO DONO (2026-05-29): opção (1) — REMOVER as tools.** As 5 tools
(convert_to_sheet_metal/flange_edge/bend_edge/unbend/rebend) foram removidas de
`fusion_mcp_scripts.py` (handlers + allowlist + dispatch), `tool_registry.py`,
`tool_schemas.py`. Teste de regressão `test_sheet_metal_tools_are_removed`
impede reintrodução acidental. Fase 6 fica **bloqueada por plataforma** até a
Autodesk expor a API de sheet metal no Python. Roadmap segue para Fase 7/8.

## Definição de pronto (Fase 6) — ⛔ FASE CONGELADA (DT-011)

- [⛔] **T6.1–T6.5** — 5 tools de sheet metal **implementadas então REMOVIDAS** (commit `877ac23`): a API Python do Fusion não as suporta. `test_sheet_metal_tools_are_removed` guarda contra reintrodução. **Não estão mais registradas.**
- [⛔] **T6.6** — Flat pattern + export DXF — **sem efeito** (sem base de sheet metal na API).
- [⛔] **Gate do dono (Fusion real)** — **não aplicável**: fase bloqueada por teto de plataforma (DT-011) até a Autodesk expor a API.
