# Micro-plano — Frente F3: Mecanismos funcionais

**Frente**: F3 | **Spec**: [`../spec.md`](../spec.md) | **Macro**: [`../plan.md`](../plan.md) › Frentes de capacidade | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de F1** (estado rico: tokens de face/aresta, `radius_mm`) **e F2**
> (planejamento hierárquico). Realiza **P1** (peças mecânicas funcionais). Os 3
> exemplos do dono viram os **gates oficiais**. Replan 2026-05-29.

## Objetivo

Dar ao módulo as capacidades de **mecânica real** que faltavam: rosca de
verdade, juntas (cinemática), componentes/montagem e **macros paramétricas de
alto nível** para os mecanismos recorrentes (dobradiça de nós, parafuso
métrico). É o que transforma "sólido bonito" em "peça que encaixa e abre".

## Decisões-chave

- **D1 — Tools low-level dedicadas, não script livre.** `thread`, `joint`,
  `make_component` expostas como tools allowlistadas (mutative, auto-exec no
  fluxo). Respeita a constituição (nada de shell/script livre no caminho feliz).
- **D2 — Rosca MODELADA, não cosmética.** `ThreadFeatures.createInput` +
  `isModeled=True` (a API expõe — confirmado no replan). Designação derivada do
  diâmetro via `ThreadDataQuery` quando o LLM não passar `designation`.
- **D3 — Macros compõem primitivas VALIDADAS.** `knuckle_hinge` e `metric_screw`
  não reimplementam geometria: chamam os handlers já aprovados (`_add_box`,
  `_add_cylinder`, `_combine_bodies`, `_thread`, `_joint`). Isso reduz o risco
  de "API blind" — cada tijolo já passou em gate. Eixo Z (orientação
  reparametrizável).
- **D4 — Geometria primeiro, cinemática por cima.** Se a junta falhar na API, a
  geometria do mecanismo continua válida (o erro é claro e o corpo fica no
  lugar). A dobradiça "abre" pela junta revolute, mas o conjunto físico
  (knuckles coaxiais + pino) já é montável manualmente.
- **D5 — Encaixe por medida real (F1), não por chute.** O nudge do planner
  instrui: meça o `radius_mm` do macho e dimensione a fêmea com clearance;
  rosqueie macho e fêmea com a MESMA `designation`.

## Tools entregues

| Tool | Tipo | O que faz |
|---|---|---|
| `fusion.thread` | mutative | Rosca modelada (externa/interna) numa face cilíndrica (token F1 ou selector). |
| `fusion.make_component` | mutative | Move um corpo para uma nova occurrence (base de montagem/junta). |
| `fusion.joint` | mutative | Junta revolute/rigid/slider/cylindrical entre corpos/componentes via `JointGeometry` de faces. |
| `fusion.knuckle_hinge` | additive (macro) | Dobradiça de nós que abre: 2 abas + coluna de knuckles alternados + pino (+ junta revolute opcional). |
| `fusion.metric_screw` | additive (macro) | Parafuso métrico: haste + cabeça + rosca modelada. |

Wiring idêntico ao padrão das demais: `FUSION_SCRIPT_TOOLS` + dispatch +
`tool_schemas` + `tool_registry`. Nudge de mecanismos no `planner._build_messages`.

## Validação

- **Mock (CI) — `tests/test_f3_mechanisms.py` (7 testes):** presença nas 5
  allowlists; categorias de risco; script Python válido com args realistas
  (braces do f-string); handlers + dispatch presentes; rosca usa
  `threadFeatures`/`createThreadInfo`/`isModeled`; junta expõe
  revolute/slider/rigid; macros compõem `_add_box`/`_add_cylinder`/`_combine`/
  `_thread`. **221 testes do subconjunto modeling verdes; 0 novos erros de lint.**
- **Gate (Fusion real) — os 3 oficiais (PENDENTE do dono):**
  1. **Dobradiça que abre** — `knuckle_hinge` com `joint='revolute'`: as duas
     abas giram coaxialmente em torno do pino.
  2. **Parafuso que encaixa** — `metric_screw` M6 + furo roscado `thread`
     `is_internal=true` M6 no sólido alvo: o parafuso entra na rosca.
  3. **Suporte de monitor paramétrico** — composto via F2 (placas + furos
     paramétricos, DT-002) + junta de articulação.

## Riscos / trade-offs

- **API blind**: `thread`/`joint` foram escritos contra a API documentada sem
  Fusion à mão (defensivos com try/except + erro claro). O gate do dono é quem
  confirma a geometria. Mitigação: macros reusam primitivas já validadas.
- **Orientação Z dos macros**: a dobradiça nasce com o pino vertical (Z) para
  compor com cilindros Z-axis; é reparametrizável/rotacionável depois. Follow-up:
  orientação livre via plano de construção.
- **Folga física dos knuckles**: hoje pino e knuckles são coaxiais (a junta dá o
  movimento); para impressão 3D com folga real, furar os knuckles com clearance
  é follow-up sob demanda.

## Definição de pronto (F3)

- [x] `thread` (modelada), `make_component`, `joint` (revolute/rigid/slider/cyl).
- [x] Macros `knuckle_hinge` e `metric_screw` compondo primitivas validadas.
- [x] Schemas + registry + dispatch + nudge do planner.
- [x] Testes mock (`test_f3_mechanisms.py`) + subconjunto modeling verde.
- [ ] **Gates oficiais no Fusion real (dono)**: dobradiça abre · parafuso encaixa · suporte paramétrico.
- [ ] _Follow-up sob demanda_: orientação livre dos macros; clearance físico dos knuckles; `snap_fit`; junta por token F1 explícito nos macros.
