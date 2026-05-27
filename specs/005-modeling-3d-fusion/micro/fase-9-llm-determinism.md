# Micro-plano — Fase 9: Determinismo da interpretação do LLM

**Fase**: 9 | **Spec**: [`../spec.md`](../spec.md) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 8 fechada (cobertura "todo o Design" estável). Frente nasceu do gate da Fase 4 (Cenário A), onde se confirmou que o nudge é a camada mais fraca contra variabilidade do planner. O detalhe abaixo é um **stub** — o micro-plano é reescrito just-in-time antes de iniciar a fase. Mantido aqui para preservar cross-links e a decisão de roadmap.

## Objetivo

Reduzir a variabilidade do planner contra o adapter Fusion por **defesa em camadas determinísticas**, na ordem de robustez × custo. Eliminar a dependência da boa vontade do modelo (nudges em system prompt) substituindo por contratos forçados, normalização determinística e re-prompts dirigidos por erro real.

## Motivação (evidência observada)

Durante a Fase 4 (Cenário A — placa parametrizada com 4 furos):
- Nudges no system prompt (NOMES DE CORPO, PARAMETRIZAÇÃO, PADRÕES SIMÉTRICOS, anti `face:`/`bounding_box`/`target_face`) **reduziram** a frequência de drifts mas **não eliminaram**. LLM ignorou nudge explícito em 1/4 dos furos do gate.
- Mesmo prompt produziu planos diferentes entre execuções.
- Handlers absorveram parte (sanitize implícito de `target_face`, aliases de campos), mas o caminho deveria ser explícito e mensurável.

Bug J' (registrado no replan da Fase 4) é o gatilho desta fase.

## Camadas (ordem de aplicação)

### 9.1 — Structured Outputs / function calling estritos

Declarar JSON Schema das tools allowlistadas no `tool_registry` e usar o modo de saída estruturada do provedor (Anthropic tool use / OpenAI structured outputs) pra que o LLM **fisicamente não consiga** emitir campo fora do schema. Cobre ~80% dos drifts conhecidos:
- `target_face`, `face:"Body.top_face"`, `bounding_box.max_x`.
- Variantes de nome (`axis_line` vs `axis`, `value_mm` vs `expression`, `dimensions_mm` vs `width_mm/depth_mm/height_mm`).
- Tipos errados (string em campo numérico, lista em campo escalar).

Pré-requisito: `tool_schemas.py` (já absorvido na Fase 2) precisa virar fonte de verdade do schema enviado ao provedor.

### 9.2 — Sanitizer determinístico pós-LLM

Camada entre planner e executor (`backend/app/modeling/plan_sanitizer.py`, a criar):
- **Strip de campos não-allowlistados** com `logger.warning` (telemetria via `ModelingTracer`).
- **Normalização de aliases** centralizada (deixa de espalhar `_normalize_*` por handler).
- **Detector de padrão simétrico**: N instâncias de uma feature com posições; se a fórmula não for espelho perfeito da primeira (mesmas magnitudes, só sinais), normalizar pra mirror — com log de warning pra revisão humana.
- **Inferência de unidade de expressão**: generaliza o Fix C (`_infer_unit_from_expr`) pra todas as tools dimensionais.

Compatível com 9.1: o sanitizer corrige o que o schema deixou passar (LLM ainda pode emitir lista assimétrica de fórmulas mesmo com schema válido).

### 9.3 — Retry agêntico com guidance específica

Reuso do `agent_loop.py` + `build_correction_context` (Fase 2). Quando um step falha em runtime:
- Em vez de só logar e mostrar erro no card, **realimentar o LLM** com:
  - O erro do executor (e.g. `EXTRUDE_CREATION_FAIL_ERROR: No target body found`).
  - O step problemático (apenas o step, não o plano inteiro).
  - O campo suspeito (se identificável por padrão).
  - A correção esperada (ex.: "remova `target_face`; usar apenas `body_ref`").
- Teto de retries por step (já existe — 5) e por plano.

### 9.4 — Verifier LLM opcional (atrás de flag)

Para planos críticos (> N steps configurável), um segundo prompt revisa o plano contra checklist: simetria, parametrização, campos válidos, fórmulas espelhadas. Caro em latência+tokens → opt-in via `MODELING_PLAN_VERIFIER_ENABLED`.

### 9.5 — Templates / few-shots por padrão frequente

Pós-telemetria: identificar padrões recorrentes (ex.: "placa com N furos", "caixa com tampa", "flange com parafusos") e oferecer macro template parametrizado. LLM preenche slots, não inventa estrutura. Tradeoff: reduz criatividade pra casos novos → manter como **opt-in pelo planner**, não default.

## ADR-020 — Structured Outputs + sanitizer + retry agêntico (a rascunhar)

A fase deve nascer com um ADR-020 cobrindo:
- Decisão de adotar Structured Outputs como contrato (vs JSON livre + parser tolerante).
- Sanitizer como camada arquitetural (vs continuar normalizando dentro de cada handler).
- Política de retries com guidance (limites, observabilidade, custo).

## Tarefas atômicas (esboço, detalhe just-in-time)

- **T9.0** — ADR-020 rascunhado + aprovado pelo dono.
- **T9.1** — Structured Outputs ligados a partir de `tool_schemas.py`; testes de contrato (LLM mock) garantem que campo fantasma é rejeitado na origem.
- **T9.2** — Sanitizer determinístico + telemetria; cobertura por unit tests dos drifts conhecidos do replan v3/v4.
- **T9.3** — Retry agêntico com guidance no fluxo de pós-execução (reuso `agent_loop.py`).
- **T9.4** — Verifier LLM atrás de flag, com gate de custo (estimativa de tokens por plano).
- **T9.5** — Templates pra 1–2 padrões frequentes confirmados por telemetria.

## Telemetria de sucesso

Medir, com a observabilidade da Fase 2, antes vs depois:
- Taxa de campos-fantasma por plano.
- Taxa de planos com fórmula assimétrica em padrão simétrico.
- Retries por step.
- % de gates que reproduzem com `repeat run` o mesmo resultado (estabilidade).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest` (cobertura nova do sanitizer + structured outputs mock).
- **Gate do dono (Fusion real)**: rodar os Cenários A/B/C da Fase 4 em sequência, **sem qualquer ajuste manual de prompt entre execuções**, e validar:
  - Cenário A fecha (4 furos) sem intervenção em 2 de 2 execuções.
  - Cenário B fecha (revolve + edição paramétrica) em 2 de 2.
  - Cenário C fecha (move_body rotação) em 2 de 2.
- Redução mensurável das métricas de telemetria.

## Riscos

- **Custo extra de tokens** com Structured Outputs e Verifier opcional. Mitigação: medir e ajustar; Verifier atrás de flag.
- **Schema enviado divergir do contrato real do adapter** (regressão de manutenção dupla). Mitigação: `tool_schemas.py` como fonte única, gerar schema a partir do registry no boot.
- **Sanitizer "corrigindo demais"** e mascarando bugs reais do planner. Mitigação: todo strip/normalização vira evento de trace (visível no modal de diagnóstico).

## Definição de pronto (Fase 9)

- [ ] ADR-020 aprovado.
- [ ] Structured Outputs no provedor primário (com fallback gracioso para provedores sem suporte).
- [ ] Sanitizer determinístico em produção, com telemetria.
- [ ] Retry com guidance ligado e validado em pelo menos 1 cenário real.
- [ ] Gate do dono aprovado nos 3 cenários da Fase 4 sem ajuste manual.
- [ ] Documentação dupla (Docusaurus + SDD) atualizada com o novo contrato.
- [ ] Unit tests cobrindo os drifts conhecidos do replan.
