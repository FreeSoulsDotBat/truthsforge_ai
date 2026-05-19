# handoff.md

> **Para a próxima IA/humano que pegar o trabalho:** leia esse arquivo
> inteiro **antes** de tocar código. As seções abaixo descrevem o que já
> está em produção, o que está em PR aberto, os gaps que ficaram
> explicitamente sem fazer, e como continuar a partir da Onda 6. As
> decisões consolidadas com o dono do produto seguem firmes —
> não reabrir sem aprovação.

## Estado atual

Refatoração v2 (chat-first integral + título obrigatório). **Onda 5
concluída localmente** na branch `codex/3d-chat-title-required`; falta
PR/merge.

| Onda                                                 | Status               | PR                   | Commits-chave                         |
| ---------------------------------------------------- | -------------------- | -------------------- | ------------------------------------- |
| 0 — Specs/docs/ADRs                                  | mergeado             | #19                  | `bf9395a`                             |
| 1 — Backend foundations                              | mergeado             | #19                  | `0546ff8` → `371eb0e`                 |
| 2 — Backend chat-first orchestration                 | mergeado             | #20                  | `f5269b7` → `c3cb10c`                 |
| 3 — Frontend feature module 3D                       | mergeado             | #21 + fixes #22, #24 | `a94a273`                             |
| 4 — Frontend cards + aprovação inline + auto-analyze | mergeado             | #25                  | `cf42144` → `424be99`                 |
| 5 — Título obrigatório do chat (frontend)            | concluída localmente | —                    | branch `codex/3d-chat-title-required` |
| 6 — QA / docs finais + wire orchestrator no stream   | iniciada (hotfix QA) | —                    | —                                     |

Verificação ao fim da Onda 4 (local, Windows):

- `pytest tests/ --ignore=tests/test_postgres_store.py` → **243 verdes**
- `pnpm test:unit` → **60 verdes** em 11 arquivos (16 novos)
- `pnpm typecheck` → limpo
- `alembic history` linear `001 → 002 → 003 → 004`

Verificação da Onda 5 (local, Windows):

- `backend\.venv\Scripts\python.exe -m ruff format --check backend\app\api\routes\chat.py backend\tests\test_chat_title_required.py` → limpo.
- `backend\.venv\Scripts\python.exe -m ruff check backend\app\api\routes\chat.py backend\tests\test_chat_title_required.py` → limpo.
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_chat_title_required.py -q` → **8 verdes**.
- `backend\.venv\Scripts\python.exe -m pytest backend\tests --ignore=backend\tests\test_postgres_store.py --ignore=backend\tests\test_alembic_migrations.py -q` → **239 verdes**.
- `pnpm --filter @truths-forge/web lint` → limpo.
- `pnpm --filter @truths-forge/web typecheck` → limpo.
- `pnpm --filter @truths-forge/web test:unit` → **68 verdes**.
- `pnpm --filter @truths-forge/web exec prettier --check <arquivos tocados>` → limpo.
- `pnpm --filter @truths-forge/docs build` → limpo com warning conhecido de `vscode-languageserver-types`.
- Smoke visual local em `http://127.0.0.1:5173` → modal abriu antes do envio, bloqueou título vazio, aceitou `Smoke título obrigatório` e o backend persistiu a sessão com mensagem sem `chat_title_required`.

Limitações: `pnpm --filter @truths-forge/web format:check` completo ainda
falha por 38 arquivos preexistentes fora do escopo. A suíte backend completa
sem ignores parou na coleta porque o venv atual não tem `alembic`.

---

## Hotfix QA Fusion após Onda 5

Sintoma reportado no Fusion real: com MCP Fusion configurado, qualquer prompt
caía no mesmo fallback retangular (`add_rectangle 40x20` + extrusão 12) e o
plano visual não variava. Causa confirmada em `backend/app/modeling/planner.py`:
`create_heuristic_plan` usava `_default_steps()` fixo para Fusion quando o planner
LLM estava indisponível ou falhava.

Correção aplicada na branch `codex/3d-chat-title-required` (e isolada no
PR companheiro `feat/planner-llm-wip`, PR #27):

- fallback Fusion agora deriva um perfil simples do prompt dentro da allowlist;
- pedidos retangulares/base/chapa/placa usam `fusion.add_rectangle` com dimensões
  extraídas de sequências tipo `80x40x12 mm`;
- pedidos circulares/cilíndricos/disco/pino/eixo/tubo usam `fusion.add_circle`
  e extrusão com `diâmetro`/`altura` quando informados;
- o sketch do fallback passou a enviar `plane_ref="xy"`, alinhado ao executor
  determinístico do Fusion MCP;
- `_normalize_prompt` faz NFKD + strip de diacríticos para unificar matching
  de "paramétrico"/"parametrico", "tolerância"/"tolerancia" etc.

### PR #27 review — dedup de hints após normalização

Reviewer apontou inflate de score em `choose_software`: como
`_normalize_prompt` colapsa acentos, manter ambas as formas ("paramétrico"
e "parametrico") em `FUSION_HINTS` fazia a mesma palavra do prompt contar
duas vezes. Correção aplicada (commit do PR #27):

- Removidas as variantes não-acentuadas redundantes de `FUSION_HINTS`
  (`parametrico`, `tolerancia`, `extrusao`, `peca`) e `BLENDER_HINTS`
  (`organico`). Mantida só a forma canônica com acento; o
  `_normalize_prompt(hint)` no scoring continua fazendo o trabalho.
- Adicionada asserção defensiva `_assert_hints_dedup_after_normalize`
  que roda no import e impede regressão futura silenciosa.
- Testes novos em `test_planner_llm.py`:
  - `test_choose_software_does_not_double_count_normalized_hints`
  - `test_hint_sets_have_no_normalized_collisions`
  - `test_blender_score_with_organic_prompt_is_correct`

Validação local:

- `backend\.venv\Scripts\python.exe -m ruff format --check backend\app\modeling\planner.py backend\tests\test_planner_llm.py` → limpo.
- `backend\.venv\Scripts\python.exe -m ruff check backend\app\modeling\planner.py backend\tests\test_planner_llm.py` → limpo.
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_planner_llm.py backend\tests\test_modeling_routes.py backend\tests\test_tool_registry.py -q` → **51 verdes** antes do fix do PR #27, **18 verdes** isolando só test_planner_llm.py após o fix (inclui 3 novos casos do dedup).

Limitação: `pnpm --filter @truths-forge/docs build` foi tentado após a atualização
da doc, mas falhou neste ambiente com `fetch failed`; validação completa da doc
build e smoke manual com Fusion conectado seguem pendentes na Onda 6.

---

## O que a Onda 5 entregou

**Arquivos novos:**

- `apps/web/src/features/chat/components/ChatTitleRequiredDialog.tsx`
- `apps/web/src/features/chat/components/ChatTitleRequiredDialog.test.tsx`
- `apps/web/src/features/chat/hooks/useChatTitleGate.ts`

**Arquivos alterados:**

- `apps/web/src/features/chat/chat-domain.ts` centraliza `DEFAULT_CHAT_TITLES`,
  normalização de título e `chatSessionNeedsTitle`.
- `apps/web/src/App.tsx` abre o modal antes de `streamChat`, atualiza o título
  local da sessão, envia `title` no payload e restaura o draft quando o backend
  devolve `chat_title_required`.
- `apps/web/src/lib/api.ts` transforma HTTP 422 JSON em `onError` com
  `reason: "chat_title_required"` e lança `ChatStreamHttpError` para o caller.
- `backend/app/api/routes/chat.py` persiste `payload.title` em rascunhos já
  criados como `Novo chat` antes do primeiro envio.
- `infra/docker-compose.dev.yml` e `infra/.env.example` ligam
  `TRUTHS_FORGE_REQUIRE_CHAT_TITLE=true`.

**Contrato de UI:**

- `ChatTitleRequiredDialog` usa `role="dialog"`, `aria-modal`, autofocus no
  input, ESC para cancelar e Enter para confirmar.
- Confirmar fica bloqueado para vazio/whitespace/`Novo chat`/`New chat` e
  durante `busy`.
- O modal não executa envio por texto livre; ele apenas resolve o título para
  o fluxo do `App.tsx`.

**Pendências imediatas:**

- Rodar o smoke manual da task 5.6.
- Registrar resultados de validação final nesta seção antes de PR/merge.

## O que a Onda 4 entregou (detalhe técnico)

### Sub-etapa 4.1+4.2 — Cards no chat (commit `cf42144`)

**Arquivos novos:**

- `apps/web/src/features/modeling-3d/components/ModelingPlanCard.tsx`
- `apps/web/src/features/modeling-3d/components/ModelingPlanCard.test.tsx` (12 testes)
- `apps/web/src/features/modeling-3d/components/ModelingEditCard.tsx`
- `apps/web/src/features/modeling-3d/components/ModelingEditCard.test.tsx` (4 testes)
- `apps/web/src/features/modeling-3d/hooks/useModelingPlanActions.ts`

**`ModelingPlanCard` — contrato:**

```ts
interface ModelingPlanCardProps {
  plan: ModelingPlan;
  onApprove?: (reason?: string) => Promise<void> | void;
  onReject?: (reason: string) => Promise<void> | void;
  onRetry?: () => Promise<void> | void; // só em status="failed"
  onRevise?: () => Promise<void> | void; // só em status="failed"
  isBusy?: boolean;
}
```

- Renderiza prosa (rationale → prompt fallback), badges (software/status
  localizado em pt-BR/planner_source/kind=edit), banner amarelo quando
  há etapa `risk_level="high"` ou `approval_required=true`, lista de
  etapas com pill colorida de risk_level.
- Botões "Aprovar"/"Rejeitar" aparecem **apenas em**
  `status ∈ {"waiting_approval", "draft"}`.
- Rejeição abre form expansível com motivo obrigatório (`min_length` no
  client, button "Confirmar rejeição" só habilita com texto).
- Estados visuais: `running` (spinner amarelo), `completed` (mensagem
  verde), `failed` (alerta vermelho + botões "Tentar novamente" / "Revisar
  plano"), `rejected` (nota neutra).
- Texto livre **não** dispara nada — reforçado em copy no rodapé.

**`ModelingEditCard` — contrato:**

```ts
interface ModelingEditCardProps {
  plan: ModelingPlan; // sempre kind="edit"
}
```

- Card compacto, sem botões. Renderiza header com ícone+badge "edição",
  resumo (rationale → prompt → fallback "Edição executada no modelo 3D"),
  contagem de etapas executadas e falhas.
- Quando um edit plan está em `waiting_approval` (high-risk reaberto),
  o caller renderiza `ModelingPlanCard` em vez deste.

**`useModelingPlanActions` — contrato:**

```ts
{
  busy: boolean;
  error: string | null;
  lastPlan: ModelingPlan | null;
  lastExecution: ModelingExecutionResult | null;
  approve(planId): Promise<ModelingExecutionResult | null>;
  reject(planId, reason): Promise<ModelingPlan | null>;
  retry(planId): Promise<ModelingExecutionResult | null>;
  revise(planId, reason?): Promise<ModelingPlan | null>;
  reset(): void;
}
```

- `approve` chama `modeling3dApi.approvePlan(id)` seguido de
  `modeling3dApi.executePlan(id)` em sequência. Mantém os dois retornos
  em `lastPlan` / `lastExecution`.
- `reject` e `revise` usam `modeling3dApi.rejectPlan(id, reason)`.
- Todas capturam exceção em `error` sem propagar.

### Sub-etapa 4 integration — wire no App.tsx (commit `ffb6f73`)

**Arquivo modificado:** `apps/web/src/App.tsx`

**`applyPlanToSession(plan, nextStage)`** — helper local que substitui
`metadata.modeling_plan` na mensagem correspondente da sessão e ajusta
`session.modeling_stage` / `session.modeling_plan_id`. Rejeição limpa
`modeling_plan_id` e volta para `discovery`.

**Handlers wire-up:**

- `handleApproveModelingPlan(planId)` → `hook.approve` → `applyPlanToSession(result.plan, "editing")`
- `handleRejectModelingPlan(planId, reason)` → `hook.reject` → `applyPlanToSession(rejected, "discovery")`
- `handleRetryModelingPlan(planId)` → `hook.retry` → `applyPlanToSession(execution.plan, "editing")`
- `handleReviseModelingPlan(planId)` → `hook.revise` → `applyPlanToSession(rejected, "discovery")`

**Prop `modelingPlanActions`** passada ao `MessageBubble` apenas quando
`activeSessionIsModeling3D=true`. Chats normais recebem `undefined` e
o card fica não-interativo (botões somem).

### Sub-etapa 4.3 — Auto-analyze de anexos (commit `92218dd`)

**Onde:** `apps/web/src/App.tsx`, dentro do `try{}` de envio do chat,
imediatamente após o stream completar e antes do `catch`.

**Trigger:** `modeling3dPayload.enabled && uploadedFileIds.length > 0`.

**Comportamento:**

1. `Promise.all` paralelo sobre `uploadedFileIds`.
2. Para cada, `modeling3dApi.analyzeAttachment(chatId, fileId)`.
3. Cada sucesso vira `ChatMessage` assistant local com:
   - `metadata.response_mode = "modeling_3d_attachment_analysis"`
   - `metadata.attachment_analysis = AttachmentAnalysis` completo
   - `content = analysis.context_text` (pronto para LLM ler)
4. Falhas viram nota assistant com `response_mode =
"modeling_3d_attachment_analysis_error"` e texto humano legível —
   nunca quebram o chat.
5. `void Promise.all` não bloqueia o reset dos `attached*` states.

### Sub-etapa 4 — `app-chat.tsx` polishing

- Removeu o `ModelingPlanCard` legacy interno (~45 linhas).
- `MessageBubble` aceita `modelingPlanActions?: ModelingPlanCardActions`.
- Lógica de decisão Plan vs Edit:
  ```tsx
  metadata.modeling_plan.kind === "edit" &&
    metadata.modeling_plan.status !== "waiting_approval"
    ? <ModelingEditCard />
    : <ModelingPlanCard ... callbacks />
  ```
- Teste `app-chat.test.tsx` atualizado: assertions sem `mode` badge,
  status localizado, sem copy "painel 3D" removido.

### Sub-etapa 4 — `modeling3dApi` ganhou `approvePlan` / `rejectPlan` / `executePlan`

**Arquivo:** `apps/web/src/features/modeling-3d/api/index.ts`

```ts
approvePlan(planId, payload = { decision: "approve" }): Promise<ModelingPlan>
rejectPlan(planId, reason: string): Promise<ModelingPlan>
executePlan(planId): Promise<ModelingExecutionResult>
```

Todos usam `apiRequest` com `POST` e mapeiam direto para
`POST /api/3d/plans/{id}/approve` e `POST /api/3d/plans/{id}/execute`
(rotas backend preservadas na Onda 2.11 para uso interno).

---

## Decisões consolidadas com o dono do produto

### Módulo 3D (ADR-013)

- **Fluxo único**: descoberta → plano apresentado no chat → aprovação
  por botões inline → execução → edições com mini-planos. Os três modos
  legados (`plan_only`/`approval_required`/`safe_auto`) são removidos.
- **Aprovação só via botões inline no card**, não no painel. Resposta
  textual livre não aciona execução.
- **Aprovação global do plano cobre todas as etapas**, incluindo
  high-risk (`apply_boolean`, `repair_non_manifold`, `restore_snapshot`,
  `run_script`). Sem reaprovação step-a-step depois.
- **High-risk em edição posterior** abre nova aprovação inline; edição
  comum autoexecuta como mini-plano.
- **Flag `is_modeling_3d` por chat**, persistida e imutável após criação.
  Toggle global vira `nextChatIs3D` (apenas marca a intenção do próximo
  chat).
- **Ativar 3D em chat com histórico**: modal pergunta antes; confirma
  cria novo chat 3D vazio sem copiar mensagens.
- **Anexos com análise profunda**: imagens via vision (gateway LLM,
  stub hoje — ver gap abaixo) e arquivos 3D (`STL`/`OBJ`/`STEP`/`3MF`/
  `BLEND`) via Blender headless — bounding box, mesh stats, simetria,
  features identificáveis, sugestões.
- **Painel 3D removido**. Config de adapters vai para Configurações
  gerais; diagnóstico vira modal acessível pelo cabeçalho do chat 3D.
- **Trigger discovery → planning**: decisão livre do LLM. A tool
  `3d.propose_plan` é o único gatilho formal.

### Título obrigatório (ADR-014, escopo não-3D acoplado)

- **Front e back validam**. Front bloqueia o input (Onda 5 — pendente),
  back retorna 422 quando `chat.title` vazio/default (Onda 2.9, atrás
  da feature flag `TRUTHS_FORGE_REQUIRE_CHAT_TITLE`).
- **Migração backfill** aplica `"Sem título - YYYY-MM-DD"` (derivado
  de `created_at`) a chats existentes sem título (Onda 2.2).
- **Auto-titulação OpenAI removida** completamente (serviço +
  endpoint + provider method) — Onda 2.10.

### Decisões herdadas (v1, ADR-012)

- Blender real e Fusion bridge são obrigatórios para a trilha 3D.
- Fusion tem contrato próprio dentro do bounded context.
- Fusion MCP Server local (porta padrão `27182`) é o caminho preferido;
  bridge legado em `apps/fusion-addin/` permanece como fallback.

---

## Gaps e pendências (LEIA ANTES DE MEXER)

Estes itens **não foram entregues** durante as Ondas 0–4 — não por
descuido, mas por escopo ou dependência. Estão listados aqui para que
outra IA não pense que estão prontos ou que precisam ser refeitos.

### Gap 1 — SSE handler dedicado para execução

**Onde está agora:** `applyPlanToSession` em `App.tsx` atualiza estado
otimisticamente a partir da resposta direta de
`approvePlan + executePlan`.

**O que falta:** backend não emite eventos
`modeling_execution_started`, `modeling_execution_progress`,
`modeling_execution_step_completed`, `modeling_execution_completed`,
`modeling_execution_failed` no stream SSE. Quando esses forem emitidos,
substituir o update otimista por handlers no `streamChat.onEvent` (como
o `"modeling_plan"` já existente em `App.tsx:1247-1269`).

**Para quem implementar:** começar em `backend/app/api/routes/chat.py`
no bloco do `modeling_3d.enabled`, depois adicionar dispatcher
correspondente em `apps/web/src/App.tsx`. Carryover para **Onda 6** ou
sub-fase dedicada entre 5 e 6.

### Gap 2 — Wire do `ModelingChatOrchestrator` ao stream handler

**Onde está agora:** `POST /api/chat/stream` ainda chama
`ModelingService.create_plan_async` inline (compat v1). O
`ModelingChatOrchestrator` existe em
`backend/app/modeling/chat_orchestrator.py` com 5 métodos públicos
(`ask_clarification`, `propose_plan`, `propose_edit_plan`,
`approve_plan`, `reject_plan`, etc.) e está totalmente testado, mas
**não é chamado pelo stream handler ainda**.

**O que falta:** o stream handler precisa:

1. Detectar `chat.is_modeling_3d` no início.
2. Decidir a fase atual via `chat.modeling_stage`.
3. Chamar `orchestrator.propose_plan(chat, payload)` em `discovery`
   (em vez de `service.create_plan_async`).
4. Em `editing`, chamar `orchestrator.propose_edit_plan`.
5. Emitir SSE event `modeling_plan` igual ao fluxo atual.
6. Plumar o `EditPlanOutcome.requires_approval` para o frontend saber
   se pode auto-executar ou exibir reaprovação.

**Para quem implementar:** Carryover para **Onda 6** ou PR dedicado
entre 5 e 6. Pode ser feito junto com o Gap 1 (SSE de execução)
porque os dois mexem na mesma região do código.

### Gap 3 — Vision real para imagens

**Onde está agora:** `ModelingAttachmentAnalyzer._call_vision` retorna
`None` como stub. Frontend exibe summary placeholder + sugestões.

**O que falta:** quando o `LLMGateway` aceitar conteúdo multimodal
(`list[dict[str, Any]]` em vez de `list[dict[str, str]]`), implementar
chamada vision real com a imagem como data URL base64. Local exato:
`backend/app/modeling/attachment_analyzer.py:_call_vision`.

**Para quem implementar:** sub-fase no contexto de uma melhoria do
gateway LLM; não bloqueia nenhuma das ondas restantes.

### Gap 4 — Análise profunda de CAD STEP

**Onde está agora:** `ModelingAttachmentAnalyzer._analyze_cad_metadata`
retorna metadata-only (size_bytes, extension).

**O que falta:** quando o Fusion adapter expor análise headless de
STEP (corpos, features, printability), trocar o stub por chamada real.
Local: `backend/app/modeling/attachment_analyzer.py:_analyze_cad_metadata`.

**Para quem implementar:** sub-fase do bounded context Fusion;
backlog Onda 6+.

### Gap 5 — Telemetria do trigger `propose_plan`

**Decisão:** instrumentar mas não bloquear (handoff Onda 2). Telemetria
deve auditar quando o LLM chama `propose_plan` com descoberta
insuficiente (poucas mensagens em discovery).

**Onde está agora:** não implementado.

**Para quem implementar:** adicionar audit event
`modeling.chat.proposed_plan_without_clarification` no
`ModelingChatOrchestrator.propose_plan` quando
`chat.message_count_in_stage == 1` ou similar. Pode ser feito junto
com o Gap 2 (wire do orchestrator).

### Gap 6 — Modal de título obrigatório no frontend (resolvido na Onda 5)

**Decisão:** ADR-014. Cliente React precisa exigir título antes da
primeira mensagem.

**Onde está agora:** backend já valida com `HTTP 422` quando a feature
flag `TRUTHS_FORGE_REQUIRE_CHAT_TITLE=true`. Flag está em
`backend/app/core/config.py`, default `false` para não quebrar o
frontend legado.

**Status:** concluído localmente em `codex/3d-chat-title-required`; falta
PR/merge.

---

## Guia histórico da Onda 5

Este plano fica como registro do que foi implementado. A maior parte do
trabalho da Onda 5 foi frontend; o backend recebeu apenas o ajuste para
persistir o título em rascunhos já criados.

### Contratos backend que o frontend precisa honrar (já implementados)

1. **Campo opcional `title` em `ChatStreamRequest`**:

   ```python
   # backend/app/core/contracts.py
   class ChatStreamRequest(BaseModel):
       message: str
       session_id: str | None = None
       title: str | None = None   # ← novo (Onda 2.9)
       ...
   ```

   O frontend deve incluir esse campo em todo `POST /api/chat/stream`.

2. **422 quando flag ativa**:

   ```python
   # backend/app/api/routes/chat.py
   def _enforce_required_chat_title(payload: ChatStreamRequest) -> None:
       normalized = (payload.title or "").strip().lower()
       if not normalized or normalized in DEFAULT_CHAT_TITLES:
           raise HTTPException(
               status_code=422,
               detail={
                   "error": "chat_title_required",
                   "message": "Esse chat precisa de um título antes...",
               },
           )
   ```

   `DEFAULT_CHAT_TITLES = {"novo chat", "new chat"}` — qualquer um
   desses + vazio → 422.

3. **Feature flag controla**:
   ```python
   # backend/app/core/config.py
   require_chat_title: bool = Field(
       default_factory=lambda: (
           os.getenv("TRUTHS_FORGE_REQUIRE_CHAT_TITLE", "false").lower()
           in {"1", "true", "yes", "on"}
       )
   )
   ```
   Na Onda 5, `infra/.env.example` e `docker-compose.dev.yml` foram
   atualizados para `true`.

### Plano de execução da Onda 5

#### 5.1 — Componente `ChatTitleRequiredDialog`

**Onde:** `apps/web/src/features/chat/components/ChatTitleRequiredDialog.tsx`
(criar pasta `components/` se não existir).

**Props:**

```ts
interface ChatTitleRequiredDialogProps {
  open: boolean;
  initialTitle?: string;
  onConfirm: (title: string) => Promise<void> | void;
  onCancel?: () => void;
  busy?: boolean;
}
```

**Comportamento:**

- Modal acessível (`role="dialog"`, `aria-modal="true"`).
- Input texto com `min_length=1`, autofocus.
- Botão "Confirmar" desabilita enquanto título vazio/whitespace ou
  está em `DEFAULT_CHAT_TITLES` (`"Novo chat"`, `"New chat"`).
- ESC cancela; Enter confirma se válido.
- Copy: "Dê um título para esse chat antes de começar: isso ajuda
  você a encontrá-lo depois e economiza chamadas ao modelo."

**Test file:** `ChatTitleRequiredDialog.test.tsx` cobrindo:

- Modal abre/fecha com prop `open`
- Confirma desabilitado com título vazio/default
- ESC fecha
- Enter confirma quando válido
- `busy=true` desabilita confirm

#### 5.2 — Hook `useChatTitleGate`

**Onde:** `apps/web/src/features/chat/hooks/useChatTitleGate.ts`.

**API sugerida:**

```ts
function useChatTitleGate(activeSession: ChatSession | null) {
  // Retorna { needsTitle: boolean, openTitleDialog, ... }
  // needsTitle === true quando:
  //   - sessão é nova (sem messages.length) OU
  //   - title está em DEFAULT_CHAT_TITLES OU vazio/whitespace
}
```

#### 5.3 — Wire no `App.tsx`

1. Importar `useChatTitleGate` e `ChatTitleRequiredDialog`.
2. Antes de chamar `streamChat`, checar `gate.needsTitle`:
   - Se sim, abrir modal e aguardar `onConfirm`.
   - Depois de confirmar, atualizar `session.title` localmente e
     incluir `title` no payload do `streamChat`.
3. Em `onError` do `streamChat`, detectar
   `error.reason === "chat_title_required"` (ou detail.error) e abrir
   o mesmo modal.
4. No `ChatStreamRequest`, passar `title: activeSession?.title`.

#### 5.4 — Tratar 422 no `streamChat`

**Onde:** `apps/web/src/lib/api.ts`.

Precisa que o `onError` callback do `streamChat` seja chamado com algo
do tipo:

```ts
onError({
  reason: "chat_title_required",
  message: detail.message,
  status: 422,
});
```

#### 5.5 — Flag flip + smoke test

Após 5.1–5.4 mergeado:

1. Adicionar `TRUTHS_FORGE_REQUIRE_CHAT_TITLE=true` em
   `infra/docker-compose.dev.yml` e `infra/.env.example`.
2. Rodar manualmente: criar chat novo, tentar enviar mensagem sem
   título → modal abre → confirma → mensagem sobe sem 422.
3. Validar que chats antigos (com título já populado pela migração 002)
   continuam funcionando sem modal.

#### 5.6 — Atualizar docs

- `docs/application-map.md` — descrever o fluxo de criação de chat com
  título obrigatório.
- `README.md` — se mencionar auto-titulação, remover.
- `specs/modeling-3d-fusion/tasks.md` — marcar 5.1–5.6 concluídos.
- `handoff.md` (este arquivo) — mover Onda 5 para mergeado e listar
  novos commits.

### Estimativa

- 5.1–5.4: ~400 linhas TSX + testes
- 5.5: 3 linhas em env files + smoke test manual
- 5.6: ~50 linhas docs

Total: pequeno-médio. Compatível com um único PR.

---

## Mapa de contratos de API (frontend ↔ backend)

| Endpoint                                                | Quem chama                                 | Estado                                                                               |
| ------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------ |
| `POST /api/chat/stream`                                 | `streamChat` em `lib/api.ts`               | Aceita `title` opcional (Onda 2.9). Retorna SSE com `modeling_plan` event quando 3D. |
| `POST /api/chat/sessions/{chat_id}/attachments/analyze` | `modeling3dApi.analyzeAttachment`          | Onda 2.7. Retorna `ChatAttachmentAnalyzeResponse`.                                   |
| `GET /api/3d/capabilities`                              | `modeling3dApi.capabilities`               | Diagnóstico, mantido.                                                                |
| `GET /api/3d/plans`                                     | `modeling3dApi.plans`                      | Read-only para diagnóstico.                                                          |
| `POST /api/3d/plans/{id}/approve`                       | `modeling3dApi.approvePlan` / `rejectPlan` | Onda 4. Body `{decision, reason}`.                                                   |
| `POST /api/3d/plans/{id}/execute`                       | `modeling3dApi.executePlan`                | Onda 4. Sem body.                                                                    |
| ~~`POST /api/3d/plans`~~                                | —                                          | **Removido na Onda 2.11**.                                                           |
| ~~`POST /api/3d/steps/{id}/approve`~~                   | —                                          | **Removido na Onda 2.11**.                                                           |

## Mapa de state machine

```
created (title obrigatório quando flag on)
  → discovery
       ↓
   planning ← (rejeição) ←┐
       ↓                  │
   approved               │
       ↓                  │
   executing              │
       ↓                  │
   editing ────────────── ┘ (high-risk em edição)
       │
   completed (archive)
```

Estados representados em `ChatSession.modeling_stage` (enum `ChatModelingStage`).
Transitions implementadas em `backend/app/modeling/chat_state.py`
(funções puras, 18 testes).

## Mapa de eventos de auditoria

Eventos emitidos pelo `ModelingChatOrchestrator` (todos com
`metadata.chat_id`):

- `modeling.chat.discovery_started`
- `modeling.chat.clarification_asked`
- `modeling.chat.plan_proposed`
- `modeling.chat.plan_approved`
- `modeling.chat.plan_rejected`
- `modeling.chat.execution_started`
- `modeling.chat.execution_completed` (ou `_failed`)
- `modeling.chat.edit_auto_executed`
- `modeling.chat.edit_high_risk_requested`
- `modeling.chat.edit_high_risk_approved` / `_rejected`
- `modeling.chat.archived`

Eventos legados (preservados): `modeling.plan_created`,
`modeling.plan_approved`, `modeling.plan_rejected`,
`modeling.plan_executed`, `modeling.snapshot_created`,
`modeling.snapshot_restored`, `modeling.printability_validated`.

---

## Pontos abertos (não-bloqueantes para 5/6)

- **System prompt de descoberta**: 5 tools dedicadas estão expostas via
  `backend/app/modeling/prompts/discovery_system.md`. Falta adicionar
  exemplos few-shot para o trigger `propose_plan`. Backlog Onda 6+.
- **Limites de tamanho/timeout para análise 3D**: proposta inicial é
  50 MB / 15 s, ajustar conforme experimentos com Blender real.

---

## Referências

- Plano de execução original (host-side): `C:\Users\Jonatan\.claude\plans\gostaria-de-planejar-uma-lovely-ember.md`
- Spec viva: `specs/modeling-3d-fusion/spec.md`
- Plano técnico: `specs/modeling-3d-fusion/plan.md`
- Tasks: `specs/modeling-3d-fusion/tasks.md`
- ADRs: `docs/decisions.md` (ADR-012, ADR-013, ADR-014)
- Documentação operacional: `docs/3d-mcp-modeling.md`
- Mapa da aplicação: `docs/application-map.md`
- PRs: #19 (Onda 0+1), #20 (Onda 2), #21+#22+#24 (Onda 3 + fixes),
  #25 (Onda 4)
