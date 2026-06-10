# Varredura completa — Módulo de Modelagem 3D (workflows)

**Data**: 2026-06-10 · **Branch auditada**: `claude/hopeful-brahmagupta-jc4bg6` (= `feat/3d-modelling-updates` consolidada) · **Referência de comportamento idealizado**: `specs/005-modeling-3d-fusion/` (spec v4, plan macro, micro-planos F1–F9), `.specify/memory/constitution.md` (P6/P8), `AGENTS.md`, ADRs 017–024.

**Método**: 6 fatias auditadas em paralelo (núcleo do fluxo de chat, loop agêntico/execução, segurança/policy/snapshots/auditoria, adapters Fusion/Blender + MCP, frontend, estado rico/espacial F1/F7/F9) + execução real dos gates de qualidade. Vários achados centrais foram confirmados de forma independente por 2–3 fatias.

**Volume**: ~135 achados únicos após cruzamento de duplicatas — **5 críticos, ~20 altos, ~55 médios, ~40 baixos** + ~25 gaps de teste estruturais. Os relatórios detalhados por fatia (anexos no fim deste arquivo) preservam arquivo:linha e evidência de cada achado.

---

## 0. Correções aplicadas nesta branch (2026-06-10, pós-varredura)

Aprovadas pelo dono ("corrigir tudo que não precisa de interação minha"). Gates verdes após cada commit: backend `ruff format --check` + `ruff check` + `pytest` (689 testes); web `format:check` + `lint` + `test:unit` (145) + `typecheck` + `build`.

| Commit | Achados corrigidos |
|---|---|
| `fix(modeling): aprovacao obrigatoria p/ destructive + gate anti-replay` | **C1** (enforcement de `destructive` em `requires_approval`/policy/`_plan_has_high_risk`), **C5 backend** (409 para approve/execute de plano terminal/não-aprovado; `ensure_plan_approvable`/`ensure_plan_executable` como fonte única), guard do delta corretivo alinhado ao RF-009 (corrige dentro do envelope aprovado; rejeita só escalação) |
| `fix(modeling): caminho vivo do card passa pelo orchestrator` | **C2** (rotas delegam ao orchestrator; state machine duplicada removida da rota), **C3** (rejeição volta a `discovery` + justificativa registrada no histórico para o discovery usar — RF-007), **C4** (estágio `failed` alcançável; retry de `failed` re-executa; falha de edição não é mais anunciada como sucesso), vínculo `modeling_plan_id` só para planos primários |
| `fix(modeling): loop agentico — rollback nativo injetado e divergencia exausta falha explicito` | **RF-011 real** (marker de timeline capturado pré-execução + `fusion.rollback_timeline` injetado no loop), exaustão por divergência termina `failed` explícito (CS-003), `agent_loop.rollback_failed` no trace (RF-024), contagem de correções precisa, `ModelingTraceLevel.warn` no retry async do planner |
| `fix(modeling): transporte mcp_http no contrato + paridade list/call no MCP standalone` | `mcp_http` no Literal (diagnóstico não quebra mais no modo standalone), `relate_bodies` fora do `tools/list` externo, teste de contrato cross-layer registry×scripts (M11) |
| `fix(modeling): Gate B nao estoura excecao crua com ref declarativa` | crash do enforcement F9 com `@`-ref em `translation_mm` (ADR-024) |
| `fix(web/modeling-3d): build verde + fluxo do card coerente com o backend` | typecheck/build (ES2022 + `Error cause`), **C5 frontend** (reconciliação do card via `GET /plans/{id}` após 409), ternário morto `failed→editing`, SSE `waiting_approval→planning`, `trace_id` no modal de diagnóstico (RF-024), tipos `mcp_http`/`model_state`/`model_verdict`/`sub_goals`, rótulos PT-BR no EditCard, textos pré-P1 do diálogo/configurações atualizados, catch no rollback do EditCard |
| `style(backend): ruff format + E501 zerados` | gate RNF-004 backend verde |
| `fix(modeling): token timing-safe no add-in + preferencia de software persistente` | A2 (add-in compara token com `compare_digest`), preferência de software (RF-001) persiste entre chats |

**Permanecem em aberto** (exigem decisão do dono e/ou validação no Fusion real): contradição ADR-022 × `move_body` assado (placement paramétrico) e schemas LLM-facing contraditórios; heurística `is_open_boundary` (falso-positivo para furo passante); RF-026 (printability/artifacts do Fusion no tempdir do host); relatório `VerificationResult`/UI esperado×medido (RF-012/013); badges de modo mock/real na UI (RF-002); add-in legado com 11/55 tools (A1); RF-014 pulada com software "auto"; anexos perdidos entre turnos (F4); executor linear default sem parada na falha (flags OFF); demais médios/baixos dos anexos.

---

## 1. Críticos (5)

### C1. Categoria `destructive` não exige aprovação em nenhuma camada determinística
`policy.py:104-111`, `tool_registry.py:712-733`, `chat_orchestrator.py:1093-1101`, `planner.py:610-614` — `requires_approval` só checa blocked/read_only/high_risk/`risk_level==high`; `ToolCategory.destructive` (ex.: `fusion.delete_body`, que ESTÁ no `PLANNER_TOOLSET`) cai em "não precisa de aprovação". A policy ainda **sobrescreve** `approval_required=true` honesto do LLM. Numa edição em modo fluido, "remova o corpo X" com `risk_level=low` **deleta geometria sem humano no loop**; o corretor do loop agêntico pode trocar um passo por `delete_body` e re-executar. A docstring do próprio enum promete "Always requires approval". **Viola P6/P8/RF-022/RNF-003.** A única defesa real é o prompt do planner. *(Confirmado por 2 fatias independentes.)*

### C2. DT-006 só meio-resolvido: o caminho vivo aprovar/rejeitar/executar bypassa o orchestrator
`routes/modeling.py:104-133` chama `ModelingService.approve_plan/execute_plan`, não o `ModelingChatOrchestrator`. Consequências: o estágio do chat **não transita** pela state machine (planning→approved→executing→editing/failed nunca acontece no fluxo vivo); audits `modeling.chat.plan_approved/execution_*` nunca são emitidos; `_advance_chat_to_editing_after_execute` (modeling.py:154-186) reimplementa a transição na rota (state machine duplicada — exatamente o que DT-006/RNF-006 mandaram consolidar). A docstring de `get_modeling_orchestrator` afirma o contrário (stale).

### C3. RF-007 quebrado: rejeitar plano trava o chat em vez de retomar a descoberta
Rejeição via card → plano `rejected`, chat permanece `planning` com `modeling_plan_id` setado. A próxima mensagem do usuário (a justificativa!) tenta propor plano → `transition(planning, PLAN_PROPOSED)` é inválida → `InvalidModelingStageTransition` → SSE "error". Além disso a justificativa coletada pela UI é **descartada** pelo backend (não vai a auditoria, nem ao plano, nem ao histórico que o discovery lê — `service.py:221-234`, `chat_modeling.py:370-379`). O teste `test_chat_stream_3d_reject_returns_plan_to_discovery` tem nome que promete RF-007 mas só asserta `plan.status=="rejected"`.

### C4. Chat fica preso após falha de execução — DT-008 "resolvido" mas inalcançável no caminho vivo
Falha no `/execute` → plano `failed`, mas `_advance_chat_to_editing_after_execute` faz early-return (status != completed) → chat permanece `planning`. O estágio `failed` (`chat_state.py:111`) **nunca é atingido no fluxo real**; a próxima mensagem crasha com a mesma transição inválida de C3. DT-008 foi corrigido na state machine, mas a state machine não é usada pelo caminho vivo (consequência de C2).

### C5. Card de plano persistido "ressuscita" aprovável — re-execução de plano já concluído
O card lê `metadata.modeling_plan` da mensagem persistida (gravado uma única vez em `waiting_approval` — `chat_modeling.py:542-546`); após aprovar/executar, nem o backend atualiza o metadata nem o frontend reconcilia via `GET /plans/{id}` ao recarregar. Pior: `apply_plan_approval` e `service.execute_plan` **não têm guarda de status terminal** — um clique num card histórico re-aprova e re-executa todos os passos (incluindo high-risk cobertos pela aprovação antiga) sobre o design ativo do Fusion. Relacionado: `POST /plans/{id}/execute` também executa plano `waiting_approval` (o gate ADR-013 só existe no orchestrator, que é código morto no caminho vivo — ver C2).

---

## 2. Altos (seleção dos ~20)

**Segurança / contrato de execução**
- **Rollback de RF-011 é no-op em produção**: `run_plan_with_optional_loop` nunca injeta `rollback=` → sempre `agent_loop.rollback_skipped`; e **nenhum snapshot automático precede a execução** — não há "último estado seguro". O primitivo (`fusion.rollback_timeline` + marker) já existe no undo de edição, só não foi plugado. DT-005 está pior que o documentado: snapshot de filesystem não captura o estado do Fusion (que vive no host).
- **Exaustão do loop por divergência geométrica termina como sucesso**: plano fica `running` → orchestrator interpreta `EXECUTION_COMPLETED` → chat cai em `editing` como se tivesse dado certo (viola RF-011/CS-003).
- **Correção high-risk impossível (RF-009 furado)**: o corretor rejeita qualquer correção cuja tool exija aprovação — até a MESMA tool high-risk já aprovada no plano. RF-009 diz que a aprovação única cobre deltas corretivos; o código nem pausa nem corrige: recusa silenciosamente e o plano falha.
- **Executor linear (caminho default, flag do loop OFF) não para na primeira falha**: steps seguintes continuam executando sobre modelo inconsistente, sem rollback.

**Fidelidade / verificação (coração do produto)**
- **`VerificationResult`/relatório esperado×medido não existe**: a entidade-chave da spec não foi implementada; verificação é transiente (conformidade nunca é registrada; divergência só aparece dentro de payload de trace). RF-012/RF-013/CS-004 sem implementação real — e a UI também não exibe `model_verdict`/`model_state` (campos nem existem nos tipos TS).
- **RF-002 furado na UI**: nenhum badge distingue mock/adapter ausente/real/erro no fluxo do chat — com Fusion desconectado, o chat inteiro "finge sucesso" (card diz "Plano executado." com transport mock). No backend, mock do Fusion devolve `ok:True` até para tool inexistente.

**RF-026 / printability (3 sub-gaps)**
- Destino de impressão perguntado na descoberta mas nunca persistido como estado do chat; `fusion.validate_printability` como passo de plano não persiste `ModelingPrintabilityReport`; exports do Fusion caem no tempdir do **host** e nunca viram PlatformFile/artifact registrado (o registro só funciona para o Blender, congelado).

**Fluxos quebrados em condições default**
- **RF-014 pulada com software "auto" (o default)**: reconciliação ao vivo e `rollback_marker` só rodam `if software == fusion`; o frontend manda `null` e o planner resolve fusion como default — então no caminho default a edição não lê estado atual e o botão "Desfazer última edição" some.
- **Anexos perdem-se entre turnos (F4/RF-004)**: a análise de imagem só roda sobre `attached_file_ids` do turno corrente e nunca é persistida — se a descoberta fizer 1 pergunta, o plano final é gerado "cego" à imagem (image-to-model degrada para text-to-model).
- **Gate B (F9) crasha com exceção crua**: `enforce_relative_coord` roda sobre args crus e faz `float()` em componente declarativo válido (`@body(...)...`) → `ValueError` não-tipado escapa do handler e derruba o `execute_plan` (viola ADR-024 "erro tipado, nunca exceção crua").
- **`is_open_boundary` falso-positivo**: qualquer face com furo passante (2+ loops) vira "abertura" → placa com furos é rotulada `container` no estado semântico que o LLM lê; roles `open_boundary`/`cover_opening` podem mirar a face errada.

**Contratos dessincronizados**
- **ADR-022 × código**: a spec/ADR prometem placement paramétrico (make_component + joint, "sobrevive a recompute"; 1º corte 'baked' foi rejeitado pelo dono) — o código emite `move_body` assado; e `tool_schemas.py:611-617` ainda anuncia ao LLM o comportamento antigo enquanto `tool_registry.py:492-498` descreve o novo: **as duas fontes LLM-facing se contradizem no mesmo prompt**.
- **`mcp_http` derruba o diagnóstico**: o transport documentado não existe no Literal do contrato nem nos tipos TS → `GET /capabilities` 500 → modal de diagnóstico inteiro quebra exatamente no modo MCP standalone (Fase 1).
- **Add-in bridge conhece 11 das ~55 tools** com handlers próprios divergentes (e compara token com `!=`, não timing-safe) — no Fusion real só com add-in, a maioria dos planos falha; doc trata como fallback equivalente.
- **`fusion.relate_bodies`** exposto no `tools/list` do MCP standalone mas sem handler executável (mismatch registry×scripts; não há teste de contrato cross-layer).
- **`ModelingTraceLevel.warning` não existe** (`planner_service.py:554`) → `AttributeError` mata o retry F6 no caminho async com `fallback_reason` enganoso. *(Confirmado por 3 fatias.)*
- **Gates de qualidade (RNF-004) vermelhos no próprio módulo**: web `typecheck`/`build` **não compilam** (`useModelingPlanActions.ts:92` — `new Error(msg, {cause})` exige ES2022); `ruff format` falha em 25 arquivos; 16× E501 em `fusion_mcp_scripts.py`/`tool_registry.py`; prettier falha em `useModeling3dTrace.ts`. Backend pytest: 678 verdes; web vitest: 144 verdes.

---

## 3. Status real das dívidas documentadas (DT)

| DT | Status documentado | Status real encontrado |
|---|---|---|
| DT-002 (createByReal sem parâmetro) | fechado (Fase 4) | **Parcial** — primitivas box/cylinder/sphere/cone ainda "assam" |
| DT-005 (snapshot filesystem) | redesenhar na Fase 2 | **Aberta e pior**: rollback nunca injetado, sem snapshot pré-execução, snapshot não captura estado do Fusion |
| DT-006 (rota bypassa orchestrator) | consolidar na Fase 2 | **Meio-resolvida**: orchestrator existe mas o caminho vivo aprovar/rejeitar/executar não passa por ele (C2) |
| DT-008 (EXECUTION_FAILED = sucesso) | corrigida | **Resolvida na state machine, inalcançável no caminho vivo** (C4); reintroduzida no caminho de edição (falha de edição cai em `editing` como sucesso) |
| DT-009 (script backend-owned) | ADR-019 aceito | **OK no desenho**; gap nomeado no próprio ADR segue aberto (transporte default 27182 sem auth) |
| DT-010 (loop não pausa + divergência) | ajustada | **Parcial com torção**: divergência dispara correção e não pausa, mas correção high-risk é rejeitada (contra RF-009) e `destructive` não é detectada (C1) |
| DT-011/DT-012 (sheet metal/sculpt) | congeladas | Coerente — tools removidas |

## 4. Padrão estrutural dos achados

1. **Camada nova bem construída, integração final ausente**: o repositório tem os primitivos certos (state machine com `failed`, rollback de timeline, `model_verdict`, tracer, resolver espacial com erros tipados) — mas o "último parafuso" não foi apertado: rotas não usam o orchestrator, o loop não recebe o rollback, a UI não recebe o verdict, o enum não recebe o transport.
2. **A suíte verde dá falsa segurança**: 678+144 testes passam porque os testes fixam o comportamento atual (inclusive o defeituoso — ex.: sanitizer descartando `position_mm`, texto pré-P1 do diálogo) e não cobrem os caminhos de falha/estágio do chat/categoria destructive.
3. **Defaults divergem do que foi validado nos gates**: loop agêntico, planejamento hierárquico e camada espacial vivem atrás de flags default OFF; o comportamento default (linear, sem rollback, sem parada na falha) é o menos seguro e o menos testado nos gates reais.

## 5. Priorização recomendada

1. **P0 — segurança/aprovação**: C1 (enforcement de `destructive` em `requires_approval`/policy/`_plan_has_high_risk` + teste de decisão), C5 + gate de status terminal em `approve_plan`/`execute_plan` (409 para plano já executado/não aprovado).
2. **P0 — destravamento do fluxo vivo**: C2/C3/C4 (rotear aprovar/rejeitar/executar pelo orchestrator ou, no mínimo, transitar estágio + propagar justificativa de rejeição + alcançar `failed`).
3. **P1 — RF-011 real**: injetar rollback no loop + snapshot/marker automático pré-execução; corrigir o terminal state da exaustão por divergência.
4. **P1 — build verde**: corrigir `useModelingPlanActions.ts:92` (typecheck/build), `ModelingTraceLevel.warn`, ruff/prettier.
5. **P2 — fidelidade visível**: persistir `VerificationResult`/expor `model_verdict` na UI; badges de modo mock/real no chat; `mcp_http` no contrato.
6. **P2 — consistência espacial/contratos**: Gate B com erro tipado; `is_open_boundary` com critério de loop interno; reconciliar ADR-022×schemas×registry; teste de contrato registry×schemas×scripts.

## 6. Pontos sólidos confirmados (sem achado)

- Fronteira ADR-019 bem implementada: `run_script` inalcançável; args sempre dados (nunca código); export `target` sanitizado.
- Auth do MCP standalone correta (Bearer + `compare_digest`, loopback default, sem rota sem auth); backend é mesmo só um cliente.
- F1 (estado rico) integrada de ponta a ponta: captura pós-execução → `plan.model_state` → contexto de edição → blocos hierárquicos → reconciliação; tokens estáveis com `edge_token_stale`.
- Conversões de unidade cm↔mm do read-back corretas (spot-check ×10/×100/×1000).
- RF-006 no frontend: aprovar/rejeitar-com-justificativa/editar existem e a edição realmente envia o plano editado (PATCH).
- RF-003 núcleo: clarificação não cria planos/execuções; round-trip de persistência dos campos 3D sem perda (dev_store e postgres em paridade).
- Steps bloqueados nunca executam; expansão F7 bloqueia concretos high-risk fail-safe; deprecated tools (ADR-020) fora do planner/schemas/edit_plan.


---

# ANEXO: core-chat-flow.md

# Auditoria — Núcleo do Fluxo de Chat (Modelagem 3D)

> Rascunho incremental — achados confirmados até agora. Versão final ordenada por severidade ao fim.

## Achados confirmados (rascunho)

1. [crítica] Caminho vivo de aprovar/rejeitar/executar NÃO passa pelo orchestrator (DT-006 só meio-resolvido)
   - backend/app/api/routes/modeling.py:104-133 chama `_service().approve_plan` / `_service().execute_plan` (ModelingService), não `ModelingChatOrchestrator.approve_plan_only/execute_plan/reject`.
   - Consequências: estágio do chat NÃO transita (planning→approved→executing→editing/failed nunca acontece pela state machine); audit `modeling.chat.plan_approved/execution_started/execution_completed/execution_failed` nunca emitidos no caminho vivo; `_advance_chat_to_editing_after_execute` (modeling.py:154-186) reimplementa a transição na rota (state machine duplicada).
   - Docstring de `get_modeling_orchestrator` (chat_orchestrator.py:1195-1204) afirma que as rotas `/approve`+`/execute` usam o orchestrator — FALSO (stale).

2. [crítica] RF-007 quebrado no caminho vivo: rejeitar plano NÃO retoma a descoberta
   - POST /plans/{id}/approve com decision=reject → service.approve_plan → apply_plan_approval → plano `rejected`; chat fica em `planning`, modeling_plan_id segue setado.
   - Próxima mensagem do usuário (justificativa) → rota propõe plano primário → transition(planning, PLAN_PROPOSED) inexistente → InvalidModelingStageTransition → SSE "error".
   - Teste test_chat_stream_3d_reject_returns_plan_to_discovery (test_modeling_routes.py:161) tem NOME que promete RF-007 mas só asserta plan.status=="rejected" — não verifica o estágio do chat.

3. [crítica] Chat fica preso após falha de execução no caminho vivo (DT-008 inalcançável)
   - Falha em /execute → plano failed, `_advance_chat_to_editing_after_execute` early-return (status != completed) → chat permanece em `planning`. Estado `failed` (chat_state.py:111) é inalcançável no fluxo vivo.
   - Próxima mensagem → mesma exceção de transição (planning, PLAN_PROPOSED).

4. [alta] Gate de aprovação só existe no frontend: /execute roda plano `waiting_approval`
   - service.execute_plan (service.py:349-369) não valida status do plano; executor só bloqueia steps `approval_required`. Plano primário sem high-risk forçado a waiting_approval pelo gate P1 (chat_modeling.py:515-528) tem steps approval_required=False → POST /plans/{id}/execute direto executa tudo sem aprovação.
   - O guard ADR-013 existe apenas em orchestrator.execute_plan (chat_orchestrator.py:623-627) — código morto no caminho vivo.

5. [alta] RF-014/T3.6 pulados quando software é "auto" (caso default)
   - chat_orchestrator.py:952-955: leitura de timeline/geometria ao vivo só roda `if software == ModelingSoftware.fusion`, onde software = payload.software_override or chat.modeling_software_preference. Frontend manda null para "auto" (apps/web/src/features/modeling-3d/api/index.ts:138) e o planner resolve fusion como DEFAULT (planner.py:350-354).
   - Resultado: no fluxo "auto" (default), edição NÃO lê estado ao vivo (sem reconciliação RF-014) e rollback_marker fica None (botão "Desfazer última edição" some — T3.6 degradado).

6. [alta] Loop agêntico: exaustão por divergência geométrica termina com status `running` (não-terminal)
   - agent_loop.py:169-175: step divergente mas tool ok → step status completed → has_failed_step False; blocked_step_ids → status `running`. Viola RF-011/CS-003 ("término sempre explícito"). Downstream: orchestrator trata como EXECUTION_COMPLETED (chat_orchestrator.py:499-503: só `failed` vira EXECUTION_FAILED).

7. [alta] Executor linear não para na primeira falha
   - executor.py:297-334: após step failed, steps seguintes continuam executando (sem aborted). Com modeling_agentic_loop_enabled=false (default, config.py:156), viola caso de borda "erro irrecuperável: para, reverte, reporta" — steps subsequentes rodam sobre modelo inconsistente.

8. [média] Rota de clarificação grava estágio diretamente, bypassa state machine, e "cura" o estágio failed
   - chat_modeling.py:383-396: keep_stage = editing se has_existing_model (inclui failed) — chat em `failed` que recebe pergunta de clarificação vai silenciosamente para `editing` sem qualquer execução de correção. Transições CLARIFICATION_ASKED só existem de discovery (chat_state.py:92); rota não usa transition().
   - Também move planning→discovery silenciosamente, órfão: plano waiting_approval antigo continua aprovável pelo card.

9. [média] AttributeError latente mata o retry F6 no caminho async
   - planner_service.py:554: `ModelingTraceLevel.warning` não existe (enum: debug/info/warn/error — contracts.py:1448). Primeiro erro de LLM em _build_plan_async → AttributeError → cai no except externo → fallback heurístico SEM retry e com fallback_reason errado (classifica o AttributeError).

10. [média] Falha em edição auto-executada/high-risk aprovada cai em `editing` como sucesso
    - propose_edit_plan/approve_edit_plan emitem EDIT_AUTO_EXECUTED/EDIT_HIGH_RISK_APPROVED sem olhar execution.plan.status (chat_orchestrator.py:1012-1029, 1045-1052). Edição que falhou deixa o chat em `editing` igual a sucesso (DT-008 reintroduzido no caminho de edição). Runtime status da rota diz "Edição aplicada (modo fluido)" mesmo failed (chat_modeling.py:566-571).

11. [média] Bugs latentes no código morto do orchestrator (failed-stage)
    - approve_plan_only de chat em `failed` → else-branch PLAN_APPROVED → transição inexistente → raise (chat_orchestrator.py:575-588).
    - reject() de chat em `failed` despacha para reject_plan → (failed, PLAN_REJECTED) inexistente → raise (chat_orchestrator.py:686-688).

12. [baixa] `_advance_chat_to_editing_after_execute` sobrescreve modeling_plan_id com plano de edição
    - modeling.py:176-186: quando um plano kind=edit completa via card com chat fora de `editing` (ex.: failed), modeling_plan_id passa a apontar para o mini-plano de edição — contraria o contrato do rollback (modeling.py:142-144) e estreita o contexto da próxima edição.

(pendente: verificação de testes/gaps, RF-003/RF-019, discovery)


---

# ANEXO: core-chat-flow-part2.md

# Auditoria — Núcleo do Fluxo de Chat 3D (Parte 2: RF-003, RF-019, discovery, gaps de teste)

> Continuação de `o ANEXO core-chat-flow.md acima` (achados 1–12 já confirmados lá; não duplicados aqui). Numeração continua em 13.

## Achados novos

13. [alta] Contexto de anexos (F4) se perde entre turnos de descoberta — plano final gerado "cego" à imagem
    - backend/app/api/routes/chat_modeling.py:364-369 — `build_attachments_context` só roda sobre `payload.attached_file_ids` do TURNO CORRENTE; o bloco `<anexos-analisados>` é injetado em `plan_prompt` mas nunca persistido (a mensagem do usuário grava só `content=payload.message` + ids em metadata, linhas 265-284).
    - backend/app/api/routes/chat_modeling.py:118-149 — `_modeling_chat_history` só carrega `role`/`content`; ignora `metadata.attached_file_ids` dos turnos anteriores.
    - Fluxo comum "imagem + pedido → discovery pergunta → usuário responde → plano": no turno 2 `attached_file_ids` vem vazio, o discovery e o planner nunca veem a análise da imagem do turno 1; `plan_prompt` vira `assessment.refined_brief` (linhas 438-439) de um LLM que não viu o anexo. Mesmo no turno 1 (ready imediato), a análise só sobrevive comprimida no `refined_brief` (lossy).
    - Violação: RF-004 ("incorporar o resultado ao contexto") + RF-003 (perguntas dirigidas deveriam considerar o anexo) + RF-019 (histórico existe persistido mas não é usado para reconstituir contexto).
    - Impacto: image-to-model degrada para text-to-model sempre que a descoberta faz ao menos 1 pergunta.

14. [média] Loop de clarificação sem teto de rodadas e com pergunta genérica repetida — caso "pergunta para sempre"
    - backend/app/modeling/discovery.py:172-178 — `effective_ready = ready and confidence >= threshold and not questions`; quando o LLM diz `ready=true` mas com `confidence` consistentemente abaixo do limiar (ex.: 0.65 < 0.7) e sem perguntas, o código injeta SEMPRE a mesma pergunta genérica ("Pode detalhar a geometria e as dimensões principais…"), turno após turno, independentemente da resposta do usuário.
    - backend/app/api/routes/chat_modeling.py:370-436 — a rota não tem contador/limite de rodadas de clarificação nem comando de escape ("planeje assim mesmo"); o único corte é o LLM mudar de ideia.
    - Agravante: `_MAX_HISTORY_MESSAGES = 12` (discovery.py:34,117) ⇒ após ~6 rodadas as primeiras respostas (dimensões etc.) saem da janela e o LLM volta a perguntar o que já foi respondido (perguntas duplicadas).
    - Violação: RF-003 (perguntas DIRIGIDAS, não burocráticas/repetidas); caso de borda de UX sem término garantido.
    - Impacto: usuário pode ficar preso na descoberta sem nunca receber plano; não há registro/aviso de loop.

15. [média] RF-003 silenciosamente desativado fora da OpenAI: descoberta nunca pergunta no fallback heurístico
    - backend/app/modeling/planner_service.py:697-705 — `_resolve_planner_model` só aceita modelos `provider == ProviderName.openai`; backend/app/llm_gateway/providers.py:78-92,408 — só `OpenAIProvider` implementa `generate_structured` (Anthropic/Google levantam `ProviderConfigurationError`).
    - backend/app/modeling/discovery.py:218-240 — `heuristic_assessment` retorna `ready_to_plan=True` sempre; backend/app/modeling/planner_service.py:287-289,339-341 — sem modelo OU em qualquer exceção do LLM, cai nesse heurístico.
    - Violação: RF-003 ("QUANDO o contexto for insuficiente, O SISTEMA DEVE fazer perguntas" — sem exceção na spec) e RF-002 (modos degradados devem ser sinalizados; aqui nada avisa o usuário que a descoberta está desligada — só `rationale="discovery_llm_unavailable"` interno, nunca exibido).
    - Impacto: instalação Anthropic/Google-only ou com OpenAI fora do ar nunca clarifica; "uma peça pequena" vira plano heurístico direto (segurado apenas pelo gate P1 de aprovação).

16. [média] RF-019/restart: nenhum caminho de recuperação para chat persistido em estágio intermediário — estado é legível mas não retomável
    - O estado da sessão 3D persiste corretamente (ChatSession.modeling_* em contracts.py:401-409; payload integral JSON/JSONB em dev_store.py:1233-1247 e postgres_store.py:1388-1394 — round-trip ok), mas a máquina de estados não tem transições de retomada: de `approved`/`executing` os únicos eventos legais são EXECUTION_* (chat_state.py:88-136), que só disparam DENTRO da mesma chamada do orchestrator. Crash/restart entre `EXECUTION_STARTED` e o término estranda o chat para sempre nesses estágios (nenhuma mensagem de usuário gera evento válido).
    - No caminho vivo (que nem transita — achado 1): crash durante POST /execute deixa chat em `planning` + plano `approved`/parcial; a próxima mensagem dispara `transition(planning, PLAN_PROPOSED)` inexistente → SSE "error" (mesma mecânica dos achados 2/3, gatilho novo: restart). Não há reconciliação no startup nem endpoint de reset de estágio; o executor só grava o status final ao fim (executor.py:336-346), então o plano fica como `approved`/`running` órfão.
    - Violação: RF-019 ("persistir de forma reconstituível, para que o motor entenda criações anteriores" — o motor relê mas não consegue retomar o fluxo).
    - Impacto: queda de energia/restart do backend no meio de uma execução = chat 3D permanentemente quebrado (só o card /execute re-tentável salva, se o usuário souber).

17. [média] `modeling_fluid_mode` é persistido mas nunca lido — toggle do usuário é no-op e contrato está stale
    - backend/app/api/routes/chat_modeling.py:336-346 persiste o toggle vindo do cliente; linhas 487-492 chamam `propose_edit_plan(..., fluid_mode=True)` HARDCODED (decisão do dono T3.4 de 2026-05-25). Nenhum outro ponto do backend lê `session.modeling_fluid_mode` (grep: só contracts e a escrita na rota).
    - backend/app/core/contracts.py:406-409 ainda documenta "Quando True, edições aditivas auto-executam" (implica que False pararia no card) — falso; o ramo `not fluid_mode` do orchestrator (chat_orchestrator.py:985-1000, DT-006 waiting_approval) é código morto.
    - Violação: contrato stale (AGENTS.md "atualize documentação quando contrato mudar"); expectativa de human-in-the-loop do usuário que desligou o modo fluido não é honrada (mitigado: high-risk sempre para — P8 preservado).
    - Impacto: UI oferece um controle que não controla nada; edição não-high-risk sempre auto-executa.

18. [baixa] `discovery_system.md` é prompt morto, contradiz o prompt real e tem teste fixando o arquivo morto
    - backend/app/modeling/prompts/discovery_system.md:3-11 afirma ser "carregado pelo orquestrador e injetado como system em cada chamada" e que as 5 tools (`3d.ask_clarification` etc.) "são contrato com o ModelingChatOrchestrator" — nenhum código de produção chama `discovery_system_prompt()` (único consumidor: backend/tests/test_discovery_system_prompt.py); o discovery real usa o `_SYSTEM_PROMPT` inline (discovery.py:57-106) e Structured Outputs, sem tools.
    - Conteúdo conflita com o prompt vivo: md manda "Pergunte, pergunte, pergunte" e "Sem suposições silenciosas: não chute default" vs prompt real "Pergunte SOMENTE quando houver ambiguidade real… assumindo defaults razoáveis".
    - Violação: drift de documentação/prompt (AGENTS.md); teste que dá falsa confiança sobre comportamento inexistente.
    - Impacto: manutenção futura pode "corrigir" o arquivo errado; nenhum impacto de runtime.

## Gaps de teste (RF-003/RF-007/RF-019 + achados 1–12)

19. [alta] Caminho vivo aprovar/rejeitar/executar/falhar sem nenhuma asserção de estágio do chat nem do gate ADR-013 — os achados críticos 1–4 passam batidos
    - backend/tests/test_modeling_routes.py:117-158 (`test_chat_stream_3d_gates_plan_without_executing`): após /approve e /execute asserta só status do PLANO; nunca verifica `session.modeling_stage` (planning→approved→executing→editing) nem os audits `modeling.chat.*` → achado 1 sem regressão.
    - test_modeling_routes.py:161-187 (`test_chat_stream_3d_reject_returns_plan_to_discovery`): além do já apontado (nome promete RF-007, só asserta `rejected`), falta o passo seguinte — enviar a justificativa e assertar que um NOVO plano é proposto → achado 2 (RF-007 quebrado) sem cobertura.
    - Nenhum teste executa um plano COM `conversation_id` que FALHA e verifica o estágio: `test_modeling_failure_is_logged_with_error_envelope_fields` (945-1004) não vincula chat → achado 3 (chat preso após falha; `failed` inalcançável) sem cobertura. DT-008 só é testado na state machine pura (test_chat_modeling_state_machine.py:64-94) e no orchestrator (test_chat_orchestrator.py:307-321) — ambos código morto no caminho vivo.
    - Nenhum teste tenta POST /plans/{id}/execute direto num plano `waiting_approval` esperando recusa → achado 4 (gate só no frontend) sem regressão; o guard do orchestrator (chat_orchestrator.py:623-627) também não tem teste.
    - Impacto: a suíte dá falsa confiança — cobre o orchestrator (test_chat_orchestrator.py:682-741) que as rotas vivas não usam.

20. [média] Edição: falha pós-execução, software "auto" e ramo não-fluido sem cobertura
    - Todos os testes de edição auto-executada assertam apenas sucesso (`completed`): test_modeling_routes.py:416-507 e test_chat_orchestrator.py:343-460; nenhum simula edição auto-executada/high-risk-aprovada cuja execução FALHA → achado 10 (falha vira "Edição aplicada" + editing) sem regressão.
    - Todos os testes fusion de rollback/reconciliação passam `software_override=fusion` explícito (ex.: test_chat_orchestrator.py:361-388); nenhum cobre o caso default "auto" (override None + preferência None) → achado 5 (leitura ao vivo e rollback_marker pulados no fluxo padrão) sem cobertura.
    - `test_chat_stream_edit_auto_executes_even_with_fluid_off` (416-450) fixa o `fluid_mode=True` hardcoded da rota (achado 17); o ramo `not fluid_mode` do orchestrator (chat_orchestrator.py:985-1000) não tem teste nenhum — morto e não-pinado.
    - test_chat_modeling_state_machine.py não asserta que `CLARIFICATION_ASKED` é INVÁLIDO fora de discovery (editing/failed/planning) — exatamente o bypass que a rota explora (achado 8).

21. [média] Discovery e persistência RF-019 sem testes de integração
    - backend/tests/test_modeling_discovery.py:1-121 cobre só `_assessment_from_payload`/`heuristic_assessment` (puros). Sem teste de: `assess_request_async` com exceção do gateway → fallback heurístico (caminho de planner_service.py:339-341, vizinho do bug AttributeError do achado 9); pergunta genérica repetida/limite de rodadas (achado 14); truncamento `_MAX_HISTORY_MESSAGES`; `_build_messages` (system extra de modelo existente, software_override); anexos no contexto entre turnos (achado 13).
    - RF-019: nenhum teste (em nenhum dos 4 arquivos nem em testes de storage) faz round-trip dos campos 3D da ChatSession (`modeling_stage`/`modeling_plan_id`/`modeling_software_preference`/`modeling_fluid_mode`) por dev_store/postgres, nem simula restart (novo store) com chat em `planning`/`approved`/`executing` para verificar reconstituição/retomada (achado 16).
    - RF-003 na rota: `test_chat_stream_asks_clarification_when_ambiguous` (test_modeling_routes.py:322-374) cobre o happy-path (discovery, sem plano criado — núcleo do RF-003 OK), mas não cobre clarificação com chat em `failed` (cura silenciosa → editing, achado 8) nem em `planning` (regressão a discovery com plano órfão aprovável).
    - `test_chat_stream_ambiguous_intent_asks` (453-477) fixa a escrita direta de estágio pela rota (bypass da state machine — achado 8) como comportamento esperado.

## Resumo de contagem (Parte 2)

- crítica: 0
- alta: 2 (13, 19)
- média: 6 (14, 15, 16, 17, 20, 21)
- baixa: 1 (18)

Total parte 2: 9 achados novos. (Parte 1: 3 críticas, 4 altas, 4 médias, 1 baixa.)

## Notas de conformidade (não-achados, verificados)

- RF-003 "sem criar registros de execução": no caminho de clarificação vivo NÃO há criação de ModelingPlan/steps/execução — só mensagem de chat, audit `modeling.chat.clarification_asked` e trace events de observabilidade (chat_modeling.py:383-436). Conforme.
- RF-019 round-trip de serialização: `ChatSession.modeling_*` e `ModelingPlan` (incl. `rollback_marker`, `model_state`, `model_verdict`, `sub_goals` — contracts.py:1147-1192) são campos pydantic declarados, persistidos como payload integral (`model_dump(mode="json")`) em dev_store e postgres (JSONB); enums e datetimes sobrevivem ao round-trip. `get_or_create_session` tem paridade JSON/postgres (dev_store.py:1249-1274; postgres_store.py:1396-1424). Sem perda de campo detectada.
- Parsing do discovery: schema OpenAI `strict: true` (providers.py:424-431) torna payload malformado improvável; `_assessment_from_payload` é defensivo (clamp de confidence, coerção de intent, pergunta fallback).


---

# ANEXO: agent-loop.md

# Auditoria — Loop Agêntico e Execução (módulo 3D) vs. specs 005-modeling-3d-fusion

Escopo: `agent_loop.py`, `executor.py`, `geometry_verifier.py`, `planner.py`, `planner_service.py`, `plan_sanitizer.py`, `model_critique.py`, `visual_critique.py`, `intent_spec.py` + testes correspondentes, contra RF-008..RF-013, RF-018, CS-003/CS-004, DT-005/DT-008/DT-010 e micro-planos Fase 2/F2/Fase 9.

Todos os arquivos abaixo são relativos à raiz do repositório.

---

## Bugs

### [CRÍTICA] Categoria `destructive` não exige aprovação em NENHUMA camada determinística — `delete_body` pode auto-executar
- `backend/app/modeling/policy.py:104-105` — `requires_approval = not read_only and (risk_level==high or _is_high_risk(tool))`; categoria `destructive` não é checada.
- `backend/app/modeling/tool_registry.py:712-733` — `requires_approval()` idem: blocked/read_only/high_risk/risk_level==high; `destructive` cai no "False".
- `backend/app/modeling/chat_orchestrator.py:1093-1101` — `_plan_has_high_risk` idem; não vê `destructive`.
- `backend/app/modeling/planner.py:610-614` — o guard do passo corrigido usa o mesmo `requires_approval`; o comentário diz "Se a correção trocar o tool por um destrutivo/high-risk (ex.: delete_body...) ela NÃO pode auto-executar" — mas `requires_approval("fusion.delete_body", low)` retorna **False**.
- Evidência: `fusion.delete_body` é `ToolCategory.destructive` (`tool_registry.py:533-538`) e ESTÁ no `PLANNER_TOOLSET`. A docstring da própria `ToolCategory` (`tool_registry.py:50`) diz "destructive — **Always requires approval**"; `contracts/fusion-operations.md §1.4` diz "destructive (**aprovação obrigatória**)".
- Impacto: (a) numa edição em modo fluido (`propose_edit_plan`, `chat_orchestrator.py:976-1001`), um plano LLM com `delete_body` rotulado `risk_level=low` **auto-executa uma deleção sem nenhuma aprovação humana** (viola RF-015, RF-022/RNF-003, AGENTS.md, constituição P8); (b) no loop agêntico, uma "correção" que troque a tool por `delete_body` auto-executa. Toda a proteção depende do LLM rotular o risco corretamente — exatamente o não-determinismo que F6/F9 existem para eliminar.

### [ALTA] Esgotamento do loop por DIVERGÊNCIA geométrica termina como sucesso para o usuário (plano fica `running`)
- `backend/app/modeling/agent_loop.py:152-175` — ao esgotar as 5 iterações por divergência (tool ok), `outcome.step.status == completed` → `has_failed_step=False` → plano persiste `status=running`.
- `backend/app/modeling/chat_orchestrator.py:499-503` (e :639-643) — `EXECUTION_FAILED` só se `status == failed`; `running` vira **`EXECUTION_COMPLETED`** e o chat cai em `editing` como sucesso.
- Violação: RF-011 ("para, reverte... e **reporta a falha**") e CS-003 ("**sempre** termina de forma explícita"). O rollback até é disparado, mas o usuário recebe "concluído" e o plano fica preso em `running`. No esgotamento por ERRO de tool o fluxo está correto; o bug é específico do caminho de divergência — justamente o que DT-010 mandou cobrir.

### [MÉDIA] `ModelingTraceLevel.warning` não existe — retry assíncrono do planner morre em `AttributeError`
- `backend/app/modeling/planner_service.py:554` usa `ModelingTraceLevel.warning`; o enum só tem `warn` (`contracts.py:1448-1452`). O sync usa `warn` corretamente (:497).
- Em `_build_plan_async`, a 1ª falha do LLM → branch de retry → `AttributeError` → capturado pelo except externo (:564) → fallback heurístico imediato com `fallback_reason` enganoso. O retry F6 nunca acontece no caminho async. Atenuante: não há chamador vivo de `create_plan_async` — bug latente, invisível aos 678 testes (só o retry síncrono é testado).

### [MÉDIA] Re-execução de step bem-sucedido-mas-divergente não desfaz o efeito anterior — risco de geometria duplicada
- `backend/app/modeling/agent_loop.py:136-143` — em divergência, o loop re-executa o passo corrigido **sem undo/snapshot-restore** do efeito da primeira execução (ex.: `add_box` 100→ mede 90 → corrige p/ 110 → dois corpos). Idem expansão F7 parcial (`executor.py:639-717`).
- Os campos `retryable` / `safe_to_retry_after_snapshot_restore` do envelope (`executor.py:162-180`) **nunca são consultados** pelo loop.
- Violação: RF-013 + caso de borda "não deixa o modelo em estado inconsistente silencioso". O Gate 4 validou só o caso benigno (tool falhou → sem side-effect).

### [BAIXA] Evento "(após N correção(ões))" impreciso quando o corretor desiste
- `agent_loop.py:145-147` — corretor devolve `None` na 1ª tentativa → nenhuma correção aplicada, mas o evento reporta "(após 1 correção(ões))" (RF-013/RF-024).

### [BAIXA] `_decode_input_json` engole JSON inválido do LLM e executa a tool sem args
- `planner.py:1238-1249` — `input_json` inválido vira `{"_raw": ...}`; o step executa com defaults em vez de falhar explicitamente (espírito de RF-018).

### [BAIXA] `_provenance_carry` nunca é resetado entre execuções
- `executor.py:276,825-835` — carry sobrevive entre execuções do MESMO plano (retry permitido); edição manual no Fusion entre execuções → "before" stale → `ChangeRecord` errado → veredito F8 pode acusar falso.

### [BAIXA] Falha do rollback só vai a `logger.error`, não ao trace
- `agent_loop.py:234-237` — sem evento `agent_loop.rollback_failed` no tracer; o dono não vê no diagnóstico (RF-024) que a reversão de RF-011 falhou.

### [BAIXA] Sanitizer não varre valores `dict` aninhados
- `plan_sanitizer.py:78-95` — `_value_has_geom_ref` cobre `str|list|tuple`; ref geométrica dentro de dict passa intacta ao adapter.

---

## Incongruências spec×código

### [ALTA] RF-011: rollback nunca é injetado no caminho vivo — "reverte ao último snapshot seguro" é no-op
- `agent_loop.py:414-427` — `run_plan_with_optional_loop` constrói o loop **sem `rollback=`** → `_do_rollback` (:221-233) sempre cai em `agent_loop.rollback_skipped`.
- Agravante: o rollback nativo JÁ existe e é usado no undo de edição (`fusion.rollback_timeline` + `rollback_marker`, `service.py:371-427`), mas não foi plugado ao loop. A micro Fase 2 marca "[x] rollback" na definição de pronto; DT-005 segue residual.

### [ALTA] RF-009/DT-010: correção de step high-risk legítimo é impossível — o corretor recusa, o loop esgota e "reverte"
- `planner.py:610-614` — `_corrected_step_from_payload` rejeita QUALQUER correção cujo tool exija aprovação. Step original `combine_bodies` (high_risk, JÁ aprovado no plano) que falha não pode ser corrigido nem com a MESMA tool → corrector devolve `None` (`planner_service.py:357-371` engole a exceção) → loop esgota → plano falha.
- Violação direta de RF-009: "A cobertura inclui os **deltas corretivos**... o loop **não pausa** para reaprovar correções high-risk". O código nem pausa nem corrige: recusa silenciosamente. DT-010 marcado como resolvido — só o "não pausa" foi entregue.

### [ALTA] RF-012/RF-013/CS-004: não existe `VerificationResult` nem relatório esperado × medido; conformidade nunca é registrada
- A entidade `VerificationResult` da spec não existe em lugar nenhum do backend.
- `agent_loop.py:207-219` — verificação é transiente: CONFORME → **nada** registrado; DIVERGENTE → só dentro do payload de `agent_loop.correction_attempt`. RF-012 manda "registrar conformidade **ou** divergência"; RF-013 manda "disponibilizar relatório ao usuário". Existe mecanismo de disparo de correção, não relatório.

### [MÉDIA] RF-010/RF-011 só valem atrás de flag default OFF; o caminho default (linear) não para nem reverte em falha
- `config.py:156-160` — `modeling_agentic_loop_enabled` default `false`.
- `executor.py:297-334` — no linear, step falho NÃO interrompe: steps seguintes continuam (cascata), sem rollback. Viola "erro irrecuperável: **para**, reverte e reporta" no comportamento default do produto.

### [MÉDIA] Hierárquico (F2): bloco lazy com step high-risk falha sem qualquer chance de aprovação
- `chat_orchestrator.py:188-231` + `planner_service.py:231-267` — blocos planejados na execução nunca passam por aprovação. Bloco com `combine_bodies` (que o próprio nudge recomenda p/ dobradiças) nasce `waiting_approval`, steps high-risk bloqueiam, bloco termina `running` → turno aborta como falha. Viola RF-008/RF-009 no modo hierárquico (flag default OFF, mas validado em gate).

### [MÉDIA] Sanitizer F6: descarta args de posicionamento silenciosamente e não cobre o caminho de correção
- `plan_sanitizer.py:145-156` — `position_mm`/`origin_mm`/`center_mm` com ref geométrica são **removidos** em vez de falhar o passo: o `hole` executa em posição default (mis-place silencioso) — fixado por teste (`test_f6_plan_sanitizer.py:50-58, 212-224`). A doc promete "não reescreve geometria".
- `planner.py:1176-1180` — `_sanitize_actions` é descartado: nenhuma ação vira evento do `ModelingTracer` (mitigação da micro fase-9, "todo strip vira evento de trace", não implementada — só `logger.warning`).
- `planner.py:591-624` — o passo **corrigido** pelo loop NÃO passa pelo sanitizer: a correção pode reintroduzir ghost keys/refs que a sanitização original removeu.

### [MÉDIA] Gate de aprovação ausente no endpoint do card: `POST /plans/{id}/execute` executa plano não-aprovado
- `routes/modeling.py:126-133` → `service.py:349-366` — `ModelingService.execute_plan` não valida `plan.status`; o loop só barra `draft`. Plano `waiting_approval`/`rejected` roda os steps não-high-risk. O guard "ADR-013 gate" existe SÓ no `chat_orchestrator.execute_plan` (:618-627).

### [MÉDIA] Fallback heurístico pode executar geometria genérica sem revisão humana nos fluxos automáticos
- `planner_service.py:451-510` — falha do LLM degrada para `create_heuristic_plan` (boilerplate retângulo/cilindro + extrude + export). No one-shot o usuário aprova o card; mas: bloco hierárquico (`chat_orchestrator.py:188-195`) executa o bloco heurístico direto, sem gate; correção visual (`visual_critique.py:325-326`) não checa `planner_source` — falha transitória do LLM vira extrusão default aplicada ao modelo (o detector de duplicatas não pega).

### [BAIXA] RF-018 em modo mock: tool desconhecida retorna `ok: true`
- `mcp_client.py:168-195` — sem adapter, QUALQUER `tool_name` (mesmo fora do registry) retorna `ok=True, transport="mock"`. Com adapter real o erro é explícito (`fusion.tool_not_allowlisted`, fusion_adapter.py:414-420) e o mock é sinalizado (RF-002), mas no container o plano "passa verde" com tool inexistente.

### [BAIXA] `seq` dos steps vindos do LLM não é validado nem ordenado
- `planner.py:1161-1162` — `seq` aceito cru (duplicado/fora de ordem); execução segue a ordem do array, mas eventos/traces usam `seq` (`_subgoals_from_payload` ordena; steps não — inconsistente).

- Unidades (item 4): conversões cm↔mm/cm²↔mm²/cm³↔mm³ do read-back foram spot-checked em `fusion_mcp_scripts.py` (×10/×100/×1000, diâmetro→raio /20) e estão corretas.

---

## Dívidas documentadas não resolvidas (status real)

- **DT-005 (rollback nativo)** — ABERTA e pior do que documentado: nem o mecanismo injetável é plugado (sempre `rollback_skipped`), apesar de `fusion.rollback_timeline`+`rollback_marker` já existirem no undo de edição.
- **DT-010** — PARCIAL: ✓ divergência dispara correção; ✓ não pausa; ✗ corretor REJEITA correção high-risk mesmo da própria tool aprovada (RF-009 furado) e ✗ não detecta `destructive`. A spec marca como ajustada — não está.
- **DT-008** — resolvida no `chat_state` (`ChatModelingStage.failed`), mas o caso divergência-esgotada nunca emite `EXECUTION_FAILED` (plano `running`).
- **F2 follow-up** — `replan_next_block` e `MAX_REPLAN_BLOCKS` **não existem no código**; bloco que falha aborta o turno (coerente com a doc; registrado como status real).
- **Fase 9/F6** — 9.4/9.5 não iniciados (documentado); telemetria de sanitização via trace prometida como mitigação não implementada.
- **`geometry_verifier.py` é código morto** — `verify_relation`/`propose_repair` não são chamados por produção (só pelos testes); `relate_bodies` executa sem verificação de contato apesar do verificador pronto (gate P6 declarado no docstring).

---

## Gaps de teste

1. **Esgotamento por divergência** — nenhum teste cobre o estado terminal quando a divergência persiste pelas 5 iterações (`test_agent_loop.py:165-181` só testa divergência que converge). Revelaria o `running`/`EXECUTION_COMPLETED`.
2. **Guard do passo corrigido** — zero testes para `_corrected_step_from_payload` (rejeição high-risk/destructive; e o caso "mesma tool high-risk aprovada deveria poder ser corrigida" — RF-009).
3. **`requires_approval`/policy com `destructive`** — decision table (`test_tool_registry.py:323-339`) não testa nenhuma tool destructive; nenhum teste no repo exige aprovação para `fusion.delete_body` (a CRÍTICA é invisível à suíte).
4. **Retry async do planner** — só o sync é testado (`test_planner_llm.py:606`).
5. **Teste que fixa comportamento contrário à spec** — `test_f6_plan_sanitizer.py:50-58/212-224` consagra o descarte silencioso de `position_mm` (mis-place silencioso onde a spec pede conservadorismo/falha explícita).
6. **Hierárquico** — fakes não cobrem bloco com step high-risk nem bloco heurístico de fallback executando sem gate.
7. **Duplicação na re-execução pós-divergência** — sem teste; idem `retryable`/`safe_to_retry_after_snapshot_restore`.
8. **Gate de aprovação no `service.execute_plan`** — sem teste de execução de plano `waiting_approval`/`rejected` via card.
9. **Relatório de verificação (RF-012/013/CS-004)** — não há teste (a feature não existe).

---

## Resumo

| Severidade | Qtde |
|---|---|
| Crítica | 1 |
| Alta | 4 |
| Média | 7 |
| Baixa | 7 |
| **Total** | **19 achados** (+ 6 itens de status de dívida + 9 gaps de teste) |

Os três mais urgentes: (1) bypass de aprovação para categoria `destructive` em todas as camadas determinísticas (deleção auto-executa no modo fluido e via corretor); (2) esgotamento por divergência geométrica reportado como sucesso (`running`/`EXECUTION_COMPLETED` — RF-011/CS-003); (3) rollback de RF-011 nunca injetado no caminho vivo (sempre `rollback_skipped`), apesar do primitivo de rollback de timeline já existir para o undo de edição.


---

# ANEXO: security-policy.md

# Auditoria — Módulo 3D: Segurança, Policy, Snapshots, Auditoria e Observabilidade

Repositório: raiz | Data: 2026-06-10
Referências: spec 005 (RF-016..026, RNF-001/003, DT-005/DT-009), `observability-plan.md`, constituição P6/P8, AGENTS.md "Modelagem 3D", ADR-019/020/021/022/023.
Contexto: suíte pytest do backend 100% verde (678 testes) — os achados abaixo são compatíveis com isso (os testes pinam o comportamento atual, inclusive o defeituoso).

---

## Bugs

### [SEVERIDADE: crítica] Categoria `destructive` não tem enforcement — deleção pode auto-executar sem aprovação humana
- **Arquivos**: `backend/app/modeling/tool_registry.py:712-733`, `backend/app/modeling/policy.py:104-111`, `backend/app/modeling/chat_orchestrator.py:1093-1101`, `backend/app/modeling/planner.py:1231-1235`
- **Evidência**:
  - `tool_registry.requires_approval`: checa `is_blocked` → `is_read_only` → `is_high_risk` → `risk_level == high`. **Nunca checa `ToolCategory.destructive`**, embora a docstring do enum prometa: `destructive — removes geometry/files. Always requires approval.` (tool_registry.py:50).
  - `policy.apply_modeling_policy`: `requires_approval = not is_read_only and is_high_risk` (policy.py:105) e **sobrescreve** `approval_required` do step (policy.py:111) — ou seja, mesmo que o LLM marque honestamente `approval_required=true` para `fusion.delete_body` com `risk_level=medium`, a policy **remove** a exigência e rebaixa o step de `waiting_approval` para `pending` (policy.py:109-110).
  - `planner._risk_level` default = `low` quando o LLM omite/erra o campo (planner.py:1232-1234).
  - `fusion.delete_body` e `fusion.rollback_timeline` são `destructive` (tool_registry.py:534-544); `delete_body` está no `PLANNER_TOOLSET` (pinado em `tests/test_tool_registry.py:189`) — o LLM pode planejá-lo.
  - No fluxo fluido de edição, `chat_orchestrator._plan_has_high_risk` (1093-1101) só vê `risk_level==high`, `is_high_risk` e `approval_required` (já zerado pela policy) → uma edição "remova o corpo X" com `delete_body` risk `low/medium` **auto-executa** (`propose_edit_plan`, chat_orchestrator.py:1002-1029).
  - `fusion_mcp_scripts.py:3306-3307` comenta "Exige aprovacao humana (categoria destructive na policy)" — **a policy não faz isso**.
  - `executor._run_expanded_steps` (executor.py:657-661) bloqueia expansão F7 com concretos `high_risk`/`blocked`, mas a docstring fala "high_risk/destrutivo" e o código **não checa destructive**.
- **Violação**: P6 ("Alterações e deleções exigem aprovação humana"), P8, AGENTS.md "Modelagem 3D" ("Preserve human-in-the-loop para deleções"), RNF-003, RF-022.
- **Impacto**: deleção de geometria sem aprovação humana no caminho feliz — a única defesa real é o prompt do planner pedir `risk_level` correto (planner.py:926-928), que não é enforcement.

### [SEVERIDADE: alta] Guard de correção do loop promete rejeitar tool "destrutiva" mas não rejeita
- **Arquivo**: `backend/app/modeling/planner.py:604-614` (`_corrected_step_from_payload`)
- **Evidência**: comentário: "Se a 'correção' trocar o tool por um destrutivo/high-risk (ex.: delete_body, combine_bodies), ela NÃO pode auto-executar — rejeitamos". O código usa `requires_approval(tool_name, step.risk_level)`, que retorna `False` para `fusion.delete_body` com risk `low/medium` (mesma raiz do bug crítico).
- **Violação**: P6/P8; RF-023 (operação destrutiva no caminho feliz).
- **Impacto**: um delta corretivo do loop agêntico pode trocar o passo por `delete_body` e re-executar imediatamente (`agent_loop.run` re-executa o corrected sem nova policy), deletando geometria sem aprovação.

### [SEVERIDADE: alta] `ModelingTraceLevel.warning` não existe — AttributeError quebra o retry do planner async
- **Arquivo**: `backend/app/modeling/planner_service.py:554` vs `backend/app/core/contracts.py:1448-1452`
- **Evidência**: `_build_plan_async` no retry: `level=ModelingTraceLevel.warning` — o enum só tem `debug/info/warn/error`. O caminho síncrono usa `warn` correto (planner_service.py:496).
- **Violação**: RF-024 (trace correto); objetivo central do observability-plan (diagnosticar fallback do planner).
- **Impacto**: na primeira falha do LLM no caminho async, o `AttributeError` é capturado pelo `except` externo (linha 564), **pulando o retry F6** e registrando `fallback_reason` derivado do AttributeError em vez do erro real do provedor — exatamente a classe de falha silenciosa ("uma bola → retângulo") que o plano de observabilidade nasceu para eliminar. Nenhum teste cobre o retry async (suíte verde com o bug).

### [SEVERIDADE: média] `sequence` de trace pode duplicar dentro do mesmo trace (dedupe SSE×GET quebrável)
- **Arquivo**: `backend/app/modeling/observability.py:70-72, 247, 366-367`; uso em `backend/app/api/routes/chat_modeling.py:324, 365, 487, 500`
- **Evidência**: `_sequence_var` é `contextvars.ContextVar`. `asyncio.to_thread` executa com **cópia** do contexto: incrementos feitos dentro do thread (orchestrator/planner/executor) não retornam ao contexto pai. A rota de chat abre o trace no contexto async e despacha trabalho em múltiplos `to_thread`; eventos gravados depois (ou num segundo `to_thread`) reusam os mesmos números. Além disso, `start_trace(existing_trace_id=...)` reseta `_sequence_var.set(0)` (linha 247) reiniciando a numeração do mesmo trace.
- **Violação**: contrato do `ModelingTraceEvent.sequence` ("monotônico dentro do trace para dedupe SSE vs GET", observability-plan + contracts.py:1486-1488).
- **Impacto**: timeline do modal pode desordenar/deduplicar eventos errados; o endpoint ordena por `(sequence, created_at)` o que mitiga, mas o dedupe por sequence no frontend pode descartar eventos legítimos.

### [SEVERIDADE: média] Singleton `get_tracer` é ordem-dependente — primeira chamada sem store cala a persistência para sempre
- **Arquivo**: `backend/app/modeling/observability.py:684-697`; chamadas sem store em `backend/app/modeling/mcp_client.py:237, 275`
- **Evidência**: "A store é injetada na primeira chamada e cached. Chamadas subsequentes ignoram o parâmetro" — se `get_tracer()` (sem store) rodar primeiro (ex.: erro stdio no `LocalMCPClient` antes de qualquer serviço construído, ou uso direto), o tracer global fica com `_store=None` e **todos** os flushes futuros descartam eventos silenciosamente, mesmo quando executor/rotas passam a store correta.
- **Violação**: RF-024 (trace persistido), observability-plan ("observabilidade não pode ser fonte de incidente" — aqui ela falha silenciosa).
- **Impacto**: traces vazios não-determinísticos conforme a ordem de import/uso; difícil de diagnosticar (a própria ferramenta de diagnóstico é a vítima).

### [SEVERIDADE: baixa] Passo `project_store.restore_snapshot` "executa" como mock ok:True sem restaurar nada
- **Arquivo**: `backend/app/modeling/executor.py:902-908` + `backend/app/modeling/mcp_client.py:180-195`
- **Evidência**: `_dispatch_step` só trata `project_store.create_snapshot` inline; `restore_snapshot` (high_risk, registrada no registry) cai no `mcp_client._execute_step_in_process`, que devolve `{"ok": True, "transport": "mock", ...}` para qualquer tool não-blender/fusion.
- **Violação**: RF-022 (allowlist de fonte única com handler coerente); caso de borda da spec ("sem fingir sucesso").
- **Impacto**: um plano contendo o passo de restore reporta sucesso (com verb "preparado") sem efeito; o restore real só existe via `ModelingSnapshotService.restore` (rota). Confusão de contrato, baixo risco prático (tool fora do PLANNER_TOOLSET).

### [SEVERIDADE: baixa] Eviction FIFO de buffers de trace pode evictar trace ATIVO
- **Arquivo**: `backend/app/modeling/observability.py:514-531`
- **Evidência**: ao atingir `DEFAULT_MAX_BUFFERS`, evicta `next(iter(self._buffers))` — o mais antigo por inserção, não por inatividade; um trace longo (execução de plano grande) pode ser evictado enquanto ativo (flush antecipado, sem perda de dados, mas o trace fica fragmentado em múltiplos flushes).
- **Impacto**: menor; só sob pressão de ~1000 traces vazados.

### [SEVERIDADE: baixa] Snapshots/cópias de workspace sem limite de tamanho
- **Arquivo**: `backend/app/modeling/workspace.py:60-73`, `backend/app/modeling/snapshot_service.py:49-118, 154-166`
- **Evidência**: `copy_into_snapshot`/`restore_from_snapshot` copiam tudo sem cota/limite; AGENTS.md exige "timeout, limite de tamanho, auditoria e rollback" para tools de escrita. Timeouts existem (subprocess Blender `modeling_subprocess_timeout_seconds`; HTTP Fusion 30s — fusion_adapter.py:128), auditoria existe; **limite de tamanho não**. Cada restore sem `force` ainda cria um snapshot automático extra.
- **Impacto**: exaustão de disco possível por snapshots repetidos de workspaces grandes. (Path traversal está coberto: `safe_segment`, `is_inside` no restore — snapshot_service.py:151.)

---

## Incongruências spec×código

### [SEVERIDADE: alta] RF-011 — o rollback "ao último estado seguro" não existe em produção
- **Arquivos**: `backend/app/modeling/agent_loop.py:414-427` (`run_plan_with_optional_loop`), `agent_loop.py:221-232` (`_do_rollback`)
- **Evidência**: o `ModelingAgentLoop` aceita `rollback=` injetável, mas **nenhum call site de produção injeta** (orchestrator `_run_execution` → `run_plan_with_optional_loop`; `service.execute_plan` idem) — só o teste injeta (`tests/test_agent_loop.py:152`). Ao esgotar as 5 iterações, `_do_rollback` registra `agent_loop.rollback_skipped` ("nenhum mecanismo de reversão injetado") e segue. Além disso, **nenhum snapshot automático é criado antes da execução** (nem o planner emite `project_store.create_snapshot`, nem o orchestrator chama `snapshots.create`) — não há "último estado seguro" para reverter.
- **Violação**: RF-011, P8 ("rollback explícito... são contrato"), RNF-003; cenário de aceitação 3 da História 1.
- **Impacto**: em falha irrecuperável o modelo fica no estado intermediário inconsistente; o trace ao menos registra o skip (não é silencioso, mas é inefetivo).

### [SEVERIDADE: alta] DT-005 — status real PIOR que o documentado: snapshot de filesystem não captura o modelo Fusion
- **Arquivos**: `backend/app/modeling/snapshot_service.py` (todo), `backend/app/modeling/workspace.py:60-125`, `backend/app/modeling/fusion_mcp_scripts.py:3851`
- **Evidência**: snapshot continua sendo cópia do workspace local (`.local/modeling/workspaces/...`). O estado do Fusion vive no host (documento + exports em `tempfile.gettempdir()` do host) — o workspace não contém o modelo; restaurá-lo não altera o Fusion. O único rollback efetivo no Fusion é `fusion.rollback_timeline` via `rollback_marker` (T3.6), limitado à "última edição" e capturado best-effort. DT-005 ("redesenhar na Fase 2") segue aberto; a Fase 2 entregou o loop, não o rollback nativo.
- **Violação**: DT-005/RF-011/P8.
- **Impacto**: "GeometrySnapshot: estado salvo para rollback" (entidade da spec) é ilusório para o software principal do produto.

### [SEVERIDADE: alta] RF-026 — destino de impressão não persiste, printability não dispara e artifacts do Fusion não são registrados
- **Arquivos**: `backend/app/core/contracts.py:402-404`, `backend/app/modeling/printability.py:32-55`, `backend/app/modeling/artifacts.py:59-77,166-167`, `backend/app/modeling/fusion_mcp_scripts.py:3843-3876`
- **Evidência** (3 sub-gaps):
  1. O chat 3D não tem campo de destino de impressão (`is_modeling_3d`/`modeling_software_preference`/`modeling_stage` apenas), embora a entidade "Chat 3D" da spec exija "preferência de software e **destino de impressão**". A descoberta pergunta sobre impressão (discovery_system.md:27), mas a resposta não vira estado consultável.
  2. Relatório de printability só nasce via `POST /api/3d/validate/printability` (manual) e **hardcoded** em `blender.validate_printability` (printability.py:37); quando `fusion.validate_printability` roda como passo de plano, o resultado fica só no tool_call — **nenhum `ModelingPrintabilityReport` é persistido** nesse caminho.
  3. Exports do Fusion são gravados em `tempfile.gettempdir()` **do host Windows**; `artifacts.register_outputs` só promove paths dentro de `settings.data_dir` (artifacts.py:73,166-167) e, no container, `path.is_file()` é falso → export STL/STEP/3MF do Fusion **nunca vira PlatformFile/ModelingModelVersion**. O registro de artifacts funciona de fato apenas para o Blender (congelado).
- **Violação**: RF-026; P8 ("printability são parte do contrato"); entidade Artifact/PrintabilityReport da spec.
- **Impacto**: o requisito "registrar artifact e relatório de printability quando destino=impressão" depende de ação manual do dono e está estruturalmente quebrado para o Fusion.

### [SEVERIDADE: média] RF-009/DT-010 — delta corretivo high-risk não é "coberto pela aprovação do plano": é rejeitado
- **Arquivo**: `backend/app/modeling/planner.py:604-614` vs spec RF-009 ("A cobertura inclui os deltas corretivos... o loop não pausa para reaprovar correções high-risk — decisão do dono, 2026-05-23")
- **Evidência**: `_corrected_step_from_payload` **rejeita** qualquer correção que `requires_approval` (high-risk) — o loop cai em "sem correção", esgota e falha. Não pausa (ok), mas também não executa o delta HR que o RF-009 diz estar coberto pela aprovação única.
- **Violação**: RF-009 (interpretação divergente, resolvida a favor da constituição P6 sem atualizar a spec/DT-010).
- **Impacto**: planos cuja correção natural é um boolean (`combine_bodies`) falham sistematicamente em vez de se autocorrigirem; comportamento defensável (P6) mas em contradição documental com a decisão do dono registrada na spec.

### [SEVERIDADE: média] Observability-plan — 4 pontos de instrumentação obrigatórios ausentes
- **Arquivos**: `backend/app/modeling/policy.py`, `snapshot_service.py`, `chat_state.py`, `attachment_analyzer.py` (nenhum importa `observability`)
- **Evidência**: a tabela "Pontos de instrumentação obrigatórios" exige `policy.decision` ("sempre"), `snapshot.write_failed`/`snapshot.restore_failed`, `state.transition` e `attachment.analysis_failed`. Nenhum desses módulos emite trace events (verificado por grep: zero referência ao tracer nos 4 arquivos).
- **Violação**: observability-plan §"Pontos de instrumentação obrigatórios"; RF-024 parcial.
- **Impacto**: decisões da policy (ex.: degradar/bloquear step) e falhas de snapshot são invisíveis no trace — justamente a classe "guard X bloqueou e ninguém viu" que o plano queria expor. (Retention job: corretamente fora de escopo, config reservada em config.py:365-369 — OK.)

### [SEVERIDADE: média] RF-022/RNF-003 — divergências residuais na "allowlist de fonte única"
- **Arquivos**: `backend/app/modeling/executor.py:902`, `backend/app/modeling/tool_registry.py:492-520, 712-733`, `backend/app/modeling/mcp_client.py:180-195`
- **Evidência**:
  1. `project_store.create_snapshot` tem handler ativo no executor mas **não existe no TOOL_REGISTRY** (registry só tem `restore_snapshot`/`list_snapshots`) — tool executável fora da fonte única (a policy a trata como desconhecida: nem read-only nem high-risk).
  2. Tools F7/F8 que movem/alteram corpos existentes (`fusion.place_body`, `fusion.align_axis`, `fusion.distribute_along`, `fusion.relate_bodies`) estão categorizadas `additive`, embora `place_body` seja descrito como "move_body determinístico" e `distribute_along` faça combine-DENTRO — a categoria alimenta a proveniência (`provenance._disappeared_op`) e a leitura de risco.
  3. A policy não rejeita tool desconhecida (pinado em `tests/test_tool_registry.py:335-337`: "caller is expected to reject"); as defesas reais são o enum do planner + a checagem dos adapters — mas com adapter desconectado, um step com tool inexistente devolve mock `ok: True` (`mcp_client.py:185-195`).
- **Pontos positivos confirmados**: `run_script` fora de `FUSION_TOOLS`/`BLENDER_TOOLS`/`PLANNER_TOOLSET` (RF-023 ok); `DEPRECATED_PLANNER_TOOLS` (ADR-020) fora do planner e do render de schema (`tool_schemas.py:1022`) e inacessíveis via `edit_plan` (valida contra PLANNER_TOOLSET, service.py:260); `UNRELEASED_PLANNER_TOOLS` dark; corretor e parser do plano re-validam contra PLANNER_TOOLSET (planner.py:598, 1167).
- **Impacto**: drift baixo hoje, mas o contrato "uma fonte" tem furos auditáveis.

### [SEVERIDADE: baixa] Audit de aprovação/snapshot/printability sem `trace_id`
- **Arquivos**: `backend/app/modeling/chat_orchestrator.py:1131-1136`, `backend/app/modeling/service.py:228-233`, `snapshot_service.py:106-117,184-197`, `printability.py:55-67`
- **Evidência**: `modeling.plan_approved/_rejected`, `modeling.snapshot_created/_restored`, `modeling.printability_validated` não anexam `trace_id` (o campo existe no contrato e é usado em `plan_created`, `plan_executed`, `agent_loop_executed` e no `_audit` do orchestrator).
- **Violação**: observability-plan §AuditEvent (navegação bidirecional trace↔audit).
- **Impacto**: navegação audit→trace incompleta nos eventos de aprovação e snapshot.

### [SEVERIDADE: baixa] DT-009/ADR-019 — fronteira do script OK, mas o transporte default segue sem auth
- **Arquivos**: `backend/app/modeling/fusion_adapter.py:478-497`, `fusion_mcp_scripts.py:92-99, 3839-3852`, `backend/app/modeling/mcp_standalone/auth.py`
- **Evidência (positiva)**: a fronteira ADR-019 está implementada — script backend-owned; args entram via `json.loads({repr(json.dumps(...))})` (dados, nunca código — sem injeção); export `target` sanitizado contra traversal/caminho absoluto (fix mdl-adapters-004, fusion_mcp_scripts.py:3839-3852); `run_script` inalcançável pelo planner/adapters; o servidor MCP standalone exige Bearer token; o `POST /traces/events` força `source=ui`, aplica rate-limit e truncate server-side (routes/modeling.py:359-442).
- **Gap**: o transporte default (`in_process`) executa via Autodesk MCP `127.0.0.1:27182` **sem autenticação**; o caminho autenticado (standalone, `mcp_http`) não é o default. O ADR-019 nomeia esse gap como "defeito a corrigir na Fase 1" — segue aberto no caminho default.
- **Impacto**: qualquer processo local pode falar com o 27182 e executar script no Fusion — risco local-first aceito, mas em aberto contra RNF-001/ADR-019.

---

## Dívidas documentadas não resolvidas (status real)

- **DT-005 (snapshot/rollback = cópia de filesystem)** — **ABERTA e subestimada**: além de o snapshot não capturar o estado do Fusion, o hook de rollback do loop agêntico nunca é injetado em produção (`rollback_skipped` sempre) e nenhum snapshot automático precede a execução. O único rollback real é `fusion.rollback_timeline` por marker (última edição, best-effort). Ver incongruências RF-011/DT-005 acima.
- **DT-009 (script backend-owned / `featureType:"script"`)** — **PARCIALMENTE RESOLVIDA**: ADR-019 formalizado e os controles técnicos do script estão implementados e sólidos (sem injeção via args; `run_script` fora de todas as superfícies; traversal de export corrigido). O gap de auth do loopback 27182 permanece no transporte default; auth só existe no standalone (não-default).
- **DT-010 (loop bloqueava delta corretivo high-risk)** — **SUPERADA COM TORÇÃO**: o loop não pausa mais e dispara correção também em divergência geométrica (agent_loop.py:114-115). Porém a correção high-risk é **rejeitada** em vez de coberta pela aprovação do plano, divergindo do texto do RF-009 (ver incongruência média acima) — e o guard que faz essa rejeição não cobre `destructive` (bug alto).

---

## Gaps de teste

1. **[T1] Categoria `destructive` sem nenhum caso de teste** — `tests/test_tool_registry.py:323-340` cobre high_risk/read_only/blocked/unknown, mas nunca `fusion.delete_body`/`fusion.rollback_timeline` em `requires_approval`/`apply_modeling_policy`/`_plan_has_high_risk`. É o gap que mascara o achado crítico.
2. **[T2] RF-011 sem teste do caminho de produção** — `tests/test_agent_loop.py:147-159` injeta `rollback=` manualmente; nenhum teste verifica que `run_plan_with_optional_loop` (o caminho real) reverte algo ao esgotar — se houvesse, o `rollback_skipped` permanente apareceria.
3. **[T3] Retry async do planner sem teste** — `_build_plan_async` com falha na 1ª tentativa nunca é exercitado; o `ModelingTraceLevel.warning` (AttributeError) cairia com um único caso.
4. **[T4] Unicidade/monotonicidade de `sequence` sem teste cross-contexto** — nenhum teste cobre trace atravessando `asyncio.to_thread`/requests múltiplos (contrato de dedupe SSE×GET).
5. **[T5] Efetividade do restore de snapshot sobre o estado do modelo** — `tests/test_modeling_rollback.py` cobre marker/rota/metadata; nada verifica (nem documenta como invariante) que restaurar um snapshot NÃO devolve o modelo Fusion (DT-005).
6. **[T6] `fusion.validate_printability` como passo não persiste report** — `tests/test_fusion_printability_logic.py` testa só a lógica pura do script; nenhum teste cobre a ponta RF-026 (passo de plano → `ModelingPrintabilityReport` persistido), que hoje não existe.
7. **[T7] Registro de artifacts do Fusion** — nenhum teste cobre `artifacts.register_outputs` com paths de export do Fusion (tempdir do host); o skip silencioso (path fora de `data_dir`) seria detectado.

---

## Resumo

| Severidade | Qtde | Achados |
|---|---|---|
| Crítica | 1 | `destructive` sem enforcement (deleção auto-executa; policy ainda remove `approval_required` honesto do LLM) |
| Alta | 5 | guard de correção não cobre destructive; `ModelingTraceLevel.warning` (AttributeError no retry async); RF-011 rollback nunca injetado + sem snapshot pré-execução; DT-005 pior que documentado; RF-026 (destino, report e artifacts Fusion) |
| Média | 5 | sequence duplicável (contextvar × to_thread); singleton `get_tracer` ordem-dependente; RF-009 × rejeição de correção HR; 4 pontos de instrumentação obrigatórios ausentes; furos residuais na allowlist de fonte única |
| Baixa | 6 | restore_snapshot step mock ok:True; eviction FIFO de trace ativo; sem limite de tamanho em snapshots; audit sem trace_id em aprovação/snapshot; auth ausente no transporte default 27182; mock ok:True para tool desconhecida (agregado à allowlist) |
| Gaps de teste | 7 | T1–T7 |

**Pontos sólidos confirmados** (não-achados): fronteira ADR-019 do script backend-owned bem implementada (args como dados; traversal de export sanitizado); `run_script` inalcançável em todas as superfícies (RF-023 ok no desenho); steps bloqueados nunca executam mesmo após aprovação (executor pula step com `error`); gate "nunca executa plano não aprovado" no fluxo split (chat_orchestrator.execute_plan:623); aprovação única do plano + `ModelingToolCall` persistido por passo + audit por plano (RF-022 auditoria ok no núcleo); endpoints de trace com `source=ui` forçado, rate-limit e truncate server-side; auth Bearer no MCP standalone; expansão F7 bloqueia concretos high_risk fail-safe antes de executar qualquer passo.


---

# ANEXO: adapters-mcp.md

# Auditoria — ADAPTERS (Fusion/Blender) e camada MCP do módulo 3D

Repositório: raiz · Spec: specs/005-modeling-3d-fusion · pytest 100% verde (678 testes), container = mock.

## CRÍTICA
Nenhum. As fronteiras de segurança centrais estão de pé: script backend-owned/determinístico (ADR-019), `fusion.run_script` nunca exposto, auth do servidor standalone com Bearer + `compare_digest` timing-safe e loopback default, RF-018 honrado no gerador.

## ALTA
- **A1. Bridge legado (add-in) conhece só 11 das ~55 tools e diverge do caminho HTTP** — `apps/fusion-addin/TruthsForge.py:86-98`. O adapter valida contra a allowlist completa do registry (`fusion_adapter.py:414`) e encaminha qualquer tool ao add-in, que rejeita add_cylinder/revolve/fillet/thread/superfícies com `fusion.tool_not_allowlisted`. Pior: o add-in tem handlers próprios divergentes (não usa o script ADR-019) — `_add_circle` só `center_x_mm/center_y_mm`, `_extrude_profile` sem cut negativo nem seletor de perfil, sem aliases/expressões/as_surface/batch. No Fusion real **sem** o MCP oficial (só add-in), a maioria dos planos falha. Doc trata o bridge como "fallback equivalente".
- **A2. Add-in compara token com `!=` (não timing-safe)** — `TruthsForge.py:554`. O servidor standalone usa `compare_digest`; o bridge não. Inconsistência de invariante (RNF-001/ADR-019), mitigada por loopback.
- **A3. `fusion.relate_bodies` exposto pelo MCP standalone mas inexecutável** — está em `FUSION_TOOLS` (registry, `tool_registry.py:514`) → aparece no `tools/list` de clientes externos, mas falta em `FUSION_SCRIPT_TOOLS` (`fusion_mcp_scripts.py:7-64`); via HTTP vira `ValueError "fora da allowlist"` → `fusion.autodesk_mcp_error` + penaliza a saúde do adapter. Atenuante: é UNRELEASED/dark e o resolver o expande antes do dispatch quando a flag está ON.

## MÉDIA (11)
- M1. Mock do Fusion devolve `ok:True` (fusion_server/standalone/in-process) → executor marca verde; diverge do Blender (que devolve `ok:False`) — RF-002 mascarado.
- M2. `validate_printability` tem duas implementações divergentes por transporte (script hardcoded/ignora profile × `printability_logic` profile-aware).
- M3. Análise headless de arquivo 3D (RF-004) não-funcional: `source_path` é injetado mas o `blender_runner` nunca o lê (mede cena vazia).
- M4. Análise de `.step` é stub permanente (analyzer nem recebe FusionAdapter).
- M5. Timeouts em camadas inconsistentes (adapter 30s × add-in main-thread 120s).
- M6. `_eval_param` multiplica todo userParameter por 10, errado para args contáveis/angulares (cols/rows/sides/count).
- M7. G1.3 não resolvido: default silencioso para expressão inválida.
- M8. DT-002/G1.1 parcial: primitivas (box/cylinder/sphere/cone) ainda "assam" via `createByReal`.
- M9. `validate_dimensions` devolve cm enquanto o resto fala mm.
- M10. StandaloneMCPClient abre nova sessão MCP (handshake) por tool call.
- M11. Sem teste de contrato cross-layer (registry × schemas × scripts), exatamente o que `fusion-operations.md §5` prescreve — foi o que deixou A3 passar.

## BAIXA (7)
- B1. Exports via HTTP gravam no temp do host → não viram PlatformFile.
- B2. `capture_viewport` usa path fixo (race).
- B3. Macros deprecadas engolem falha do combine.
- B4. stdio timeout fixo 60s < subprocess Blender 90s.
- B5. Subset stdio (`protocol.py`) não foi aposentado como o ADR-017 mandou.
- B6. ThreadPoolExecutor por chamada.
- B7. Gaps de teste pontuais (addin allowlist, caminhos de erro declarativos, consumo real do anexo).

## Confirmações positivas
Auth do servidor standalone (RF-020/021/RNF-001) está correta: sem token hardcoded, sem rota sem auth, sem timing attack, loopback default, backend é mesmo só um cliente. Defesa de injeção (json.loads runtime) de pé. `_unwrap_inner_fusion_result` trata o `ok:false` mascarado do HTTP. Blender congelado-mas-mantido não mente status.

**Total: 21 achados — 0 crítica, 3 alta, 11 média, 7 baixa.**

Arquivos-chave: `backend/app/modeling/fusion_mcp_scripts.py`, `fusion_adapter.py`, `mcp_client.py`, `mcp_servers/fusion_server.py`, `mcp_standalone/{server,client,auth,app}.py`, `attachment_analyzer.py`, `blender_runner.py`, `tool_registry.py`, `tool_schemas.py`, `apps/fusion-addin/{TruthsForge.py,printability_logic.py}`.


---

# ANEXO: frontend.md

# Auditoria — Frontend do módulo de Modelagem 3D (apps/web/src/features/modeling-3d)

Data: 2026-06-10 · Base: specs/005-modeling-3d-fusion/spec.md (v4), chat-flow-redesign.md, docs/3d-modeling-debug.md · Testes da feature executados: 7 arquivos / 49 testes — todos verdes.

Verificações positivas (sem achado):
- RF-006 está implementado nos 3 caminhos: o card oferece Aprovar, Rejeitar **com justificativa obrigatória** (textarea + confirmação desabilitada sem motivo) e **Editar plano**; a edição NÃO é só visual — `handleSaveEdit` → `onEditPlan` → `modeling3dApi.editPlan` → `PATCH /api/3d/plans/{id}` (ModelingPlanCard.tsx:203-237; api/index.ts:70-74; App.tsx:620-627).
- Unidades mm/cm: não há conversão de unidades no frontend (format.ts só trata duração/percentual/timestamp); argumentos dimensionais são exibidos como JSON cru (`distance_mm` etc.) — nenhum bug de mm×cm encontrado.
- `useModeling3dTrace` é chamado com a ordem correta de argumentos no modal; rejeição local limpa o formulário; edição valida JSON antes de enviar.

---

## Bugs

1. **[SEVERIDADE: crítica] Card de plano "ressuscita" aprovável após recarregar o chat — permite re-executar plano já concluído** — apps/web/src/App.tsx:551-569 (applyPlanToSession só em memória) + backend/app/api/routes/chat_modeling.py:542-546 (`assistant_message.metadata["modeling_plan"] = plan_metadata` persistido uma única vez, em `waiting_approval`) + backend/app/modeling/policy.py:64-88 (`apply_plan_approval` sem guarda de status terminal) — evidência: o card lê `metadata.modeling_plan` da mensagem persistida (app-chat.tsx:262-299); após aprovar/executar, nem o backend atualiza o metadata da mensagem nem o frontend reconcilia via `GET /plans/{id}` ao recarregar a sessão; `isApprovable()` (ModelingPlanCard.tsx:115-117) volta a exibir "Aprovar" para um plano que já rodou, e `POST /approve` + `/execute` re-executam sem nenhum 409 — violação: RF-008/RF-022 (aprovação única auditável; execução fim-a-fim controlada), História 2 — impacto: um clique em um card histórico re-executa todos os passos (inclusive high-risk cobertos pela aprovação antiga) sobre o design ativo do Fusion, duplicando/corrompendo geometria sem aviso.

2. **[SEVERIDADE: alta] Justificativa de rejeição é coletada pela UI e descartada pelo backend** — apps/web/src/features/modeling-3d/components/ModelingPlanCard.tsx:493 (placeholder: "Explique o que falta ou está errado para o agente voltar para descoberta.") + api/index.ts:60-64 (`rejectPlan` → `POST /approve {decision:"reject", reason}`) — evidência: a rota REST usa `ModelingService.approve_plan` (backend/app/api/routes/modeling.py:104-109 → service.py:221-234), que aplica `apply_plan_approval` e **só audita quando `decision != reject`**; a `reason` não vai para o plano, nem para auditoria, nem para o histórico do chat — o discovery do turno seguinte (chat_modeling.py:370-379) lê apenas mensagens user/assistant e nunca vê a justificativa; o caminho do orquestrador que trata a razão (`reject_plan`, chat_orchestrator.py:690-724) não é chamado pelo card — violação: RF-007 ("retomar a descoberta usando a justificativa"), História 2 cenário 2 — impacto: a promessa da UI é falsa; o motor replaneja às cegas e o usuário repete a explicação.

3. **[SEVERIDADE: média] Ternário morto: execução que falha leva o estágio local para "editing"** — apps/web/src/App.tsx:575 — evidência: `const next = execution.plan.status === "failed" ? "editing" : "editing";` (os dois ramos são iguais) — violação: DT-008/RF-011 (estado `failed` existe justamente para distinguir falha de sucesso; `ChatModelingStage.failed` em contracts.py:386) — impacto: o estado local da sessão diverge do backend após falha; código claramente não-intencional.

4. **[SEVERIDADE: média] Evento SSE `modeling_plan` marca estágio "executing" para plano aguardando aprovação** — apps/web/src/App.tsx:1306-1307 — evidência: `modeling_stage: plan.status === "completed" ? "editing" : plan.status === "failed" ? "failed" : "executing"` — no fluxo P1 o plano chega em `waiting_approval` (chat_modeling.py:513-528), caindo no ramo "executing" — violação: chat-flow-redesign §3 (após propose o chat fica em `planning`, STOP) — impacto: estado local incorreto (planejando ≠ executando); qualquer UI futura que leia `modeling_stage` exibirá modo errado.

5. **[SEVERIDADE: média] Estado "Execução em andamento" do card é inalcançável no fluxo real; sem feedback durante a execução** — apps/web/src/features/modeling-3d/components/ModelingPlanCard.tsx:119-121, 526-531 + hooks/useModelingPlanActions.ts:123-137 — evidência: o bloco "executando" só renderiza com `plan.status === "running"`, mas o cliente nunca recebe esse status — `approve()` faz `approvePlan` + `executePlan` (REST síncrono) sem atualizar `lastPlan` para um estado intermediário, e não há SSE de progresso (comentário em App.tsx:549-550: "We don't yet receive a dedicated SSE stream for plan execution") — violação: História 1/RF-008 (acompanhar execução fim-a-fim), chat-flow-redesign §3 — impacto: durante execuções longas (minutos no Fusion real) o usuário vê apenas botões desabilitados, sem spinner nem passos ao vivo; o texto "acompanhe os passos acima" nunca aparece.

6. **[SEVERIDADE: média] Preferência de software 3D é descartada a cada novo chat** — apps/web/src/features/modeling-3d/store.ts:33-39 (`resetForNewChat` → `software: "auto"`) + App.tsx:2091 (chamado em `startNewChat`) — evidência: Modeling3DSettingsSection.tsx:14-16 promete "Esta seção define o adapter preferido para próximos chats 3D", mas a escolha vive só no zustand transiente e é zerada em todo novo chat (sem persistência em localStorage/backend) — violação: RF-001 (preferência de software é parte da identidade da sessão 3D) — impacto: o usuário configura "fusion" nas configurações e o próximo chat volta a "auto" silenciosamente.

7. **[SEVERIDADE: média] `trace_id` nunca é passado ao modal de diagnóstico — eventos de UI nunca são gravados e o trace exibido perde os spans do planner** — apps/web/src/App.tsx:2227-2233 (`<ModelingDiagnosticsModal planId={...} projectId={...}` sem `traceId`) + hooks/useModeling3dTrace.ts:52-77 (`useRecordClientTrace` → `if (!traceId) return;`) — evidência: o backend envia `trace_id` no metadata SSE do plano (chat_modeling.py:89-94) e o tipo o documenta (types/api.ts:116-119), mas App.tsx nunca o extrai; com `traceId` undefined, `record("ui.diagnostics_modal_opened", ...)` (ModelingDiagnosticsModal.tsx:79-80) é no-op permanente, e o trace cai no filtro por `plan_id` que perde os spans do planner gravados com plan_id nulo (gotcha documentado em docs/3d-modeling-debug.md §4/"Trace aparece vazio?") — violação: RF-024/História 6 (trace por passo acessível) — impacto: observabilidade da UI morta; diagnóstico mostra trace incompleto exatamente nos casos de falha de planejamento.

8. **[SEVERIDADE: baixa] `handleRollback` sem tratamento de rejeição** — apps/web/src/features/modeling-3d/components/ModelingEditCard.tsx:64-73 — evidência: `try { const ok = await onRollback(plan.id); ... } finally { setPending(false); }` sem `catch`; se um consumidor passar um callback que lança, vira unhandled rejection (o handler atual de App.tsx nunca lança porque `wrap` engole, mas o contrato do prop `Promise<boolean> | void` não garante isso) — violação: princípio "erros silenciosos" (RNF-006) — impacto: erro de rollback pode sumir sem render de erro no card.

9. **[SEVERIDADE: baixa] Janela de reconciliação pós-queda de rede é curta demais (≈7,5 s)** — apps/web/src/features/modeling-3d/hooks/useModelingPlanActions.ts:79-99 — evidência: 5 tentativas × 1,5 s; execuções reais no Fusion levam minutos — se a conexão cair no início, o poll desiste com o plano ainda `running` e propaga "Failed to fetch" — violação: intenção do próprio comentário ("corrige o 'a UI diz que falhou mas a peça saiu certa'") — impacto: falso negativo de falha volta a acontecer em execuções longas.

10. **[SEVERIDADE: baixa] Diagnóstico busca dados que nunca exibe e não atualiza durante execução** — apps/web/src/features/modeling-3d/hooks/useModeling3dDiagnostics.ts:10-17 + components/ModelingDiagnosticsModal.tsx — evidência: `plans: modeling3dApi.plans()` (lista TODOS os planos, sem filtro/limite) entra no bundle e o modal nunca renderiza `diagnostics.plans`; nem o trace nem o diagnóstico têm `refetchInterval` (o comentário de useModeling3dTrace.ts:17-19 fala em "polling on-demand", mas staleTime≠polling) — impacto: payload desperdiçado e modal congelado enquanto uma execução corre em paralelo.

## Incongruências spec×código

11. **[SEVERIDADE: alta] Relatório esperado×medido (verificação geométrica) não é exibido em lugar nenhum da UI** — apps/web/src/features/modeling-3d/components/ModelingDiagnosticsModal.tsx:131-289 — evidência: o modal mostra Trace, Adapters, Tool calls, Printability e Versões; o backend produz `ModelingPlan.model_verdict` (`ModelVerdict` com `findings[].expected/measured`, contracts.py:1035-1052, 1179-1185) e `model_state`, mas o frontend não os tipa, não os busca e não os renderiza; o `ModelingExecutionResult.events` e `blocked_step_ids` retornados pelo execute também são descartados (App.tsx:571-578 usa só `execution.plan`) — violação: RF-013 ("disponibilizar relatório esperado × medido ao usuário"), RF-024, História 3/6, CS-004 — impacto: o mecanismo central de fidelidade ("ficou exatamente como pedi") é invisível ao dono; diagnóstico exige psql/curl em vez da UI.

12. **[SEVERIDADE: alta] RF-002: a UI do chat não distingue mock / adapter ausente / execução real / erro** — apps/web/src/features/modeling-3d/components/ChatModeling3DBadge.tsx:3-14 (badge estática "3D", sem modo) + ModelingPlanCard.tsx:533-538 — evidência: o card de conclusão diz "Plano executado." independentemente de os tool calls terem rodado em `transport: "mock"`; nenhum badge de modo (mock/real) existe no fluxo do chat; a única pista é o modal de diagnóstico (seção Adapters), que o usuário precisa abrir por conta própria e que mostra `adapter.status` cru — violação: RF-002 e caso de borda "Adapter ausente / mock ... sem fingir sucesso" — impacto: com o Fusion desconectado, o fluxo inteiro "finge sucesso" no chat; exatamente o cenário que a spec proíbe.

13. **[SEVERIDADE: média] Textos do diálogo de ativação e das configurações descrevem o modelo de aprovação antigo (pré-P1)** — apps/web/src/features/modeling-3d/components/EnableModeling3DDialog.tsx:78-81 e 96-99 ("JUDITE executará adições e alterações normais via MCP fluido... sem etapa separada de aprovação para operações seguras") + settings/Modeling3DSettingsSection.tsx:31-34 ("Adições e alterações normais podem autoexecutar") — evidência: o comportamento real (P1 entregue, chat_modeling.py:513-528) é o oposto — todo plano primário PARA em `waiting_approval` — violação: chat-flow-redesign §2 (decisão do dono: aprovação sempre; fluido é opt-in) e §10/P1 — impacto: o usuário é informado de um modelo de segurança que não existe mais; mina a confiança no gate de aprovação.

14. **[SEVERIDADE: média] Toggle do "modo fluido" especificado nunca foi construído na UI** — apps/web/src/types/api.ts:171-179 (`fluid_mode?: boolean | null` existe no contrato) — evidência: nenhum componente envia `fluid_mode` (grep em apps/web: só a definição do tipo); `toModeling3DContext` (api/index.ts:134-140) nunca o inclui; chat-flow-redesign §4.3 especifica "Toggle no EnableModeling3DDialog / header do chat" e §10/P3 declara o campo entregue — violação: chat-flow-redesign §4.3/§6 — impacto: o usuário não consegue ligar/desligar o modo fluido pela UI; o campo do contrato é letra morta no frontend (o backend, por sua vez, hardcoda `fluid_mode=True` para edições em chat_modeling.py:487-492, decisão 2026-05-25 não refletida na spec §4.3).

15. **[SEVERIDADE: média] `mode: "safe_auto"` cravado no payload do chat, contra a decisão "default deixa de ser safe_auto"** — apps/web/src/features/modeling-3d/api/index.ts:137 (`mode: "safe_auto" as const`) + types.ts:36-40 (`Modeling3DChatPayload.mode: "safe_auto"` literal) + App.tsx:1108-1119 (sessão 3D existente também hardcoda) — evidência: chat-flow-redesign §4.2/§6 — "Default de modo: deixa de ser `safe_auto`. Novo default = exige aprovação"; o backend compensa forçando `waiting_approval` na rota, mas o cliente continua pedindo auto-execução e o tipo literal impede enviar `plan_only`/`approval_required` (enum de 3 valores em types/api.ts:4) — impacto: contrato enganoso; se a guarda da rota regredir, o frontend volta a auto-executar sozinho.

16. **[SEVERIDADE: baixa] Card de aprovação trunca o plano em 5 etapas sem acesso ao restante fora do modo edição** — apps/web/src/features/modeling-3d/components/ModelingPlanCard.tsx:302, 320-322 — evidência: `plan.steps.slice(0, 5)` + "+ N etapa(s) no plano completo." sem link/expansão (o usuário só vê todas as etapas se clicar "Editar plano") — violação: RF-005/RF-006 (avaliar o plano antes de aprovar) — impacto: aprovação às cegas de etapas 6+ em planos longos.

17. **[SEVERIDADE: baixa] Strings em inglês visíveis ao usuário (produto deve ser PT-BR)** — apps/web/src/features/modeling-3d/components/ModelingEditCard.tsx:88 (`<Badge>{plan.status}</Badge>` cru: "completed"/"failed", sem o `statusLabel` que o ModelingPlanCard usa) + ModelingDiagnosticsModal.tsx:240-242 (status de tool call "ok"/"error"/"blocked" cru) e 224-226 (`adapter.status` cru, ex. "adapter_mock") + ModelingPlanCard.tsx:309-311 e 383-393 (pills e select de risco "low/medium/high") — violação: AGENTS.md "Mantenha o produto em PT-BR" / RNF-004 — impacto: inconsistência de idioma na UI principal.

18. **[SEVERIDADE: baixa] Código morto na feature** — apps/web/src/features/modeling-3d/hooks/useAttachmentAnalysis.ts (hook exportado e jamais consumido por componente; a análise de anexos roda server-side em chat_modeling.py:364-369) + store.ts:31-32 (`enableNextChat`/`disableNextChat` sem nenhum chamador) — violação: RNF-006 (qualidade/clareza) — impacto: superfície morta confunde a manutenção do RF-004 no frontend.

19. **[SEVERIDADE: baixa] EditCard afirma "sem aprovação adicional (allowlist segura)" mesmo para edições high-risk que exigiram aprovação** — apps/web/src/features/modeling-3d/components/ModelingEditCard.tsx:93-96 — evidência: o texto é fixo; edições high-risk passam pelo ModelingPlanCard para aprovação e, depois de concluídas, são renderizadas pelo EditCard (app-chat.tsx:263) com a mesma frase — violação: precisão exigida por RF-022/ADR-013 — impacto: registro visual incorreto do gate aplicado.

20. **[SEVERIDADE: baixa] Acessibilidade: cópia do trace_id só por mouse e modal de diagnóstico sem focus-trap de Tab** — apps/web/src/features/modeling-3d/components/ModelingDiagnosticsModal.tsx:166-174 (`<code onClick={...}>` sem role/tabIndex/teclado) e 87-95 (só Escape; EnableModeling3DDialog tem trap de Tab, o de diagnóstico não) — violação: AGENTS.md "Mantenha rótulos acessíveis", RNF-009 — impacto: usuários de teclado não copiam o trace_id e o foco escapa do dialog.

## Dessincronização de contrato backend×frontend

21. **[SEVERIDADE: alta] Transporte `mcp_http` não existe nos tipos (nem no Literal do contrato backend) e derruba o diagnóstico inteiro** — apps/web/src/types/api.ts:44 (`ModelingTransport = "stdio" | "http" | "mock" | "local"`) × backend/app/modeling/mcp_client.py:111-112 (`transport()` retorna `"mcp_http"` quando `TRUTHS_FORGE_MCP_TRANSPORT=mcp_http`) × backend/app/core/contracts.py:800 (Literal sem `mcp_http`) — evidência: com a flag documentada em docs/3d-modeling-debug.md §5 ligada, `ModelingCapability(...)` levanta ValidationError → `GET /api/3d/capabilities` 500 → `useModeling3dDiagnostics` rejeita o `Promise.all` inteiro e o modal mostra apenas "Falha ao carregar diagnóstico MCP 3D" (ModelingDiagnosticsModal.tsx:212) — violação: RF-020/História 5 (modo standalone é caminho suportado) + RF-024 — impacto: exatamente no modo MCP standalone (Fase 1), a observabilidade da UI quebra por completo.

22. **[SEVERIDADE: alta] `ModelingPlan` do frontend não conhece `model_state`, `model_verdict` e `sub_goals`** — apps/web/src/types/api.ts:99-128 × backend/app/core/contracts.py:1173-1190 — evidência: os três campos existem e são serializados pelos endpoints REST (`response_model=ModelingPlan`), mas faltam no tipo TS; o SSE (`_modeling_plan_metadata`, chat_modeling.py:61-115) também não os envia — violação: RF-013/RF-019 (histórico de verificação reconstituível no cliente) — impacto: mesmo que alguém implemente a UI do relatório esperado×medido, o contrato TS atual não dá acesso tipado aos dados; campos chegam no JSON e são ignorados silenciosamente.

23. **[SEVERIDADE: média] `Modeling3DChatPayload.mode` tipado como literal `"safe_auto"` vs enum de 3 valores do backend** — apps/web/src/features/modeling-3d/types.ts:36-40 × backend/app/core/contracts.py:62-65 e 517-523 — evidência: `ChatModeling3DContext.mode` aceita `plan_only`/`approval_required`/`safe_auto`; o tipo do payload do frontend só permite `safe_auto` — impacto: impossibilita o cliente de pedir os modos mais restritivos previstos no contrato (mesma raiz do achado 15, aqui como dessincronização de tipo).

24. **[SEVERIDADE: baixa] `ModelingSessionStart.force_mock` opcional no front com default `True` no backend** — apps/web/src/types/api.ts:77-81 × backend/app/core/contracts.py:825-828 — evidência: omitir o campo cria sessão `mock` silenciosamente; hoje o frontend não chama `sessions/start`, mas o tipo convida ao erro — impacto: risco latente de sessões mock acidentais (RF-002).

## Gaps de teste

25. **[SEVERIDADE: média] Zero testes para a superfície de observabilidade (História 6)** — não existem `ModelingDiagnosticsModal.test.tsx`, `useModeling3dTrace.test.ts` nem `useModeling3dDiagnostics.test.ts` — evidência: o glob da feature lista testes só para Badge, EditCard, PlanCard, EnableDialog, store, format e useModelingPlanActions — violação: RNF-008 ("toda capacidade implementada DEVE ter testes unitários") + História 6 — impacto: filtros de nível, fallback de trace vazio, debounce/no-op do recordEvent e a quebra do achado 21 não têm regressão.

26. **[SEVERIDADE: média] Hook de ações do plano só testa a recuperação de rede** — apps/web/src/features/modeling-3d/hooks/useModelingPlanActions.test.ts:8-14 — evidência: o mock da API só define `approvePlan/executePlan/getPlan`; `reject`, `edit`, `revise`, `retry` e `rollback` (e o contrato "reject não executa") não têm nenhum teste de hook — violação: RNF-008; História 2 exige os 3 caminhos do plano testáveis — impacto: regressões nos caminhos negar/editar (os dois caminhos não-felizes do RF-006) passariam batido na camada de hook/API.

27. **[SEVERIDADE: média] Sem teste para reconciliação do card após reload nem para sinalização de modos mock/real** — evidência: nenhum teste cobre o cenário do achado 1 (mensagem persistida com plano `waiting_approval` + plano real `completed`) nem o RF-002 (não há UI de modo, logo não há teste) — violação: RF-002/RF-008 — impacto: os dois achados de maior severidade não têm rede de proteção.

28. **[SEVERIDADE: baixa] Teste fixa o texto desatualizado do diálogo de ativação** — apps/web/src/features/modeling-3d/components/EnableModeling3DDialog.test.tsx:37 — evidência: `expect(screen.getByText(/Modo: fluido allowlistado/i))` cimenta a cópia pré-P1 (achado 13) — impacto: o teste hoje protege o comportamento/texto errado.

---

## Resumo

| Severidade | Quantidade |
| --- | --- |
| Crítica | 1 |
| Alta | 5 |
| Média | 12 |
| Baixa | 10 |
| **Total** | **28** |

Síntese: o esqueleto do fluxo chat-first (RF-006 com aprovar/negar/editar reais, gate de aprovação, rollback T3.6) está implementado e testado no caminho feliz. Os maiores buracos são de **fidelidade ao contrato e à observabilidade prometida**: (a) cards persistidos nunca são reconciliados com o estado real do plano — re-execução possível de plano concluído; (b) a justificativa de rejeição que a UI promete usar é descartada; (c) o relatório esperado×medido (coração das Histórias 3/6) existe no backend e é invisível na UI; (d) a UI "finge sucesso" em modo mock (RF-002); e (e) o modo MCP standalone quebra o diagnóstico por enum dessincronizado.


---

# ANEXO: spatial-state.md

# Auditoria — Estado rico do modelo (F1) + Referência espacial/posicionamento (F7/F9)

Repo: raiz · Data: 2026-06-10 · Suíte backend verde (678 testes) — os achados abaixo são lacunas que a suíte não cobre ou divergências spec×código.

Specs de referência: `specs/005-modeling-3d-fusion/micro/fase-F1-estado-rico.md`, `micro/fase-F7-posicionamento.md`, `tech-debt-posicionamento.md`, `micro/fase-9-llm-determinism.md`, `micro/fase-F3-mecanismos.md`, `spec.md` (RF-012/RF-014), `docs/decisions.md` (ADR-021/022/023/024).

Veredito geral: a integração F1 está **completa** (captura pós-execução → `plan.model_state` → contexto de edição → blocos hierárquicos → reconciliação) e o wiring F7/F8/F9 é flag-consistente, sem caminho morto relevante. Os problemas estão (a) em violações pontuais do invariante "NUNCA chuta" (fallbacks/coerções silenciosas), (b) num crash não-tipado no enforcement F9, (c) num falso-positivo de medição (`is_open_boundary`) que contamina o estado semântico, e (d) numa incongruência forte entre o placement "paramétrico via joints" prometido pelo ADR-022 e o `move_body` assado que o código emite (com schema LLM-facing ainda anunciando o comportamento antigo).

---

## Bugs

- **[alta] `enforce_relative_coord` crasha com `ValueError` cru quando `translation_mm` contém `@`-ref (forma suportada pelo resolver)** — `backend/app/modeling/spatial_resolver.py:324` (via `backend/app/modeling/executor.py:522-534`) — o Gate B roda ANTES da resolução inline (`executor._maybe_resolve_spatial` chama `enforce_relative_coord` antes de `needs_resolution`/`resolve_step`) e faz `moved = _shifted_body(moving, [float(t) for t in translation[:3]])` sobre os args CRUS. Um `fusion.move_body` legítimo com componente declarativo (`{"translation_mm": [30, 20, "@body('Caixa').bbox.max_z + 2"]}` — exatamente o formato que `_resolve_point_field` suporta e `test_inline_resolves_mixed_component_list_and_axis` valida) estoura `ValueError: could not convert string to float` (ou `TypeError` p/ objeto-ref), que NÃO é `SpatialRefError` e escapa do `except SpatialRefError` em `executor.py:421` — derruba o `execute_plan` inteiro sem outcome tipado. Violação: ADR-024 invariante "erro tipado, nunca exceção crua" e o próprio contrato do módulo ("Erro tipado... nunca chuta"). Impacto: com `modeling_relative_enforcement_enabled` + `modeling_spatial_resolution_enabled` ON, um plano válido vira exceção não tratada na rota.

- **[alta] `_face_is_open_boundary` marca falso-positivo para QUALQUER face com furo passante (`loops.count > 1`)** — `backend/app/modeling/fusion_mcp_scripts.py:535-538` — o sinal (2) do commit "detecta abertura de solido ocado p/ is_open_boundary" trata todo loop interno como abertura, mas uma placa maciça com furo (Cenário A dos gates: "placa com 4 furos") tem topo E fundo com 2+ loops → ambos `is_open_boundary=true`. Consumidores: `semantic_state._derive_labels` rotula a placa como `container` (`semantic_state.py:120-124`) — violando o invariante ADR-024 "NUNCA rotula errado" — e pode rotular o vizinho mais fino como `lid`; `entity_ref` role `open_boundary` (`entity_ref.py:142-144`) passa a disputar topo×fundo (empate → erro ambíguo; áreas distintas → resolve a face errada com confiança); `cover_opening` (relation_derive) herda o alvo errado. Impacto: a semântica injetada no `<model-state>` (Pilar 2 do F9) ensina ao LLM uma montagem falsa.

- **[média] `_gap_direction` confia no SINAL da normal que o próprio repositório documenta como não-confiável** — `backend/app/modeling/spatial_resolver.py:374-407` vs `backend/app/modeling/entity_ref.py:119-123` — o lado da folga do `align='gap'` (commit "folga do align=gap segue a normal do destino") usa `_normal_sign_along(target_face)` como sinal primário. O `entity_ref` rankeia top/bottom **por posição** exatamente porque "o read-back classifica o normal do FUNDO como '+z'" (adapters sem a correção `isParamReversed` de `fusion_mcp_scripts.py:505-509`, que por sua vez engole exceção e mantém a normal sem corrigir). Não há cross-check geométrico (ex.: normal × posição do centro do corpo). Impacto: normal mal-sinada ⇒ a folga abre p/ DENTRO da caixa, silenciosamente — o mis-place confiante que F7/F9 juram eliminar; só o último degrau da cascata erra tipado.

- **[média] Enforcement "longe" mede `abs(gap)` num eixo de mate inferido por separação de centros → falso positivo p/ contato lateral** — `backend/app/modeling/spatial_resolver.py:344` + `backend/app/modeling/geometry_verifier.py:57-68` — `_mate_axis` escolhe o eixo de maior separação entre CENTROS; para um corpo alto encostado lateralmente numa placa baixa (centros separados sobretudo em z, ranges de z sobrepostos), `_gap_along` devolve "penetração" em z e `abs(gap) > 5mm` recusa um move legítimo como "flutuando longe". A limitação é documentada no `geometry_verifier` ("laudo F8, baixa/latente") mas o Gate B a promoveu a critério de RECUSA sem a ressalva. Impacto: falso `fusion.relative_coord_forbidden` em layouts laterais válidos (flag ON).

- **[média] `_coerce_float` engole `gap_mm` inválido → 0.0 silencioso (align='gap' vira flush)** — `backend/app/modeling/spatial_resolver.py:577,604-608` — `gap_mm="2mm"`/`"abc"` → `float()` falha → `return 0.0`; o usuário pediu folga e recebe contato 0 sem aviso. Mesmo padrão: `align='gap'` sem `gap_mm` nenhum degenera p/ flush sem erro (`:601` cobre só o caso coincidente). Violação: invariante "fora da gramática → erro tipado" (ADR-022 D1 / F7 §gramática). Impacto: respiro/folga pedidos somem silenciosamente.

- **[média] `distribute_along` ignora `spacing_mm` silenciosamente quando `edge.length_mm` está ausente/0** — `backend/app/modeling/spatial_resolver.py:639-652` — a condição `if spacing_mm and not fit and length and length > 0:` cai no ramo uniforme (`i/(count-1)`) quando `length` é None, sem erro. O caso "não cabe" erra tipado (`:645`), mas o caso "não sei o comprimento" chuta a distribuição. Violação: "NUNCA chuta" (F7). Impacto: espaçamento pedido ≠ espaçamento executado, sem telemetria.

- **[média] `distribute_along` ancora o protótipo pela BASE no ponto da fração e inclui as pontas (0 e 1) → último nó inteiro FORA da aresta** — `backend/app/modeling/spatial_resolver.py:652,655-669,691` + `backend/app/modeling/fusion_mcp_scripts.py:1739-1799` — `add_cylinder` posiciona a BASE em `origin_mm` e estende `height_mm` no sentido +axis; com frações `i/(count-1)` o nó em `frac=1.0` ocupa `[fim, fim+height]` (sobra pra fora da dobradiça) e nenhum nó fica centrado no seu ponto. Agravante: o `axis` emitido é o vetor exato da aresta (`:691`), mas o handler o quantiza pro cardinal dominante com `abs()` (`fusion_mcp_scripts.py:1746-1756`) — aresta diagonal ou direção negativa perdem sinal/orientação em silêncio. Violação: gate F7/F3 "caixa+tampa knuckle" (knuckles devem ladrilhar a aresta); "NUNCA chuta" p/ aresta não-cardinal. Impacto: fileira de knuckles deslocada meio-nó e nó extra fora da peça (API-blind, gate P6 pendente — mas o erro é determinístico e testável em mock).

- **[média] `place_body` não valida que `anchor` pertence ao corpo movido** — `backend/app/modeling/spatial_resolver.py:560-575` — `_resolve_face(args["anchor"])` resolve token globalmente (`_resolve_face` varre todos os corpos); na forma `@token('F')`/`{face:'<tok>'}` nada confere `anchor_face ∈ moving.faces`. Um token trocado (anchor na Caixa, body=Tampa) gera delta sem sentido aplicado à Tampa, silenciosamente. (Na forma `{body, role}` o escopo vem do entity_ref.) Impacto: mis-place silencioso por erro de eco do LLM — a classe de bug que o F8 (ADR-023) nasceu p/ matar.

- **[média] `align_axis` resolve o alvo por medição, mas o lado do corpo MÓVEL fica "primeira face cilíndrica" (índice posicional)** — `backend/app/modeling/spatial_resolver.py:623-631` (`"face_selector_one": "cylindrical"`) + `backend/app/modeling/fusion_mcp_scripts.py:4183-4187` (`coll.item(0)`) — num parafuso/pino com várias faces cilíndricas (haste, cabeça, rebaixo), a junta ancora numa face arbitrária por ordem de índice. Violação: F1 D1/ADR-021 (precedência token/medição > índice posicional); F7 ("o backend MEDE"). Impacto: eixo de junta no cilindro errado → dobradiça torta no gate.

- **[média] `coaxial_insert` mede o MAIOR raio cilíndrico do moving — para parafuso, é a CABEÇA, não a haste** — `backend/app/modeling/relation_derive.py:74-80,123-129` — `_cylindrical_radius` = `max(radii)`; o predicado mira face do furo com raio ≈ cabeça (±0.5mm). Para o gate F3 "parafuso que encaixa" (M6: haste r=3, cabeça r≈5): ou erro tipado "nenhuma face casa" (melhor caso) ou casa um rebaixo/contra-furo errado. Também: folga projetada > `_RADIUS_TOL=0.5mm` entre pino e furo torna a relação underivável. Impacto: o kind nominal do vocabulário falha no cenário-gate mais citado da spec.

- **[média] Role `open_boundary` tem fallback silencioso p/ "maior planar +z" — pode resolver o FUNDO INTERNO da caixa ocada** — `backend/app/modeling/entity_ref.py:138-148` — sem o sinal `is_open_boundary` (mocks/adapters antigos), cai na maior face planar +z; numa caixa shelled a maior +z é o piso interno ((L-2t)(W-2t) > área do aro) → `cover_opening` colocaria a tampa DENTRO da caixa. ADR-023 declara a limitação ("is_open_boundary com fallback"), mas o fallback contradiz o invariante "NUNCA chuta" e não emite warning/measured-note. O `semantic_state` recusou esse fallback de propósito (`semantic_state.py:55-60`) — incoerência interna de critério.

- **[média] `along`/`midpoint` em aresta CIRCULAR interpola a CORDA, sem erro** — `backend/app/modeling/spatial_ref.py:257-260` — `_edge_point` faz lerp start→end sem checar `is_circular`; o "midpoint" de um semicírculo é o centro do círculo (fora da curva). ADR-023 reconhece "curvas atrás de spike", mas aqui não há erro tipado — devolve um ponto geometricamente errado com confiança. Violação: "fora da gramática → `spatial_ref_unresolved`".

- **[média] Probe do `capture_model_state` usa `limit` default 60 faces/arestas por corpo → resolução sobre estado TRUNCADO** — `backend/app/modeling/model_state.py:177-186` (probe só passa `include_tokens`) + `fusion_mcp_scripts.py:3355,3422,3455` — em corpos com >60 faces (caixa com fillets/furos), roles (`top_planar`, `largest`) e buscas por token são resolvidos só sobre as 60 primeiras por índice: token existente "não encontrado" (erro tipado, ok) ou role resolvido na face errada (silencioso). Violação: F1 D2 ("estado estruturado" como fonte de verdade) — a fonte é parcial sem sinalização de truncamento no `ModelState`.

- **[média] `semantic_state._derive_touches` herda o `_mate_axis` por centros → falso negativo p/ contato lateral entre corpos de alturas distintas** — `backend/app/modeling/semantic_state.py:92-99` — para um pino alto encostado na lateral de uma placa baixa, o eixo inferido é z e `_perp_overlap_area` no plano ⊥z é 0 → contato real não registrado em `touches`. O LLM lê "não encosta em nada" e volta a chutar coordenada — o oposto do objetivo do Pilar 2.

- **[baixa] `_axis_letter` quantiza vetor diagonal p/ cardinal e usa default 'z' silenciosos** — `backend/app/modeling/spatial_resolver.py:259-267` — `[1,1,0]` vira "x" (primeiro máximo) sem erro nem nota; `align_axis` sem `body_axis` cai em z sem registrar (o caminho via `relation_derive` registra `axis_default: z` em `measured`; o caminho direto da tool não).

- **[baixa] `needs_resolution` não recursa em dicts aninhados nem detecta objeto-ref dentro de lista** — `backend/app/modeling/spatial_resolver.py:125-130,745-756` — `_has_at` recursa listas mas não dicts; `is_spatial_ref` só olha o topo. `{"center_mm": [{"body":"X","point":"bbox.max_z"}, 0, 0]}` não dispara resolução → o guard de leftover (`:190-195`) nunca roda e a ref crua é despachada ao adapter (falha downstream, não erro tipado do resolver).

- **[baixa] `center_mm` de face é o centro da AABB da face, não o centróide** — `backend/app/modeling/fusion_mcp_scripts.py:3446-3450` — para faces em L/aro assimétrico, o "centro medido" pode cair fora da face; o snap concêntrico do `place_body` desloca. Spec F7 fala em "face center" sem qualificar; vale nota no contrato.

- **[baixa] `seat_in_pocket` usa `reference_role="largest_planar"` — tende a resolver a face EXTERNA da peça, não o fundo do bolso** — `backend/app/modeling/relation_derive.py:50` — numa placa com bolso, a maior planar é o topo/fundo da placa; o assento "no bolso" encosta na superfície errada (erro tipado só se ambíguo).

- **[baixa] `align='edge'/'corner'` sempre alinha bbox-MIN; não há como pedir a borda/canto oposto** — `backend/app/modeling/spatial_resolver.py:495-507` — "rente à borda direita" alinha à esquerda, deterministicamente mas sem opção nem erro; empate de extensão em-plano resolve pelo menor índice de eixo, silencioso.

- **[baixa] `try/except SpatialRefError: raise` inócuo** — `backend/app/modeling/spatial_resolver.py:185-186` — bloco morto (re-raise puro); ruído que sugere tratamento que não existe.

## Incongruências spec×código

- **[alta] ADR-022 D3 + F7 micro prometem placement PARAMÉTRICO (make_component + joint, "sobrevive a recompute"; 1º corte 'baked' REJEITADO pelo dono) — o código emite `move_body` assado; e o schema LLM-facing ainda anuncia o comportamento antigo** — `backend/app/modeling/spatial_resolver.py:515-601` (emite só `fusion.move_body`; docstring: "Corpos seguem SEPARADOS (sem componente/junta)") vs `specs/.../micro/fase-F7-posicionamento.md` (tabela: place_body → "make_component + joint (rigid/planar/cylindrical)") e ADR-022 D3. Agravante: `backend/app/modeling/tool_schemas.py:611-617` diz ao LLM "O resolver expande em make_component + junta rígida que sobrevive a recompute" enquanto `tool_registry.py:492-498` já descreve "move_body determinístico" — as duas fontes LLM-facing se CONTRADIZEM no mesmo prompt. ADR-023/024 descrevem o comportamento novo, mas nunca revogam formalmente o D3 do ADR-022 nem atualizam a tabela do F7. Impacto: placement não sobrevive a recompute/edição paramétrica (a robustez que o dono escolheu pagando complexidade) e o LLM recebe documentação mentirosa da tool.

- **[média] F9: schema sempre ensina `align`/`gap_mm`, mas com `modeling_align_modes_enabled` OFF o resolver os ignora SILENCIOSAMENTE** — `backend/app/modeling/tool_schemas.py:638-653` (não flag-gated) vs `spatial_resolver.py:548-553` — com spatial ON + align OFF (estágio real de gates incrementais), um `align:'gap', gap_mm:2` emitido pelo LLM (ensinado pelo schema) vira snap concêntrico flush, sem warning. ADR-024 sanciona "flag OFF ⇒ align ignorado = zero regressão", mas isso vale p/ planos ANTIGOS; para planos novos com align explícito é mis-place silencioso — choque com o D4 do ADR-022 ("flag OFF → erro claro, nunca mis-place silencioso").

- **[média] F7 micro: `distribute_along` → "pattern paramétrico OU N componentes jointados"; código emite N primitivas + `combine_bodies`, sem pattern nem joint** — `backend/app/modeling/spatial_resolver.py:672-717` vs `specs/.../fase-F7-posicionamento.md` (tabela de tools). Mesma família do achado acima: a spec promete montagem nativa, o código entrega geometria assada — e o `combine_bodies` concreto do `alternate` é bloqueado pelo gate high-risk (`executor.py:657-661`), exigindo aprovação: o caminho feliz "knuckles num passo só" da spec NUNCA auto-executa hoje.

- **[baixa] Docstrings/headers stale repetindo o contrato antigo** — `backend/app/modeling/spatial_resolver.py:14-19` ("expande em make_component + combine + joint") e `backend/tests/test_spatial_resolver.py:4-6` — desatualizados em relação ao próprio código que documentam.

- **[baixa] F1 follow-up declarado e ainda aberto: selectors por token nas surface tools** — `specs/.../fase-F1-estado-rico.md:65` e `tech-debt-posicionamento.md` §3.4 — patch/extend/offset/unstitch continuam por índice (confirmado: `_faces_by_tokens` só em fillet/chamfer/shell/joint — `fusion_mcp_scripts.py:1947,2011,2085,4057,4175`). Documentado como débito; registrado aqui p/ rastreio.

## Integração incompleta

- **[ok] F1 completa** — captura pós-execução (`agent_loop.py:436,602-619`), persistência em `plan.model_state`, injeção em edição (`planner.py:703-750`), blocos hierárquicos (`planner_service.py:231-267`, `chat_orchestrator.py:170-200` — estado flui bloco a bloco com fallback `or current_state`), reconciliação ao vivo (`chat_orchestrator.py:805-828`). Tokens estáveis com erro `fusion.edge_token_stale` (nunca cai mudo em "all") — `fusion_mcp_scripts.py:648-676`. Sem meia-ligação detectada.

- **[ok] F7/F8/F9 flag-consistentes** — `relate_bodies` com flag OFF curto-circuita ANTES do resolver F7 p/ não dar erro enganoso (`executor.py:543-548`); tool declarativa crua no adapter erra tipado `fusion.spatial_not_resolved` (`fusion_mcp_scripts.py:4618-4634`); expansão exime Gate B via `from_expansion` (`executor.py:519-526`); expansão high-risk bloqueada fail-safe (`executor.py:657-661`); probe read-only não recursa (`needs_resolution(read_only=True)`); `relate_bodies` dark no planner (`tool_registry.py:608-612`).

- **[média] F7 trio sempre no `PLANNER_TOOLSET` + schema completo, mesmo com `modeling_spatial_resolution_enabled` OFF** — `backend/app/modeling/tool_registry.py:603-656` (só `relate_bodies` é UNRELEASED) + `planner.py:1090` (schemas de todo o toolset) — com a flag OFF o LLM é ensinado (schema) a usar `place_body` sem o nudge F7, e todo uso falha no adapter. "Erro claro" cumpre o D4 do ADR-022, mas é um convite estrutural a planos fadados a falhar; gating de visibilidade pela flag (como `UNRELEASED_PLANNER_TOOLS`) fecharia a meia-ligação.

- **[média] `<model-state>` nunca expõe token de aresta RETA (só circulares)** — `backend/app/modeling/model_state.py:154-163` — o render filtra `is_circular and radius_mm`; a gramática F7 (`@edge('<e>').along(f)`, `distribute_along` por edge_token) depende de aresta reta, cujo token o LLM não consegue obter do bloco injetado. O caminho via `relate_bodies.distribute_on_edge` contorna (deriva a maior aresta reta no backend), mas as formas diretas ensinadas no nudge F7 (`planner.py:853-856,862-863`) ficam inalcançáveis a partir do contexto renderizado.

- **[baixa] Gate B roda o probe `capture_model_state` ANTES de validar os args do move** — `backend/app/modeling/executor.py:530-534` vs `spatial_resolver.py:307-312` — move_body sem `translation_mm` em lista paga 1 probe Fusion à toa por passo (a validação barata vem depois do probe caro).

- **[nota] "Ciclos" em relações: não-aplicável por construção** — `relation_resolver` resolve cada `relate_bodies` isoladamente contra um probe fresco (sem grafo de constraints/solver), então ciclo A→B→A não trava — mas também significa que relações posteriores podem desfazer as anteriores sem detecção (consequência do placement assado; ver incongruência ADR-022).

## Gaps de teste

- **[alta] Nenhum teste cobre `enforce_relative_coord` com `@`-ref/objeto dentro de `translation_mm`** (o crash do 1º achado) — `test_spatial_resolver.py:481-541` e `test_spatial_wiring.py:146-178` só usam listas numéricas.
- **[média] Gate "parafuso que encaixa" sem cenário de corpo com DOIS raios cilíndricos (haste+cabeça)** — `test_relation_derive.py:80-101` usa raio único; o caso nominal do parafuso (achado coaxial_insert) passa em branco.
- **[média] `is_open_boundary`: nenhum teste do falso-positivo "furo passante"** — `test_semantic_state.py` e `test_model_state.py:139` só testam o caminho feliz; não há fixture "placa com furo" provando que ela NÃO vira `container` (hoje viraria).
- **[média] `_gap_direction` sem caso de normal mal-sinada** — `test_entity_ref.py:69` cobre a robustez do role à normal errada, mas nenhum teste cobre a folga abrindo pro lado errado com normal de destino invertida (o mesmo defeito de read-back que motivou rankear por posição no entity_ref).
- **[média] `distribute_along`: sem asserção de CONTENÇÃO da fileira na aresta** (base na fração 1.0 + height pra fora), sem caso `length_mm=None`+`spacing_mm` (fallback silencioso), sem caso de aresta diagonal (quantização do axis no handler).
- **[média] `place_body`: sem caso de anchor-token pertencente a OUTRO corpo; sem caso `gap_mm` string inválida (`_coerce_float`→0.0); sem asserção de aviso quando `align` é emitido com `modeling_align_modes_enabled` OFF (hoje é silêncio).**
- **[baixa] Truncamento do probe (`limit=60`) sem teste** — nenhum fixture com >60 faces provando erro/sinalização em vez de mis-resolução de role.
- **[baixa] `along` em aresta circular sem teste** (hoje devolveria a corda sem erro).
- **[baixa] Cenário-gate caixa+tampa knuckle (F7 P6) segue 100% dependente do gate manual** — coerente com o plano (API-blind), mas os pedaços mock-testáveis acima (contenção da fileira, eixo do nó, lado da folga) reduziriam o risco do gate.

## Resumo por severidade

| Severidade | Qtde | Itens |
|---|---|---|
| crítica | 0 | — |
| alta | 4 | crash não-tipado no Gate B; falso-positivo `is_open_boundary` (semântica falsa ao LLM); incongruência ADR-022×código (joint paramétrico vs move assado + schema contraditório ao LLM); gap de teste do crash do Gate B |
| média | 17 | lado da folga confiando em normal não-confiável; falso-positivo "longe" do enforcement; `gap_mm` engolido; `spacing_mm` ignorado; fileira de nós fora da aresta; anchor sem ownership; align_axis por índice posicional; raio máximo no coaxial_insert; fallback do open_boundary; corda em aresta circular; probe truncado (limit 60); touches falso-negativo lateral; schema `align` não-gated; distribute_along sem pattern/joint (e combine bloqueado no caminho feliz); F7 trio visível com flag OFF; tokens de aresta reta ausentes do `<model-state>`; +4 gaps de teste de severidade média |
| baixa | 12 | axis quantizado/default z; needs_resolution não-recursivo; center de face = AABB; seat_in_pocket largest_planar; edge/corner só bbox-min; except inócuo; docstrings stale; F1 surface-tools follow-up; probe antes da validação no Gate B; +3 gaps de teste baixos |

Pontos fortes confirmados (sem achado): identidade por `entityToken` com erro `edge_token_stale` (nunca cai mudo em "all"); precedência token>índice nos selectors sólidos; aritmética por AST restrito sem `eval` (com bloqueio de injeção testado); erros tipados consistentes (`SpatialRefError` + `code`) tratados num único seam do executor (`_spatial_failure_outcome`); desambiguação por margem com `AmbiguousRefError` (sem escolha arbitrária em empate); zero dependência de ordem de dict/set não-determinística; unidades cm→mm consistentes no read-back (×10 linear, ×100 área); no-op de Δ≈0 do place_body corretamente agregado como sucesso (expansão vazia ≠ falha).
