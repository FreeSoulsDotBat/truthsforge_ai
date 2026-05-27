# Micro-plano — Fase 5: Superfícies (NURBS)

**Fase**: 5 | **Spec**: [`../spec.md`](../spec.md) (RF-016 superfície; CS-002 Nível 2) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 4 (gate condicional aprovado; Bug J' viaja pra Fase 9). Onda de cobertura. Contrato detalhado em [`../contracts/fusion-operations.md`](../contracts/fusion-operations.md) §3.10.

## Objetivo

Cobrir o workspace **Surface** do Fusion: criação e edição de superfícies NURBS (loft, sweep, revolve e extrude em modo superfície; patch; trim; extend; offset; thicken; stitch; unstitch), com selectors de arestas/superfícies e verificação adaptada (área, fechamento, sólido resultante quando espessada).

## Estado atual (ponto de partida, 2026-05-27)

- **Cobertura de superfície = zero** no adapter. Auditoria do `fusion_mcp_scripts.py` confirma 0 ocorrências de `PatchFeatures`/`ThickenFeatures`/`StitchSurfaces`/`TrimFeatures`/`ExtendFeatures`/`OffsetFeatures`.
- `loft_profiles`/`sweep_profile`/`revolve_profile`/`extrude_profile` existem mas sempre produzem **sólido** (`new_body`); não há flag para forçar SurfaceBody.
- Selectors/`query_geometry` operam só em `BRepBodies` sólidos.
- Verifier do loop (Item C) compara só bbox (`dimensions_mm`) — não enxerga "loft saiu aberto" ou "patch ficou com buraco".

## Decisões-chave

1. **Conjunto de tools de superfície** priorizado (loft/sweep/patch/trim/extend/offset/thicken/stitch). **11 itens-alvo** mapeados na §3.10 do contracts.
2. **Estratégia de operation overload**: para criação, **flag `as_surface: bool`** nas tools existentes (loft/sweep/revolve/extrude) — DRY, evita duplicar 4 schemas e simplifica nudges no planner. Para edição (patch/trim/extend/offset/thicken/stitch/unstitch), **tools novas dedicadas** — semântica diferente, schemas próprios, sem ambiguidade. Confirmado com o dono na transição Fase 4→5.
3. **Verificação adaptada**: além de bbox/volume, métricas de superfície (área, número de superfícies, `is_closed`). Verifier do loop ganha modo `surface`.
4. **Transição superfície → sólido** (thicken/stitch) tratada como ponte para o pipeline de sólido existente — output do thicken é `BRepBody`, retorna ao caminho consagrado de fillet/chamfer/export.
5. **Peça-exemplo do gate (Nível 2)**: **carenagem por superfície NURBS espessada em sólido** (confirmada pelo dono 2026-05-27). Fluxo-alvo detalhado na §3.10.10 do contracts.

## Tarefas atômicas

- **T5.0** ✅ **Mapeamento API Fusion → tools de superfície** em [`../contracts/fusion-operations.md`](../contracts/fusion-operations.md) §3.10 (11 itens: 4 expansões `as_surface` + 7 tools novas + selectors/read-back + fluxo da carenagem). Tabela-resumo §2 também atualizada com status 🚧 Fase 5.
- **T5.1** — Implementar criação de superfície:
  - **T5.1a** ✅ — flag `as_surface` em `extrude_profile`/`revolve_profile`/`sweep_profile`/`loft_profiles` (`input.isSolid = False`); output ganha `is_surface: bool`; backward-compat (sem flag = sólido). Cobertura por `test_create_surface_variants_via_as_surface_flag` + schemas em `tool_schemas.py`.
  - **T5.1b** ✅ — `create_surface_patch` (`PatchFeatures.createInput` com boundary via sketch OU `edge_ids` + `body_ref`); helper `_profile_or_open` aplicado nos 4 handlers da T5.1a → openProfile aceito quando `as_surface=true` e sketch tem só curvas abertas; helper `_collect_edges_for_patch` valida intervalo `[0, body.edges.count)`. Output do patch traz `surface_area_mm2` + `is_surface: true` + `body_name`. Cobertura: `test_create_surface_patch_registered_and_compiles`, `test_open_profile_fallback_in_surface_handlers`, `test_planner_toolset_matches_allowlist` atualizado.
- **T5.2** — Implementar edição de superfície (**caminho crítico do gate executado primeiro**: thicken + stitch fecham a carenagem; trim/extend/offset/unstitch ficam para rodada subsequente):
  - **T5.2d** ✅ — `thicken_surface` (`ThickenFeatures.createInput(coll, thickness, isSymmetric, op, isChainSelection)`) — ponte surface → solid. Aceita aliases `surfaces`/`body_refs`; thickness via `_param_value_input` (paramétrico G1.1); `is_symmetric` e `chain` opt-in; output traz `body_name`/`dimensions_mm`/`is_surface=false`.
  - **T5.2e** ✅ — `stitch_surfaces` (`StitchFeatures.createInput(coll, tolerance, op)`) — costura ≥ 2 superfícies; resultado pode ser SurfaceBody ou Body sólido (Fusion detecta se fechou volume); `is_surface` no output reflete o que saiu.
  - **T5.2a** — `trim_surface` (`TrimFeatures`) com seleção de célula a manter por área (`keep="largest"` default).
  - **T5.2b** — `extend_surface` (`ExtendFeatures`).
  - **T5.2c** — `offset_surface` (`OffsetFeatures`).
  - **T5.2f** — `unstitch_surface` (`UnstitchFeatures`).
- **T5.3** — Selectors e verificação adaptada:
  - **T5.3a** — `query_geometry` lista SurfaceBody + `is_solid`/`surface_area_mm2`/`is_closed`; novo selector `free_edges` em `_select_edges`.
  - **T5.3b** — Verifier ganha modo `surface` (`build_surface_verifier`): compara área esperada × medida e exige `is_closed=true` antes do thicken; fia no `run_plan_with_optional_loop`.
  - **T5.3c** — `expected_surface_area_mm2`/`expected_is_closed` no schema do planner (nudge + EXECUTION_PLAN_SCHEMA).
- **T5.4** — Testes por tool (mock) + asserções; `test_fusion_script_template_compiles_for_every_tool` cobre o novo conjunto; atualizar `../adapter-gaps-roadmap.md` marcando "Surfaces" fora da nota "Fora de escopo" (decisão consolidada no spec.md, §Premissas).

## Contratos / invariantes

- Allowlist de fonte única (`tool_registry.py`); sem script livre (P8, RF-023).
- Cada tool nova toca os 5 lugares canônicos (checklist §5 do contracts: scripts, registry, tool_schemas, planner toolset, testes).
- `as_surface=true` mantém backward-compat: sem o flag, comportamento idêntico ao atual.
- Verifier de superfície é **opt-in** via `expected_surface_area_mm2`/`expected_is_closed` — planos antigos sem esses campos continuam usando só o verifier de dimensões.

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest` (cobertura nova das 11 tools/expansões + verifier de superfície).
- **Gate do dono (Fusion real)**: **carenagem Nível 2** modelada por chat:
  - 2 splines (perfil + caminho) → sweep `as_surface` → 2 patches de tampa → stitch (deve detectar fechamento) → thicken 1.5 mm → fillet → export 3MF.
  - Critério de sucesso: peça sai espessada uniformemente, sem furos não-intencionais; rollback funciona ao desfazer a edição.

## Riscos

- **Geometria NURBS sensível** (auto-interseção, falha de costura) → erros opacos do Fusion. Mitigação: verifier de fechamento antes do thicken + mensagens de erro classificadas (`fusion.trim_no_intersection`, `fusion.stitch_gap_too_large`, etc.) + loop de correção.
- **APIs version-sensitive** (G5): `PatchFeatures.createInput` vs `createInput2`, `ThickenFeatures.add` signature mudou em versões recentes. Mitigação: try/except fallback como em chamfer/move.
- **Profile selection ambíguo** (open profile vs closed profile): `_resolve_profile_selection` assume profile fechado. Mitigação: caminho alternativo `openProfiles` quando `profile.isClosed=False` no extrude/sweep/loft `as_surface`.
- **`cells_to_remove` no trim**: a API exige célula calculada pelo Fusion após `createInput` — não trivial de selecionar deterministicamente. Mitigação: estratégia v1 = `keep="largest"` por área (Fusion calcula, adapter escolhe).
- **Cobertura sólido pode quebrar** ao mexer no `query_geometry`. Mitigação: estender sem alterar campos existentes (apenas adicionar `is_solid`, `surface_area_mm2`, `is_closed`).

## Definição de pronto (Fase 5)

- [x] **T5.0** — Mapeamento API Fusion → tools de superfície no contracts (§3.10).
- [x] **T5.1** — Criação de superfície (T5.1a `as_surface` ✅; T5.1b `create_surface_patch` + openProfiles ✅).
- [~] **T5.2** — Edição de superfície (T5.2d `thicken_surface` ✅; T5.2e `stitch_surfaces` ✅; trim/extend/offset/unstitch pendentes).
- [ ] **T5.3** — `query_geometry`/selectors/verifier adaptados a superfície.
- [ ] **T5.4** — Testes verdes; `adapter-gaps-roadmap.md` atualizado; documentação dupla (Docusaurus + SDD).
- [ ] **Gate do dono** — carenagem Nível 2 aprovada no Fusion real.
