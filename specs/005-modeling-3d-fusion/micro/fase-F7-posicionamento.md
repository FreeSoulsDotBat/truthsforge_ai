# Micro-plano — Frente F7: Posicionamento paramétrico (referência espacial declarativa)

**Frente**: F7 | **Spec**: [`../spec.md`](../spec.md) | **Macro**: [`../plan.md`](../plan.md) › Frentes de capacidade | **Índice**: [`../tasks.md`](../tasks.md) | **Débito**: [`../tech-debt-posicionamento.md`](../tech-debt-posicionamento.md) | **ADR**: ADR-022

> **Depende de F1** (estado rico/tokens) **e da fundação de montagem da F3** (joint/make_component — API-blind, gateada em P1). Realiza o mandato do débito de posicionamento. Aprovado pelo dono em 2026-06-03.

## Objetivo

Trocar o posicionamento por **coordenada absoluta chutada** pelo LLM por **referência espacial declarativa + montagem nativa paramétrica do Fusion**. O LLM declara placement **relativo à geometria real** (ancorar face A à face B, distribuir N nós ao longo da aresta, eixo coaxial ao furo); um **resolver determinístico no backend** lê a geometria via o probe `query_geometry` (F1) e emite **componentes + joints** que **sobrevivem a recompute**. A matemática de coordenada sai do LLM e vai p/ código determinístico (filosofia do sanitizer F6).

## Estado atual (gargalo)

Tudo é coordenada absoluta em mm; cada primitiva nasce na origem e o LLM calcula `origin_mm`/`center_mm`/`position_mm` na mão (gates: knuckles no lado errado, pino flutuando, tampa solta, corpos fora de lugar). O nudge **proíbe** refs naturais (`Placa.top_face`, `bbox.max_x`) porque nenhum handler as suporta. Diagnóstico completo em [`../tech-debt-posicionamento.md`](../tech-debt-posicionamento.md) §1–§2.

## Decisões-chave (ADR-022)

- **D1 — Paramétrico, não assado (escolha do dono).** Placement vira **joint/constraint nativo** do Fusion (sobrevive a recompute), não transform absoluto calculado uma vez. Mais robusto; mais complexo e API-blind → mitigado gateando a fundação (P1) primeiro.
- **D2 — Resolver no BACKEND (pré-pass), não in-script.** Tools Fusion são one-shot sem `adsk` vivo entre passos; o backend tem o probe `query_geometry` já validado (mesmo seam de `capture_model_state`/`capture_viewport_image`). Resolver sobre `ModelState` é 100% testável em mock (como `plan_sanitizer`); resolver in-script seria API-blind. `fusion.place_body` in-script fica como follow-up só se a latência do probe doer.
- **D3 — Modelo assembly-aware: combine-DENTRO, joint-ENTRE.** Componentes = partes imprimíveis. Os nós da caixa **combinam com a caixa** (1 sólido) DENTRO do componente; o movimento vem de um **joint ENTRE** os componentes (caixa↔tampa, revolute no eixo do pino). Reconcilia a tensão combine×joint que quebrou a dobradiça (o gate combinou ENTRE componentes — errado).
- **D4 — Aditivo + flag (`modeling_spatial_resolution_enabled`, default OFF).** Coordenada absoluta continua funcionando; step declarativo com flag OFF → erro claro (nunca mis-place silencioso). Sanitizer (F6) só é alargado p/ poupar `@`-refs válidas.

## Gramática de referência espacial

Referencia geometria por **token estável** (F1) ou **corpo + selector**, + ponto/eixo semântico. Forma objeto e `@`-string (faz as refs hoje-proibidas FUNCIONAREM):
```
{face:<token>, point:"center", axis:"normal"}
{edge:<token>, point:"along", fraction:0.2}   {edge:<token>, axis:"direction"}
{body:"X", point:"bbox.max_z"|"bbox.corner"|"center"}
@token('<face>').center.z   @edge('<edge>').along(0.2)   @body('Placa').bbox.max_z - 20
```
Aritmética por AST restrito (sem `eval`). Fora da gramática → `fusion.spatial_ref_unresolved` (nunca chuta; espelha `fusion.edge_token_stale`).

## Tools/campos novos (resolvidos no backend → componentes+joints concretos)

| Tool/campo | LLM declara | Resolver emite | Reusa |
|---|---|---|---|
| `fusion.place_body` | `{body, anchor, target, mate:"flush"\|"coaxial", offset_mm?, clearance_mm?}` | `make_component` + `joint` (rigid/planar/cylindrical) das JointGeometry resolvidas | `_joint`, `_joint_geo_from_ref`, `_make_component` |
| `fusion.distribute_along` | `{edge:<token>, count, prototype, spacing_mm?\|fit?, alternate?:[A,B]}` | pattern paramétrico OU N componentes jointados; alternância = 2 grupos | `_add_cylinder` batch, `_pattern_*`, `_joint` |
| `fusion.align_axis` | `{body, body_axis, target:<edge/face ref>}` | `revolute`/`cylindrical` joint c/ eixo da aresta/face | `_joint` |
| `@`-refs em `origin_mm`/`center_mm`/`position_mm`/`translation_mm`/`axis` | ref inline | resolvida pré-dispatch p/ número/eixo | `_eval_pair`/`_eval_param` |

## Tarefas (fases — ver [`plan.md`](../plan.md) macro)

- **P0** — este micro-plano + ADR-022 + rows em plan/tasks (sem código).
- **P1** — **GATE da fundação de montagem** (Fusion): `_make_component`+`_joint`+combine-dentro. Pré-requisito (API-blind F3).
- **P2** — enriquecer `_query_geometry` (aresta start/end/direction; corpo bbox_min/max) + campos em `model_state.py`/`contracts.py` + testes parser. Gate Fusion.
- **P3** — `spatial_ref.py` (gramática + resolver puro) + `@`-parse + sanitizer poupa `@`. Mock `test_spatial_ref.py`.
- **P4** — `spatial_resolver.py` (placement→joint/componente; `distribute_along` expande) + 3 tools no registry/schemas + stub. Mock `test_spatial_resolver.py`.
- **P5** — nudge reescrito + flag + wiring no `agent_loop`/executor (probe→resolve→dispatch) + `test_agent_loop`.
- **P6** — gates Fusion (place_body/distribute_along/align_axis + caixa+tampa knuckle que ABRE declarativa).

## Arquivos críticos

`spatial_ref.py` (NOVO, puro), `spatial_resolver.py` (NOVO), `fusion_mcp_scripts.py` (enriquecer `_query_geometry`; registrar 3 tools→stub; REUSA `_joint`/`_make_component`/`_combine_bodies`), `agent_loop.py` (resolver pré-dispatch atrás da flag), `planner.py` (nudge), menores: `model_state.py`/`contracts.py`/`tool_registry.py`/`tool_schemas.py`/`plan_sanitizer.py`/`config.py`.

## Validação

- **Mock (CI — o grosso):** `test_spatial_ref.py`, `test_spatial_resolver.py`, extensões de `test_model_state.py`/`test_f6_plan_sanitizer.py`/`test_agent_loop.py`, presença registry/schema. `quality.ps1` com flag OFF (regressão) e ON.
- **Gates Fusion (dono — única prova do API-blind):** P1 (montagem/joints), P2 (números do query_geometry), P6 (placement real + dobradiça que abre via loop visual). Recipe em [`../gate-homologacao.md`](../gate-homologacao.md) (novo "Gate F7").

## Definição de pronto (F7)

- [ ] P0 SDD + ADR-022.
- [ ] P1 fundação de montagem gateada no Fusion (combine-dentro/joint-entre).
- [ ] P2 `query_geometry` enriquecido + gateado.
- [ ] P3/P4/P5 resolver + tools + wiring, mock verdes; flag OFF = regressão.
- [ ] **P6 gate do dono:** caixa+tampa knuckle que ABRE, 100% declarativa/paramétrica, convergindo pelo loop visual.
- [ ] Docusaurus + SDD reconciliados; itens §3.1/§3.5 do débito marcados endereçados.
