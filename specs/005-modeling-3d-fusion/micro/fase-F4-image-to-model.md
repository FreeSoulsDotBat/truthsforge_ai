# Micro-plano — Frente F4: Image-to-model

**Frente**: F4 | **Spec**: [`../spec.md`](../spec.md) | **Macro**: [`../plan.md`](../plan.md) › Frentes de capacidade | **Índice**: [`../tasks.md`](../tasks.md)

> Realiza **P3** (analisar imagem → modelo fiel). Reusa F2 (planejamento) para
> transformar o entendimento em plano. Replan 2026-05-29.

## Objetivo

Tirar a visão computacional do **stub**: o `attachment_analyzer._call_vision`
devolvia sempre `None` (gateway text-only). Agora a imagem de referência é
enviada de verdade ao LLM multimodal, que devolve uma **descrição estruturada
de CAD** (forma em primitivas, proporções, features mecânicas, esboço de
plano). Essa descrição aterra o planner — o caminho `analyze → to_context_text
→ contexto do agente` já existia e passa a carregar conteúdo real.

## Estado atual (gargalo) → entregue

- `gateway`/`providers`: contrato `messages: list[dict[str, str]]` (text-only).
  → **Widened** para `list[dict[str, Any]]`: `content` aceita `str` OU lista de
  blocos. Os providers já repassam `message["content"]` verbatim para a API
  (OpenAI Responses `input` e Anthropic `messages`), então **nenhuma mudança de
  comportamento** foi necessária — só o builder de blocos certo por provedor.
- `_call_vision`: stub `return None`. → **Real**: resolve modelo vision, monta
  mensagem multimodal, coleta a descrição via `stream_chat`, best-effort.

## Decisões-chave

- **D1 — Pass-through nos providers.** Como OpenAI/Anthropic copiam o `content`
  cru para o payload, basta o caller montar o bloco no formato do provedor. Sem
  tocar na lógica dos providers (menor risco para o chat não-modelagem).
- **D2 — Builder por provedor isolado** (`llm_gateway/multimodal.py`): Anthropic
  (`image`/`source.base64`) e OpenAI (`input_image`/data-URL). Google fica no
  caminho **text-only** (serializa `parts` diferente) — sem quebrar.
- **D3 — Vision-description-as-text primeiro.** A descrição estruturada flui
  pelo caminho de contexto JÁ existente (`AttachmentAnalysis.summary` →
  `to_context_text`). Threading do bloco de imagem cru direto no
  `generate_structured` do planner é **F4.2** (follow-up) — a descrição textual
  é provider-agnóstica e robusta, e destrava o end-to-end agora.
- **D4 — Best-effort, nunca quebra o chat.** Sem modelo vision habilitado, rede
  ou timeout → `None` → resumo metadata-only. `_run_coro` executa a corrotina em
  qualquer contexto (sync da rota ou async do orchestrator, via thread).

## Entregue

| Item | Onde |
|---|---|
| Builders multimodais por provedor | `app/llm_gateway/multimodal.py` (novo) |
| Contrato do gateway widened (compat) | `app/llm_gateway/gateway.py` |
| `_call_vision` real + `_resolve_vision_model` + `_collect_vision` + `_run_coro` | `app/modeling/attachment_analyzer.py` |
| Prompt de análise CAD (PT-BR, estruturado) | `_VISION_SYSTEM` / `_VISION_PROMPT` |
| Param `vision_model` opcional no analyzer | construtor |

## Validação

- **Mock (CI) — `tests/test_f4_vision.py` (14 testes):** builders por provedor
  (anthropic/openai shapes; text-only sem imagem e para google); `_call_vision`
  manda bloco de imagem e devolve a descrição; `analyze()` usa o resumo vision;
  sem modelo → `None` (nada enviado); erro do provider é engolido →`None`;
  `vision_model` explícito tem precedência. **99 testes dos consumidores
  (analyzer/endpoint/orchestrator/planner) verdes; lint limpo.**
- **Gate (Fusion+LLM real) — PENDENTE do dono:** subir uma foto de uma peça e
  pedir "modele isso" → o agente descreve a peça pela imagem (não pelo nome do
  arquivo) e gera um sólido coerente com a referência.

## Riscos / trade-offs

- **Formato OpenAI Responses** (`input_image`/`input_text`) assumido pela doc; o
  caminho Anthropic é o default do repo e o mais exercitado. Gate confirma.
- **Descrição-como-texto** perde detalhe fino vs. o planner ver o pixel. F4.2
  (bloco de imagem no `generate_structured`) cobre isso quando necessário.
- **Custo/latência**: chamada vision extra por imagem; protegida por timeout
  (≥60s) e size limit (50 MB) já existentes.

## Definição de pronto (F4)

- [x] Gateway multimodal backward-compatible + builders por provedor.
- [x] `_call_vision` real (resolve modelo, monta imagem, coleta descrição).
- [x] Fallback metadata-only sem modelo/erro; chat nunca quebra.
- [x] Testes mock (`test_f4_vision.py`) + consumidores verdes.
- [ ] **Gate do dono (foto → peça fiel) no Fusion+LLM real.**
- [ ] _Follow-up F4.2_: bloco de imagem direto no planner (`generate_structured`); suporte multimodal ao Google; múltiplas imagens por pedido.
