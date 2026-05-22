# Spec — Redesenho do processo de criação 3D (discovery → aprovação → edição)

> **Status:** PROPOSTA, aguardando OK do dono do produto para implementar.
> **Autor:** Claude Code, 2026-05-20.
> **Origem:** pedido do dono do produto após a placa parametrizada funcionar.
> Três dores: (1) o agente não pergunta detalhes antes de planejar; (2) o
> plano executa sem autorização; (3) edições quebram o modelo / criam doc novo.

## 1. Diagnóstico (por que as dores existem)

**Quase toda a arquitetura chat-first já existe e está sendo ignorada:**

- `app/modeling/chat_state.py` — state machine completa
  `discovery → planning → approved → executing → editing` com loop de
  clarificação e gate de aprovação.
- `app/modeling/chat_orchestrator.py` — `ask_clarification`, `propose_plan`
  (cria mas **não** executa), `approve_plan` (só aí executa), `reject_plan`
  (com motivo → discovery), `propose_edit_plan`/`approve_edit_plan`/
  `reject_edit_plan`.
- Endpoints `POST /plans/{id}/approve` e `/execute`; cards de aprovação no
  front (`useModelingPlanActions`).

**A causa raiz:** a rota de chat (`app/api/routes/chat.py`, gerador
`modeling_events`, ~L1420) **não usa o orquestrador**. Ela chama
`modeling_service.create_plan_async` e, como o modo default é `safe_auto`
(`contracts.py` L510), executa imediatamente. Curto-circuita discovery,
aprovação e a lógica de edição.

**Item 3 também tem causa no adapter:** toda execução roda `open_design`
criando um documento `Untitled` novo (visível nos traces) — logo, mesmo uma
edição começa do zero.

**Editar o plano** (passo a passo ou inteiro) antes de aprovar **não existe**
em lugar nenhum (nem backend nem front).

## 2. Decisões do dono do produto (2026-05-20)

1. **Aprovação:** plano primário **sempre** pede aprovação; edições **também
   sempre**, EXCETO se um **"modo fluido"** (toggle por chat) estiver ligado —
   nesse caso edições aditivas auto-executam. Ações destrutivas/high-risk
   pedem aprovação **sempre**, independente do toggle.
2. **Discovery:** perguntar **só quando houver ambiguidade real** (limiar de
   confiança). Se o pedido está claro, propõe o plano direto; se falta info
   (dimensões, material, encaixe, uso, tolerância), pergunta até ter ~certeza.
3. **Edição vs modelo novo:** assumir **edição do modelo atual por default**;
   um classificador de intenção detecta pedido "do zero"; se a frase der
   margem a dúvida, **pergunta** antes de agir. Inclui corrigir `open_design`
   para não apagar o modelo existente.

> Isso **revisa a ADR-013** ("adições normais podem autoexecutar no fluxo
> fluido"): o fluxo fluido passa a ser **opt-in** por chat, não o default.
> Registrar nova ADR ou aditar a 013.

## 3. Arquitetura alvo

Cada mensagem do usuário num chat 3D passa a fluir assim:

```
mensagem do usuário
   │
   ▼
[Discovery Agent]  (LLM: classifica intenção + confiança)
   │
   ├─ ambíguo / falta info ──────────────► ask_clarification  (pergunta, fica em discovery)
   │
   ├─ pedido "modelo novo" claro ────────► propose_plan (kind=primary)
   │
   └─ follow-up = edição do modelo atual ► propose_edit_plan (kind=edit)
   │
   ▼
[Card no chat]  plano proposto, STOP — não executa
   │
   ├─ Aprovar ───► approve_plan/approve_edit_plan ─► execute ─► editing
   ├─ Rejeitar (com motivo + sugestão) ─► reject ─► discovery
   │     └─ sem sugestão ► agente pergunta "como melhorar?"
   └─ Editar (passo ou plano todo) ─► PATCH plano ─► novo card
```

Exceção do **modo fluido** ligado: edições **aditivas** (categorias
`additive`/`mutative` não high-risk) pulam o card e auto-executam; high-risk
e destrutivas continuam parando no card.

## 4. Componentes (construir / ligar)

### 4.1 Discovery Agent (novo) — atende dor #1 e parte da #3
- Módulo `app/modeling/discovery_agent.py` (ou estende o planner).
- Entrada: histórico do chat + última mensagem + estado (`modeling_stage`,
  se já há `modeling_plan_id`/modelo).
- Saída estruturada (JSON): `intent` ∈ {`new_model`, `edit`, `ambiguous`},
  `confidence` (0–1), `questions` (lista, se precisa clarificar),
  `rationale`. 
- Usa `prompts/discovery_system.md` (já existe; falta few-shot p/
  propose_plan e p/ a classificação edit-vs-new).
- Limiar de confiança configurável; abaixo dele → `ask_clarification`.

### 4.2 Rewire da rota de chat — atende dor #2 (núcleo)
- `modeling_events` deixa de chamar `modeling_service` direto e passa a
  chamar o `ModelingChatOrchestrator`.
- `propose_plan`/`propose_edit_plan` emitem o card e **param** (sem execute).
- Aprovação/execução vêm dos endpoints existentes acionados pelo card.
- Default de modo: deixa de ser `safe_auto`. Novo default = exige aprovação.

### 4.3 Política de aprovação + modo fluido
- Novo campo em `ChatSession`: `modeling_fluid_mode: bool = False`.
- Toggle no `EnableModeling3DDialog` / header do chat.
- Regra: primário sempre card; edição → card, salvo `fluid_mode and not
  high_risk`. High-risk/destrutivo sempre card.

### 4.4 Edição vs novo + fix do `open_design` — atende dor #3
- Intenção vem do Discovery Agent (4.1).
- `open_design`: reusar o design ativo quando a intenção é `edit`; só criar
  documento novo quando `new_model`. Hoje ele sempre cria `Untitled`.
- Editar um modelo existente nunca deve recriar o documento nem zerar bodies.

### 4.5 Edição de plano (passo / todo) — atende "editar livremente"
- Endpoint novo `PATCH /plans/{id}` (só enquanto `status=proposed`/pré-aprovação)
  para substituir a lista de steps ou um step específico.
- UI no card: editar argumentos de um passo, reordenar, remover, ou reescrever
  o plano; re-renderiza o card; aprovação age sobre o plano editado.

## 5. Fases (cada uma é um PR, ordenadas por impacto/risco)

- **P1 — Gate de aprovação (rewire da rota → orquestrador).** Maior ganho
  imediato p/ a dor #2 e menor risco (a maquinaria existe). Inclui default
  de modo + campo `fluid_mode`. **Sem** discovery ainda (propõe direto).
- **P2 — Discovery Agent** (intenção + perguntas com limiar). Dor #1.
- **P3 — Edição vs novo + fix `open_design`.** Dor #3. Precisa de teste em
  Fusion real (comportamento de documento/design ativo).
- **P4 — Edição de plano** (PATCH + UI de editar passo/plano). "Editar
  livremente".

## 6. Contratos novos / alterados

- `ChatSession.modeling_fluid_mode: bool` (default False).
- Default de `ModelingExecutionMode` no fluxo de chat: deixa de auto-executar.
- Saída estruturada do Discovery Agent (schema acima).
- `PATCH /api/3d/plans/{id}` (edição pré-aprovação).
- `prompts/discovery_system.md`: few-shot para clarificar, propor e
  classificar edit-vs-new.

## 7. Testes

- Unit: discovery agent (intenção/confiança/perguntas) com casos claros e
  ambíguos; política de aprovação (primário/edição/high-risk/fluid).
- Orquestrador: rota emite card e **não** executa sem aprovação (regressão da
  dor #2).
- Adapter: `open_design` reusa design em edição (compile + contrato; geometria
  real validada no Fusion).
- PATCH plano: edição de passo/plano antes da aprovação.

## 8. Riscos e trade-offs

- **Revisa a ADR-013** (fluxo fluido vira opt-in) — precisa de ADR.
- P3 mexe em comportamento de documento do Fusion (alto risco sem Fusion
  real; validar com o dono).
- Mais cliques no fluxo padrão (aprovação sempre) — mitigado pelo modo fluido.
- O Discovery Agent adiciona uma chamada LLM por turno (latência/custo);
  mitigar com limiar e prompt enxuto.

## 9. Decisão registrada

- [x] Aprovar a spec e começar pela **P1**. ✅ (2026-05-20)
- [ ] Ajustar escopo/fases.

## 10. Status de implementação

### P1 — Gate de aprovação ✅ ENTREGUE (2026-05-20, branch `feat/modeling-3d-approval-gate`)

- A rota `app/api/routes/chat.py` (`modeling_events`) **deixou de
  auto-executar**. Agora cria o plano e força `status=waiting_approval`,
  emite o card e PARA. A execução só ocorre via `POST /plans/{id}/approve` +
  `/execute`, acionados pelo card (`useModelingPlanActions`, já existente).
- Sessão vai para o estágio `planning` (helper `_sync_modeling_plan_proposed`),
  não mais `editing`.
- Mensagem do chat e runtime status atualizados para "aguardando aprovação".
- Removido código morto (`_sync_modeling_plan_session`, import `asyncio`).
- Teste: `test_chat_stream_proposes_plan_without_executing` em
  `tests/test_modeling_routes.py` (propõe, não executa, sessão em `planning`,
  plano persistido `waiting_approval`).
- **Escopo deixado para fases seguintes:** discovery/perguntas (P2),
  edição-vs-novo + fix `open_design` + **modo fluido** (P3, onde o toggle
  ganha comportamento), edição de plano (P4). Em P1 **todo** plano para —
  inclusive follow-ups — o que é o default seguro acordado.
- **Revisão da ADR-013:** o "fluxo fluido" (auto-executar adições) deixou de
  ser o default; vira opt-in por chat na P3. Formalizar ADR junto da P3.

### P2 — Discovery Agent ✅ ENTREGUE (2026-05-20, mesma branch)

- Novo módulo `app/modeling/discovery.py`: avaliação via LLM (Structured
  Outputs, `DISCOVERY_SCHEMA`) que decide `ready_to_plan` + `confidence` +
  `questions` + `refined_brief`. **Pergunta só quando ambíguo:** só prossegue
  se o LLM marcar ready, a confiança bater o limiar E não houver perguntas;
  qualquer pergunta força o loop de descoberta. Fallback `heuristic_assessment`
  nunca bloqueia (ready=true) quando não há modelo.
- `ModelingPlannerService.assess_request_async` reusa resolução de modelo +
  gateway + tracer (eventos `discovery.assess` span e `discovery.assessed`).
  Exposto na fachada `ModelingService.assess_request_async`.
- Rota `chat.py:modeling_events`: antes de planejar, roda discovery (pula em
  `editing` e quando a flag está off). Se não-pronto, emite as perguntas como
  mensagem do assistente, mantém o chat em `discovery`, audita
  `modeling.chat.clarification_asked` e PARA (sem criar plano). Se pronto, usa
  `refined_brief` como prompt do planner. Quando o usuário responde, o próximo
  turno re-roda discovery com o histórico acumulado.
- Flags novas: `TRUTHS_FORGE_MODELING_DISCOVERY_ENABLED` (default true) e
  `TRUTHS_FORGE_MODELING_DISCOVERY_THRESHOLD` (default 0.7).
- Testes: `tests/test_modeling_discovery.py` (limiar/perguntas/heurístico) e
  `test_chat_stream_asks_clarification_when_ambiguous` (rota pergunta e não
  cria plano; sessão fica em `discovery`).
- **Pendente:** UI dedicada para as perguntas é opcional (hoje vão como
  mensagem normal do assistente, que o chat já renderiza). P3/P4 seguem.

### P3 — Edição vs novo + fix open_design + modo fluido ✅ ENTREGUE (2026-05-20)

**P3a (fundação, branch `feat/modeling-3d-approval-gate`):**
- `open_design` (adapter) agora REUSA o design ativo por padrão; só cria
  documento novo sem design ativo OU com `new_document`/`reset`/`force_new`.
  Corrige "edição quebra/recria o modelo".
- `/plans/{id}/execute` avança o chat 3D para `editing` após execução
  concluída (helper `_advance_chat_to_editing_after_execute`), para que
  follow-ups sejam edições.
- `ChatSession.modeling_fluid_mode` + `ChatModeling3DContext.fluid_mode`.

**P3b (fluxo):**
- Discovery agent ganhou `intent` (edit/new_model/ambiguous) no schema +
  prompt; só significativo quando já há modelo. `assess_request_async` recebe
  `has_existing_model`. Default seguro: com modelo → `edit`; sem → `new_model`.
- Rota `chat.py`: roda discovery também em `editing`. Se `intent=ambiguous`,
  PERGUNTA "edição ou novo?" e para. `intent=edit` → plano `kind=edit`
  (parent = plano atual). `intent=new_model` (com modelo) → força documento
  limpo (`_force_plan_new_document` marca o open_design com `new_document`).
- **Modo fluido:** com `modeling_fluid_mode` ligado, edição aditiva SEM
  high-risk auto-executa (pula o card); plano primário e high-risk/destrutivo
  SEMPRE param. Default OFF.
- Testes: intents em `test_modeling_discovery.py`; rota em
  `test_modeling_routes.py` (edit propõe e para; ambíguo pergunta; fluido
  auto-executa; execute→editing; open_design compile).
- **Validação real pendente:** a QUALIDADE do delta de edição depende do
  planner ver o estado atual do modelo (query_geometry/G2.2) — iterar via
  fix-by-trace no Fusion real. open_design reuse precisa de validação no
  Fusion (comportamento de documento ativo).

### P4 — Editar o plano antes de aprovar ✅ ENTREGUE (2026-05-20)

- **Backend:** `PATCH /api/3d/plans/{id}` (`ModelingService.edit_plan`) edita um
  plano enquanto `draft`/`waiting_approval`. O cliente envia a lista COMPLETA
  de etapas (cobre editar um passo, reordenar, remover, adicionar). Valida
  cada `tool_name` contra a allowlist do planner (422 se fora), reordena
  `seq`, preserva a identidade da etapa quando o `id` é informado, re-aplica a
  policy de segurança e mantém o plano em `waiting_approval` (gate P1). 409 se
  o plano já foi aprovado/executado; 404 se não existe. Contratos
  `ModelingPlanEdit`/`ModelingPlanEditStep`. Audit `modeling.plan_edited`.
- **Frontend:** `modeling3dApi.editPlan` + `useModelingPlanActions.edit` +
  botão "Editar plano" no `ModelingPlanCard` com editor inline (título, tool,
  risco, argumentos JSON por etapa; mover ↑/↓, remover, adicionar; valida o
  JSON antes de salvar). Ligado via `app-chat` → `App.tsx`.
- Testes: backend (`test_edit_plan_*` — substitui, rejeita tool fora da
  allowlist, bloqueia após aprovação); frontend (`ModelingPlanCard.test.tsx` —
  edita passo e chama onEditPlan; bloqueia em JSON inválido). 70 testes web +
  contratos backend verdes; typecheck do front limpo.

### P5 — Planner de edição ciente do modelo atual ✅ ENTREGUE (2026-05-20)

Objetivo: melhorar a QUALIDADE do delta de edição (gap registrado na P3). O
backend não fala com o Fusion ao vivo na hora de planejar, então em vez de
chamar `query_geometry` síncrono usamos o que já temos persistido.

- `build_edit_context_block(parent_plan)` (planner.py) monta um bloco
  `<modelo-atual>` com: (a) o **histórico de construção** do plano-pai
  (etapas + args) e (b) **métricas dos corpos** extraídas das saídas das
  etapas executadas (`validate_dimensions`/`validate_printability`/
  `query_geometry` — chaves `bodies`/`metrics`). Instrui o LLM a gerar SÓ o
  delta, referenciar corpos/sketches por nome e NÃO recriar a base / abrir
  documento novo.
- `create_llm_plan(_async)` e `_build_messages` aceitam `edit_context`;
  `ModelingPlannerService._resolve_edit_context` busca o plano-pai
  (`parent_plan_id`) e injeta o bloco quando `kind=edit`. Span
  `planner.llm_request` marca `edit_context=true`.
- Testes: `test_build_edit_context_block_*` em `test_planner_llm.py`.
- **Limitação:** ainda é o estado CONHECIDO (do histórico/saídas), não uma
  leitura ao vivo do Fusion. Para edições sobre um modelo aberto manualmente
  pelo usuário (sem histórico no backend), o contexto fica vazio — evolução
  futura: persistir um snapshot de `query_geometry` após cada execução.

### Status geral: P1 ✅ · P2 ✅ · P3 ✅ · P4 ✅ · P5 ✅ — processo + edição cientes.
