# Fase 0 — Inventário de Auditoria do v3 (`backend/app/modeling/`)

**Fase**: 0 | **Spec**: [`../spec.md`](../spec.md) | **Macro**: [`../plan.md`](../plan.md) | **Micro**: [`fase-0-specs-auditoria.md`](./fase-0-specs-auditoria.md)

> Entregável das tarefas **T0.5** (veredito por peça), **T0.6/T0.6b** (status real-Fusion das tools + assets do fidelity), **T0.10** (catálogo de inconsistências de doc). Auditoria **estática** (somente leitura) feita em `feat/3d-modelling-updates` @ `7a5f69a` (base `origin/master` `f0cbe62`). Nenhum código foi alterado.
>
> **Método e limites**: vereditos por leitura de código + mapeamento de testes existentes por `import`/`assert` (não rodamos coverage). "Cobertura indireta" = peça exercida por composição/integração, sem asserção unitária direta da lógica interna. Status real-Fusion cruzado **só** com evidência registrada (trace_id no `handoff.md`, gaps em `adapter-gaps-roadmap.md`); sem evidência → `desconhecido` (não inferido).

## Escala de veredito

`confiar` = correto e testado, base sólida · `evoluir` = aproveitável, mas precisa refino/refator antes de virar base do v4 · `reescrever` = desalinhado do alvo v4 (forma ou arquitetura), substituir.

## 1. Veredito por módulo (T0.5)

26 módulos, ~11.175 LOC. **Nenhum** módulo do núcleo recebeu `reescrever` por má qualidade — a dívida principal é de **integração/duplicação** (DT-006), não de código interno. Os `reescrever` são cascas de transporte que o alvo v4 (ADR-017) torna becos.

| Módulo | LOC | Cobertura | Veredito | Razão (1 linha) |
|---|---:|---|---|---|
| `tool_registry.py` | 606 | direta (`test_tool_registry`) | **confiar** | Allowlist de fonte única, bem testada; só restam shims legados intencionais. |
| `chat_state.py` | 197 | direta exaustiva | **confiar** | State machine pura, matriz de transições toda testada. |
| `discovery.py` | 233 | direta (lógica de gating) | **confiar** | Limiar de confiança coberto; fallback heurístico nunca bloqueia. |
| `workspace.py` | 96 | direta | **confiar** | Utilitário FS isolado; jail de path-traversal testado. |
| `observability.py` | 701 | direta forte | **confiar** | Tracer maduro e endurecido (regressões com teste); base da Fase 2. |
| `mcp_servers/protocol.py` | 108 | direta | **confiar** | JSON-RPC utilitário correto; subset deliberado do MCP. |
| `artifacts.py` | 180 | indireta fraca | **confiar** (+teste direto) | Registro de export coeso; falta asserção direta de `register_outputs`. |
| `prompts/__init__.py` | 36 | direta | **confiar** | Loader trivial e testado. |
| `blender_adapter.py` | 244 | indireta | **confiar/congelar** | Bem isolado (subprocesso + allowlist própria, sem `run_script`). |
| `blender_runner.py` | 805 | quase nula em CI | **confiar/congelar** | Dispatcher de funções puras; só roda com `bpy`. Decisão do dono: congelar. |
| `policy.py` | 96 | direta | **evoluir** | Reimplementa a decisão de aprovação inline em vez de reusar `tool_registry.requires_approval`. |
| `planner.py` | 824 | direta | **evoluir** | LLM/validação sólidos; heurística Fusion frágil e `asyncio.run()` embutido (risco no loop da Fase 2). |
| `planner_service.py` | 527 | indireta | **evoluir** | Duplicação sync/async; resolução de modelo (regressão histórica) sem teste direto. |
| `executor.py` | 455 | direta+indireta | **evoluir** | Execução **linear**, sem ponto de extensão p/ o loop da Fase 2; `execute_plan` grande demais. |
| `service.py` | 430 | direta | **evoluir** | Facade concentra regra de aprovação **duplicada** com o orchestrator. |
| `chat_orchestrator.py` | 794 | direta (só unidade) | **evoluir** | Bem desenhado e testado, mas **desconectado do caminho vivo** (DT-006). |
| `fusion_adapter.py` | 702 | direta forte | **evoluir** | Tradução tool→script e envelopes sólidos; seleção de transporte e fronteira de auth mudam com ADR-017/019. |
| `fusion_mcp_scripts.py` | 2445 | indireta (só sintática) | **evoluir** (cautela) | Coração funcional com muito domínio caçado a duro; f-string de 2,5k linhas é dívida séria de forma. |
| `mcp_client.py` | 255 | direta | **evoluir** | Boundary útil que sobrevive; roteamento por prefixo de string é frágil. |
| `stdio_client.py` | 209 | direta | **evoluir/aposentar** | Sólido p/ stdio, mas o alvo HTTP/SSE (ADR-017) não usa stdio. |
| `mcp_servers/_server_base.py` | 119 | direta | **evoluir** | Boa base de loop, mas sem `initialize`/capabilities/HTTP/SSE/auth. |
| `attachment_analyzer.py` | 513 | direta (boa) | **evoluir** | Esqueleto defensivo bom, mas **vision e CAD/Fusion são stubs** (`_call_vision` retorna `None`). |
| `printability.py` | 169 | parcial/indireta | **evoluir** | **Três fontes de verdade** da heurística (service / blender_runner / fusion-addin). |
| `snapshot_service.py` | 194 | indireta (gap) | **reescrever** | Rollback por cópia de filesystem, não nativo do Fusion (DT-005); sem teste direto de I/O destrutivo. |
| `mcp_servers/fusion_server.py` | 119 | direta | **reescrever** | Casca stdio: backend agindo como servidor de si mesmo; beco no alvo v4 (ADR-017). |
| `mcp_servers/blender_server.py` | 109 | direta | **reescrever** | Mesma casca stdio; ainda diverge no contrato de indisponível (Blender `ok:false` × Fusion `ok:true`). |

**Resumo**: `confiar` 10 · `evoluir` 12 · `reescrever` 3 (+1 par Blender congelado). O núcleo de domínio (registry, planner, executor, observability, fusion_mcp_scripts) é **aproveitável**; o trabalho do v4 é de **integração** (resolver DT-006), **fronteira** (ADR-017/019) e **forma** (fatiar `execute_plan` e o gerador de scripts).

## 2. Dívidas técnicas confirmadas (com evidência)

| DT | Veredito da auditoria | Evidência (file:linha) |
|---|---|---|
| **DT-005** snapshot filesystem ≠ nativo Fusion | **CONFIRMADO** | `snapshot_service.py:68,169` (`copy_into_snapshot`/`restore_from_snapshot`) → `workspace.py:71,88` (`shutil.copy2`). Nenhuma referência a timeline/marker/B-Rep no `fusion_adapter.py`. Captura `.blend`+`exports/` no disco; não reverte o design Fusion aberto. |
| **DT-006** rota × orchestrator duplicados | **CONFIRMADO (severo)** | `chat_modeling.py:320-326` chama `get_modeling_service` direto e admite não passar pelo orchestrator; reimplementa a state machine à mão (`:368-419` clarificação, `:421-432` intent, `:476-530` modo fluido, `:539-552` gate P1); `modeling.py:135-167` reimplementa `executing→editing`. Duas implementações de "aprovar plano": `service.py:205` e `chat_orchestrator.py:638`. **Efeito**: `chat_orchestrator.py` (794 LOC, bem testado) é código fora do caminho vivo. |
| **DT-007** fallback JSON silencioso | **CONFIRMADO (parcial)** | `storage/store.py`: no ramo `postgres` a falha **re-levanta** (correto); no ramo `auto` o `except Exception` **engole sem log** e cai para `DevStore` JSON (`:~26-30`), cacheado em singleton → degradação permanente até restart, sem sinal ao operador. |
| **DT-008** sem estado de falha/rollback no chat | **CONFIRMADO** | `ChatModelingStage` tem 6 estados, sem `failed`/`error`/`rollback`; `chat_state.py:105-107` mapeia `(executing, EXECUTION_FAILED) → editing` (teste confirma intenção). Chat que falhou e chat concluído ficam **ambos** em `editing`. Gap para o loop agêntico da Fase 2. |
| **DT-009** fronteira `featureType:"script"` | **CONFIRMADO → ADR-019** | `fusion_adapter.py:475-479` envia `featureType:"script"` com script gerado por `fusion_mcp_scripts.build_autodesk_fusion_script` (`:470`). Script é **backend-owned e determinístico** (LLM só escolhe tool+args); `fusion.run_script` excluído do adapter (`:53-55`) e do planner (`tool_registry.py:487-502`); args entram como **JSON desserializado** (`fusion_mcp_scripts.py:73-79`), não interpolados. **Risco residual**: é execução de Python no processo do Fusion sobre porta loopback HTTP **sem auth**. |
| **DT-010** `agent_loop` corretivo | **NÃO VERIFICÁVEL nesta branch** | `agent_loop.py` **ausente** (ver §5). Permanece como alvo de integração da Fase 2; não há código aqui para auditar. |

Achados de apoio: **executor não tem loop de auto-correção** (é `for step in plan.steps` linear; em `ok:False` marca `failed` e segue — `executor.py:162-329`); **`build_correction_context` não existe** (zero matches; o que há é `build_edit_context_block` para edição P5, `planner.py:444`).

## 3. Realidade do transport MCP (insumo do ADR-017)

Hoje coexistem **três** caminhos, e **em todos o backend é CLIENTE** — o produto **não expõe** servidor MCP algum:

| Caminho | Onde | Transport | É MCP de verdade? |
|---|---|---|---|
| **Autodesk Fusion MCP Server** (preferido) | `fusion_adapter.py:168-184,540-580` | HTTP JSON-RPC (+SSE de resposta) em `127.0.0.1:27182/mcp` | Sim — mas é servidor **da Autodesk**; nós somos cliente (`initialize` proto `2025-06-18`, `tools/list`, `tools/call`). **Sem auth no caminho HTTP.** |
| **Bridge loopback legado** (fallback) | `fusion_adapter.py:621-676` | TCP socket cru + JSON-RPC + handshake `auth` por token | Não — protocolo caseiro (add-in em `apps/fusion-addin/`). |
| **`mcp_servers/` stdio** (interno) | `_server_base.py`, `fusion_server.py`, `blender_server.py` | stdio (subprocesso) | **Não** — subset deliberado (`protocol.py:1-11`): só `tools/list|call|status|shutdown`; **sem** `initialize`/capabilities/resources/prompts, sem HTTP/SSE, sem auth. É o "esqueleto interno". |

**Conclusão**: `mcp_servers/` **não** é o servidor MCP standalone que o v4 quer; é o ponto de partida a substituir. A maior dívida não está num módulo — está na **fronteira**: o caminho preferido (27182) roda Python no Fusion **sem autenticação**. ADR-017 (servidor standalone HTTP/SSE+auth, backend vira cliente dele) e ADR-019 (fronteira do script) atacam exatamente isto.

## 4. Inventário das ~50 tools do adapter Fusion + status real-Fusion (T0.6)

`tool_registry` define **51 tools Fusion** (`FUSION_TOOLS`); **50 executáveis** (`fusion.run_script` excluído); a tupla geradora `FUSION_SCRIPT_TOOLS` (`fusion_mcp_scripts.py:7-46`) lista **38**. **Nenhuma tool tem validação automatizada contra Fusion real** — toda evidência é fix-by-trace manual no `handoff.md`.

**Distribuição de status**: ~11 `validada-no-fusion-real` (várias só **parcialmente**, via correção de drift) · ~7 `version-sensitive` · ~15 `nunca-rodada` · 2 `desconhecido`.

| Tool | Categoria | Status real-Fusion | Evidência |
|---|---|---|---|
| `fusion.open_design` | doc/additive | nunca-rodada (comportamento de doc a validar) | handoff:50-51 |
| `fusion.create_sketch` | sketch | **validada** | handoff:494 (Fix #2/#8), traces de sketch |
| `fusion.add_rectangle` | sketch | **validada** | handoff:497 (Fix #6/#9), trace placa |
| `fusion.add_circle` | sketch | **validada** | handoff:355-356; `test_add_circle_accepts_aliases` |
| `fusion.add_line` | sketch | **validada** (parcial/drift) | handoff:196-198 (trace bola `mt_019e45f8c20e`) |
| `fusion.add_arc` | sketch | **validada** (parcial/drift) | handoff:196-197 |
| `fusion.add_ellipse` | sketch | nunca-rodada | roadmap G3:134 |
| `fusion.add_slot` | sketch | nunca-rodada | roadmap G3:134 |
| `fusion.add_polygon` | sketch | nunca-rodada | handoff:359-360 |
| `fusion.add_spline` | sketch | nunca-rodada | handoff:306 |
| `fusion.add_box` | primitive | **validada** | handoff:148-154 (drift `dimensions_mm`) |
| `fusion.add_cylinder` | primitive | nunca-rodada | adapter-tools-mvp:61-68 |
| `fusion.add_sphere` | primitive | **validada** | handoff:273 (trace `mt_019e4623c801`) |
| `fusion.add_cone` | primitive | nunca-rodada | adapter-tools-mvp:61-68 |
| `fusion.extrude_profile` | feature | **validada** | handoff:494/497/534 (prisma 50×30×100) |
| `fusion.revolve_profile` | feature | **validada** (parcial) | handoff:199,204 |
| `fusion.fillet_edges` | feature | version-sensitive | roadmap G5:166-170; handoff:332-335 |
| `fusion.chamfer_edges` | feature | version-sensitive | roadmap G5:167 (`createInput` vs `createInput2`) |
| `fusion.shell_body` | feature | **validada** (parcial) | handoff:281-283 |
| `fusion.hole` | feature | **validada** | handoff:89-107 (trace `mt_019e46e06f3b`) |
| `fusion.pattern_rectangular` | feature | version-sensitive | roadmap G5:169 |
| `fusion.pattern_circular` | feature | **validada** parcial + version-sensitive | handoff:277-279 |
| `fusion.mirror_feature` | feature | nunca-rodada | handoff:294-308 |
| `fusion.combine_bodies` | feature high_risk | nunca-rodada | handoff:305-308 |
| `fusion.loft_profiles` | feature | nunca-rodada | handoff:304-306 |
| `fusion.sweep_profile` | feature | version-sensitive | roadmap G5:170 (`createPath`) |
| `fusion.move_body` | feature | version-sensitive | roadmap G5:168 (API deprecada) |
| `fusion.scale_body` | feature | version-sensitive | roadmap G5:168 |
| `fusion.split_body` | feature | nunca-rodada | handoff:236 |
| `fusion.add_construction_plane` | construction | nunca-rodada | handoff:305-306; roadmap G3:141 |
| `fusion.set_parameter` | param | **validada** | handoff:493 (Fix #1/#10), trace `mt_019e46942241` |
| `fusion.query_geometry` | query (read-only) | nunca-rodada | handoff:231-233,244-245 |
| `fusion.validate_dimensions` | query (read-only) | **validada** | handoff:92-94 |
| `fusion.validate_printability` | query (read-only) | **validada** | handoff:92-93 (trace `mt_019e46e06f3b`) |
| `fusion.export_stl` | export | **validada** | handoff:273,534 (Fix #5) |
| `fusion.export_step` | export | desconhecido | sem trace de STEP |
| `fusion.export_3mf` | export | desconhecido | Fix #5 guard; sem trace de sucesso |
| `fusion.run_script` | high_risk | N/A (nunca exposto) | `fusion_adapter.py:53-55`; `tool_registry.py:429-432` |

> A diferença 50 (executáveis) × 38 (`FUSION_SCRIPT_TOOLS`) é trabalho a confirmar na geração; tratar tools fora da tupla como `nunca-rodada` até prova em contrário.

### Candidatas a smoke da Fase 1

Pipeline ponta-a-ponta priorizando tools já **validadas** (falha = regressão clara):

**`open_design → create_sketch → add_rectangle → extrude_profile → validate_printability → export_stl`**

É essencialmente o caso "prisma 50×30×100" (primeiro end-to-end bem-sucedido, handoff:534) — bom baseline de regressão para um cliente externo (ex.: Claude) validar o servidor MCP standalone. Incluir `query_geometry` no smoke mesmo sendo `nunca-rodada`: é a leitura de estado central do v4 (Fase 3) e vale validá-la cedo.

## 5. Assets do fidelity-roadmap (T0.6b) — convergência de branches pendente

**Confirmado ausentes nesta branch** (`find`/`git ls-files` sem resultado):

- `specs/005-modeling-3d-fusion/fidelity-roadmap.md` — **ausente**
- `backend/app/modeling/agent_loop.py` — **ausente**
- `backend/app/modeling/tool_schemas.py` — **ausente**
- `planner.build_correction_context` — **inexistente** (só há `build_edit_context_block`)

São descritos como **não-commitados no worktree `master`** de outra sessão (`spec.md:211-212,219`), formalmente **absorvidos pelo v4** como insumo das Fases 2/4/8. **Não há como auditar o que não está na árvore.** A Fase 2 depende de **convergir as branches** (merge/clone fresco) antes de partir do `ModelingAgentLoop`; até lá, DT-010 é planejamento, não auditoria. **Risco mantido**: duas sessões editando o mesmo módulo → escolher uma fonte de verdade.

## 6. Catálogo de inconsistências de documentação (T0.10) — backlog da Fase final

Para reconciliar na **Fase final** (não "consertar" agora — evita retrabalho enquanto o código v4 ainda muda):

| # | Inconsistência | Local (verificado) | Ação na Fase final |
|---|---|---|---|
| D1 | Modos legados `safe_auto`/`plan_only`/`approval_required` e gate "sempre PARA" | `docs/3d-mcp-modeling.md` (5 ocorrências) | Remover; alinhar ao ADR-013 (modos removidos) + execução fim-a-fim do v4. |
| D2 | Endpoints removidos ainda documentados | `docs/api.md:102` (`POST /api/3d/plans/{id}/approve`), `:104` (`POST /api/3d/steps/{id}/approve`) | Remover/atualizar (aprovação é inline no chat, DT-006). |
| D3 | **Caminho pessoal vazado** em doc versionada | `docs/local-dev.md:5` (caminho pessoal `C:\Users\...`) | ✅ **Corrigido nesta fase** — substituído pela referência versionada `specs/005-modeling-3d-fusion/observability-plan.md`. |
| D4 | 27182/stdio apresentados como atuais, não como legado/upstream | `docs/3d-mcp-modeling.md`, ADR-012 | Reposicionar como upstream/legado sob o servidor standalone (ADR-017). |
| D5 | ADR-012/013 parcialmente superados | `docs/decisions.md` | Marcar superações por ADR-017 (transport/exposição) e nota de evolução do fluxo. |
| D6 | Documentação dupla 3D inexistente no Docusaurus | `apps/docs` | Criar categoria/landing 3D cobrindo os 5 níveis + servidor MCP (RNF-007). |

## 7. T0.11 — alinhamento de UI (RNF-009): **desbloqueado**

A premissa do plano ("`homolog-new-ui` não acessível neste container") **não vale mais**: o re-skin v4 foi mergeado na `master` via **PR #42** e esta branch já o inclui (base `f0cbe62`). Logo a UI nova (`apps/web/src/components/ui/*`, `features/chat`, `features/dashboard`) **está presente**. A passada de refactor de `apps/web/src/features/modeling-3d/` para alinhar à nova UI fica **pronta para ação**, mas é esforço de fase com entrega de UI (não de doc) — recomendo executá-la nas fases que tocam UI (2+), não na Fase 0. Atualizar `plan.md` › Pendências de ambiente neste sentido faz parte do gate.

## 8. Síntese / recomendação de sequência (Fase 0 → 1 → 2)

1. **Resolver DT-006 primeiro** (decisão de arquitetura): promover `chat_orchestrator` ao caminho vivo enxugando `chat_modeling.py`, **ou** oficializar a rota e aposentar o orchestrator. Sem isso, o loop agêntico da Fase 2 nasceria sobre duas máquinas de estado divergentes.
2. **ADR-017** habilita a Fase 1 (servidor MCP standalone): substituir as cascas stdio (`fusion_server`/`blender_server` = `reescrever`), evoluir `_server_base`/`mcp_client`/`stdio_client`, **fechar o gap de auth** do caminho 27182.
3. **DT-008 + executor**: introduzir estado de falha/correção distinto e fatiar `execute_plan` com ponto de extensão **antes** de construir o loop (Fase 2).
4. **DT-007** (rápido, baixo risco): logar o `except` do ramo `auto` em `storage/store.py`.
5. **Convergir branches** (fidelity) antes da Fase 2; **reescrever `snapshot_service`** para rollback nativo do Fusion (DT-005).

## Definição de pronto (Fase 0) — estado

- [x] Inventário de auditoria com veredito por peça (T0.5).
- [x] Status real-Fusion das tools mapeado + candidatas de smoke (T0.6).
- [x] Assets do fidelity confirmados ausentes; convergência registrada (T0.6b).
- [x] ADR-017, ADR-018, ADR-019 rascunhados em `docs/decisions.md` (T0.7/T0.8/T0.9).
- [x] Inconsistências de doc catalogadas para a Fase final (T0.10).
- [x] T0.11 reavaliado (desbloqueado).
- [ ] **Gate do dono** (T0.12): aprovação do inventário + ADRs → libera Fase 1.
