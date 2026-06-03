# Micro-plano — Frente F5: Edição robusta com contexto

**Frente**: F5 | **Spec**: [`../spec.md`](../spec.md) | **Macro**: [`../plan.md`](../plan.md) › Frentes de capacidade | **Índice**: [`../tasks.md`](../tasks.md)

> **Evolui a Fase 3** (edição manual) **sobre F1** (ModelState). Realiza **P4**
> (editar peça pronta com contexto prévio). Replan 2026-05-29.

## Objetivo

Antes da F5, a reconciliação pré-edição (`_build_reconciliation_block`) lia só a
**timeline** do Fusion (features + parâmetros, texto). A geometria rica de F1
(tokens estáveis de face/aresta, raios, topologia) era persistida no plano, mas
**não era relida ao vivo** na hora de editar — então uma mudança manual do
usuário no Fusion deixava o planner editando contra um snapshot velho.

F5 fecha esse gap: antes de planejar a edição, lê também a **geometria AO VIVO**
(`fusion.query_geometry`), parseia num `ModelState` (F1) e injeta esse bloco
estruturado no contexto do planner — a edição parte do modelo **atual e real**.

## Decisões-chave

- **D1 — Reusar o padrão de probe da Fase 3.** `_read_live_geometry` espelha
  `_read_live_timeline`: roda UMA vez, fora dos steps, best-effort; falha nunca
  bloqueia a edição. Reusa `executor._execute_single_step` (seam único).
- **D2 — Reusar o parser/render de F1.** `model_state_from_query_output` +
  `render_model_state_block` (já testados) produzem o bloco `<model-state>` ao
  vivo. F5 não reescreve a camada de estado — compõe sobre ela.
- **D3 — Anexar, não substituir.** `_build_live_state_block` concatena o
  ModelState ao vivo à reconciliação textual da timeline (as duas visões somam:
  timeline = histórico de features; ModelState = geometria atual com tokens).
- **D4 — Flag default OFF.** `modeling_live_geometry_reconciliation_enabled` é um
  probe extra (custo/latência) e preserva o caminho da Fase 3 já homologado até
  o gate do dono. Liga junto com o loop/hierárquico nas homologações.

## Entregue

| Item | Onde |
|---|---|
| Flag `modeling_live_geometry_reconciliation_enabled` (default OFF) | `app/core/config.py` |
| `_read_live_geometry` (probe `query_geometry` best-effort) | `chat_orchestrator.py` |
| `_build_live_state_block` (timeline + ModelState ao vivo) | `chat_orchestrator.py` |
| Wiring em `propose_edit_plan` (atrás da flag) | `chat_orchestrator.py` |

> Nota: a injeção do ModelState **persistido** no contexto de edição já vinha de
> F1 (`build_edit_context_block`/`render_model_state_block`). F5 acrescenta a
> leitura **ao vivo** na reconciliação — o complemento que faltava para captar
> drift manual.

## Validação

- **Mock (CI) — `tests/test_f5_live_reconciliation.py` (8 testes):**
  `_build_live_state_block` anexa o `<model-state>` ao vivo (com tokens/raios
  reais) à reconciliação; passa intacto sem geometria / quando não parseia; usa
  só a geometria quando não há reconciliação. `_read_live_geometry` roda o probe
  `query_geometry`, devolve `None` em falha/exceção e pula software não-fusion.
  **71 testes (orchestrator/agent_loop/model_state) verdes; lint limpo.**
- **Gate (Fusion real) — PENDENTE do dono:** abrir um modelo, **mexer à mão no
  Fusion** (ex.: mudar um raio), pedir uma edição por chat e confirmar que o
  planner parte da geometria ATUAL (token/raio reais no contexto), não do
  snapshot do último plano.

## Riscos / trade-offs

- **Probe extra** por edição (latência/tokens): mitigado pela flag default OFF e
  best-effort (nunca bloqueia).
- **Volume de contexto**: o bloco ModelState é top-N faces/arestas salientes (já
  limitado em F1), evitando estourar o prompt.
- **Reconciliação estruturada profunda** (diff explícito snapshot↔ao vivo, em vez
  de só anexar os dois) fica como follow-up — hoje o LLM concilia vendo ambos.

## Definição de pronto (F5)

- [x] Leitura da geometria ao vivo + injeção de ModelState atual na edição.
- [x] Flag default OFF preserva o caminho da Fase 3 homologado.
- [x] Best-effort: probe que falha nunca bloqueia a edição.
- [x] Testes mock (`test_f5_live_reconciliation.py`) + consumidores verdes.
- [ ] **Gate do dono (editar após mudança manual) no Fusion real.**
- [ ] _Follow-up_: diff estruturado snapshot↔ao vivo; sinalizar drift explícito ao usuário no card.
