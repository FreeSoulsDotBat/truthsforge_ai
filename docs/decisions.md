# Decisoes

## ADR-001 - Monorepo

Usar um unico repositorio com frontend compartilhado, wrappers desktop/mobile, backend e infra. Isso reduz atrito para uma aplicacao pessoal e facilita evoluir contratos entre UI e API.

## ADR-002 - FastAPI e Python

Backend em Python 3.11 com FastAPI para favorecer processamento de arquivos, RAG, engenharia de prompts, agentes e ciencia de dados.

## ADR-003 - React/Vite + Tauri + Capacitor

Uma base React responsiva gera web, desktop e mobile. Tauri fica como wrapper Windows e Capacitor como wrapper Android. Instaladores completos ficam depois do dev loop estar estavel.

## ADR-004 - Postgres + Qdrant

Postgres e a fonte transacional de producao local. Qdrant e o indice vetorial principal por performance, filtros e tuning dedicado. O backend usa a interface `VectorStore` para permitir troca futura para pgvector/LanceDB.

O store JSON permanece apenas como fallback de desenvolvimento/testes quando Postgres nao esta disponivel. Ele nao deve ser tratado como formato de producao, nem como caminho de sincronizacao entre dispositivos. Para rodar o produto completo, use Postgres + Qdrant + Valkey pelo Docker Compose.

O modulo 3D pode guardar arquivos pesados no filesystem local e metadados no store principal. Apesar da proposta inicial de SQLite para um servico 3D isolado, a aplicacao consolidada mantem Postgres como fonte transacional unica para reduzir divergencia entre chat, agentes, RAG, auditoria, custos e modelagem.

Payloads `JSONB` sao aceitos no MVP para acelerar iteracao. Quando houver volume real, as rotas mais quentes devem ser normalizadas primeiro: mensagens, chunks/documentos, auditoria, permissoes, tool calls e politicas de retencao.

## ADR-005 - LangGraph/LangChain para agentes

LangGraph/LangChain entram para fluxos agentic com estado, checkpoint humano e multiplos passos. A aplicacao ainda mantem politicas, permissoes e auditoria em codigo proprio.

## ADR-006 - Seguranca mobile

O acesso remoto padrao sera por Tailscale/WireGuard. Portas HTTPS publicas ficam fora do MVP inicial para reduzir risco.

## ADR-007 - Modelos locais

Chat fica restrito a OpenAI, Anthropic e Google. Modelos locais podem ser usados para embeddings, reranking, OCR auxiliar e outras tarefas de infraestrutura que reduzam custo.

## ADR-008 - Governança SDD por domínio

Mudanças relevantes devem referenciar uma spec/task. Quando a frente exceder ajuste pontual, a spec deve viver em `specs/<slug-do-dominio>/`, separada do baseline `repo-foundation`.

Toda entrega relevante deve incluir o checklist obrigatório de `docs/delivery-checklist.md`. Antes de alterar a plataforma, o executor deve confirmar com o dono do produto o nome da branch e a mensagem de commit em formato semântico.

## ADR-009 - Autonomia de agentes e tools

JUDITE deve evoluir como orquestradora que delega contexto e coordena workflows multi-etapa com checkpoints humanos. Agentes e tools podem executar adições sem aprovação quando a policy permitir. Alterações e deleções exigem aprovação humana.

Tools de escrita ou execução devem operar em diretório isolado por projeto, com rede permitida no MVP, timeout e limites de tamanho definidos pela implementação, auditoria e rollback obrigatório.

## ADR-010 - RAG, dados sensíveis e provedores externos

Documentos indexados podem compor prompts enviados a OpenAI, Anthropic ou Google quando esses provedores estiverem configurados. Conteúdo sensível deve ser classificado por controle manual e heurística automática, com rastreabilidade na auditoria.

O fluxo automático assistido de importação ChatGPT para bases revisadas não faz parte do MVP imediato.

## ADR-011 - Mobile MVP sem autenticação de usuário

O pareamento mobile inicial deve usar QR code local. Para o MVP, não haverá autenticação de usuário no mobile; o cliente pareado pode manter cache offline completo.

## ADR-012 - 3D/Fusion obrigatório no MVP

Blender real e Fusion conectado são obrigatórios para a trilha atual de modelagem 3D. Fusion deve ser tratado como spec própria do bounded context 3D, com planner, policy, snapshots, rollback, printability, exports e artifacts rastreáveis. O caminho preferido é o Fusion MCP Server local do próprio aplicativo (`/mcp` na porta exibida pelo Fusion, padrão `27182`); o bridge loopback legado permanece apenas como fallback compatível.

## ADR-013 - 3D chat-first integral; remoção do painel; aprovação inline

A experiência de modelagem 3D passa a ser **integralmente conduzida pelo chat**. O painel 3D do dashboard é removido. Configuração de adapters (Blender path, Fusion MCP URL, transports) migra para Configurações gerais. Diagnóstico operacional (capabilities, sessões, snapshots, tool calls, model versions, printability reports) vira modal read-only acessível pelo cabeçalho do chat 3D.

Cada chat marcado como 3D segue uma **state machine única**:

```
created (title obrigatório) → discovery → planning → approved → executing → editing ↺
                                              ↑                                ↓
                                              └────── (rejeição) ──────────────┘
```

> DT-008 (posterior) adicionou um estágio `failed` distinto: uma execução que
> falha vai para `failed` (não `editing`), para o loop agêntico e a UI
> distinguirem um run quebrado; a recuperação usa os mesmos eventos de
> edição/retry. Ver `backend/app/modeling/chat_state.py`.

A flag `is_modeling_3d` é por chat, persistida e imutável após criação. Ativar 3D em um chat com histórico não-vazio abre modal que oferece criar um novo chat 3D vazio; não há cópia de mensagens entre chats.

A UI **não expõe mais o seletor de modos** (`plan_only`/`approval_required`/`safe_auto`): o chat sempre usa o fluxo fluido (`safe_auto`). O enum `ModelingExecutionMode` **permanece** no contrato interno (`backend/app/core/contracts.py`; `plan_only` ainda força rascunho) — apenas não há mais escolha na interface. Sempre que o agente julgar que tem contexto suficiente, propõe o plano e o backend transiciona o chat para `planning`. O plano aparece no chat como `ModelingPlanCard` com prosa, etapas, badges de risco, banner de aviso para etapas high-risk e dois botões: "Aprovar" e "Rejeitar" (com campo opcional de motivo). Texto livre **não** aciona execução.

A aprovação global do plano cobre todas as etapas, incluindo high-risk (`apply_boolean`, `repair_non_manifold`, `restore_snapshot`, `run_script`). Não há mais aprovação step-a-step após o plano primário aprovado. Edições posteriores (estado `editing`) geram mini-planos auto-aprovados quando só contêm tools allowlistadas não-high_risk; ao tocar em high-risk, o card volta a pedir aprovação inline. Snapshots manuais, rollback explícito, allowlist e auditoria permanecem como guardrails obrigatórios.

A descoberta de contexto aceita anexos com análise profunda: imagens via vision do gateway LLM e arquivos 3D (`STL`/`OBJ`/`STEP`/`3MF`/`BLEND`) via Blender headless extraindo bounding box, contagens, volume, simetria, features e sugestões iniciais.

A allowlist de tools deixa de viver em três arquivos espalhados (`planner.py`, `policy.py`, adapters) e passa a derivar de uma única fonte (`backend/app/modeling/tool_registry.py`) para eliminar divergência silenciosa.

A trajetória de implementação está descrita em `specs/005-modeling-3d-fusion/plan.md`. O replan v4 (ADR-021) reorganizou as ondas originais em frentes de capacidade **F1–F6** (estado rico → planejamento agêntico → mecanismos → image-to-model → edição robusta → determinismo); a virada para o motor genérico está em **ADR-020**.

## ADR-014 - Título de chat obrigatório; remoção da auto-titulação OpenAI

Todo chat (3D ou não) passa a exigir título não vazio antes da primeira mensagem. O frontend bloqueia o input de envio e exige nomeação imediata; o backend rejeita `POST /api/chat/stream` com `HTTP 422` quando `chat.title` estiver ausente ou vazio.

O serviço/endpoint atual que chama a OpenAI para gerar título automático é **removido**, eliminando consumo de tokens dessa chamada. A migração que torna `chats.title NOT NULL` aplica backfill `"Sem título - YYYY-MM-DD"` (derivado de `created_at`) aos chats existentes para preservar dados sem quebrar a constraint.

A motivação combina três pontos: (1) economia de tokens em uma chamada que não agrega valor consistente, (2) clareza explícita de propósito do chat desde o início, (3) suporte ao novo fluxo 3D, onde o título distingue rapidamente sessões de modelagem na sidebar (junto com o `ChatModeling3DBadge`).

Renomeação posterior do chat continua permitida via UI. A obrigatoriedade vale apenas para a transição "chat criado → primeira mensagem enviada".

## ADR-015 - Abstração de storage (interface Store)

**Status: Aceita (spec 070 ratificada); implementação pendente.** Hoje
`get_store()` (`storage/store.py`) ainda retorna `Any` e **não existe** um
`Protocol Store` em `backend/app/storage/` — a decisão foi aprovada mas o código
ainda não a reflete.

A camada de storage passa a ter uma **interface única** descrita por um `typing.Protocol` `Store` em `backend/app/storage/`, derivada da superfície atual já compartilhada por `PostgresStore` (`postgres_store.py`) e pelo dev-store JSON (`dev_store.py`). `get_store()` (`storage/store.py`) passa a ser tipado como `Store`.

Motivação: hoje os dois stores duplicam ~46 métodos sem contrato comum (~3390 linhas), o que gera risco de divergência silenciosa quando uma assinatura muda em apenas um deles.

A decisão **não troca a stack** (P5/ADR-004 permanecem: Postgres é produção; JSON é apenas dev/test). A implementação é **faseada e de baixo risco**: (1) teste de paridade que garante superfície idêntica entre os dois stores; (2) `Protocol Store` extraído da superfície atual, sem alterar implementações; (3) opcionalmente, fatiamento futuro em repositórios por domínio, um por vez, com testes. Cada fase roda os gates de `scripts/quality.ps1` antes de concluir.

Spec e plano: `specs/070-storage-persistence/` (ver `research.md`).

## ADR-016 - Geração de tipos do contrato a partir do OpenAPI

**Status: Proposta (dívida DT-003 em aberto; spec 140 em rascunho).** Ainda não
implementada: `apps/web/src/types/api.ts` segue mantido à mão (~750 linhas) e não
há `openapi-typescript` (nem script de geração) no toolchain.

Os tipos do contrato consumidos pelo frontend deixam de ser mantidos à mão em `apps/web/src/types/api.ts` (740 linhas) e passam a ser **gerados a partir do OpenAPI do backend** (`apps/web/src/types/openapi.json`, hoje já exportado mas não usado), via `openapi-typescript` (ou equivalente leve).

Motivação: eliminar o drift silencioso entre backend e frontend, no qual uma mudança de contrato no FastAPI não se reflete nos tipos manuais.

Por ser **mudança de toolchain de build** (nova dependência de dev + passo de geração), a adoção entra em um PR controlado próprio, com `typecheck`/`build` verdes e os tipos gerados versionados ou gerados no build. Sem dependências pesadas em runtime (P-Frontend de `AGENTS.md`).

Spec e plano: `specs/090-frontend-web-shell/` (dívida DT-003).

## ADR-017 - Servidor MCP standalone para modelagem 3D (local-first + auth)

**Status: Aceito (gate Fase 0 aprovado em 2026-05-24; implementado na Fase 1 — `backend/app/modeling/mcp_standalone/`).** Referências: P1, P2, P6; RNF-001; supera parcialmente ADR-012 (transport/exposição).

**Contexto.** Hoje o backend é **cliente** em todos os caminhos MCP da modelagem 3D e o produto **não expõe** servidor MCP algum (ver auditoria `specs/005-modeling-3d-fusion/micro/fase-0-auditoria.md` §3). Coexistem: (a) o **Autodesk Fusion MCP Server** em `127.0.0.1:27182/mcp` (HTTP JSON-RPC, caminho preferido — porém **sem autenticação**); (b) um **bridge TCP loopback legado** com token; e (c) `backend/app/modeling/mcp_servers/` — um esqueleto **stdio** que é, por desenho (`protocol.py:1-11`), um subset do MCP (só `tools/list|call|status|shutdown`, sem `initialize`/capabilities/resources/prompts, sem HTTP/SSE, sem auth). O dono quer que as operações 3D fiquem atrás de um **servidor MCP standalone reutilizável**, para que outros clientes (ex.: Claude) as usem sem reengenharia futura.

**Decisão.** Criar um **servidor MCP standalone, MCP-compliant**, que expõe as tools Fusion já confiadas (ver inventário §4) com:
- **Protocolo real**: `initialize`/handshake + capabilities + `tools/*` (e `resources/*`/`prompts/*` quando fizer sentido), substituindo o subset stdio interno.
- **Transport HTTP + SSE** (streaming), aposentando o stdio in-process como caminho-alvo.
- **Local-first (P1)**: bind em loopback por padrão; acesso remoto **apenas** via VPN/pareamento (Tailscale/WireGuard); **proibida** exposição pública ingênua.
- **Autenticação obrigatória em toda conexão** (RNF-001), inclusive no caminho loopback HTTP — **fechando o gap de auth atual** do 27182.
- **Backend como cliente** do servidor (evolui a boundary `LocalMCPClient`); o caminho Autodesk 27182 e o bridge TCP permanecem como **upstream/fallback** sob o servidor, não como superfície exposta.

**Consequências.** `mcp_servers/_server_base.py` + `protocol.py` evoluem ou são trocados por um SDK MCP real; as cascas `fusion_server.py`/`blender_server.py` (backend servindo a si mesmo via stdio) viram becos → **reescrever** (auditoria §1); `mcp_client.py`/`stdio_client.py` adaptam-se ao novo transport (stdio tende a sair). Não há troca de stack (P2): é componente novo dentro da stack atual. Precede a **Fase 1**; gate = cliente externo conecta + smoke das tools no Fusion real.

## ADR-018 - Reabrir "single-body" → cobertura "todo o Design" (assemblies)

**Status: Rascunho — parcialmente revogado por ADR-021 + DT-011/DT-012.** A tese
central deste ADR (cobrir **todo o Design**, incluindo sheet metal e sculpt) foi
abandonada: **sheet metal** (DT-011) e **sculpt** (DT-012) são tetos da
plataforma e ficaram **congelados**; o programa virou de "cobertura de
workspaces" para "capacidades de sólidos mecânicos" (ADR-021). A parte de
**assemblies** sobrevive, mas foi **absorvida pela frente F3** (já entregue
`fusion.make_component` e `fusion.joint`), não mais como "Fase 8 por último".
Referências: P8; RNF-005; **supera `specs/005-modeling-3d-fusion/g4-assemblies-decision.md`** (decisão "single-body" de 2026-05-20).

**Contexto.** Em 2026-05-20, o dono escolheu **manter single-body** (Opção A) porque o caso dominante era peça única imprimível e assemblies eram over-kill (`g4-assemblies-decision.md`). O v4 redefine a cobertura-alvo como **todo o workspace Design** (sólido, superfície, sheet metal, sculpt **e** assemblies/componentes/juntas/materiais), o que reabre aquela decisão. Mudança no data model do plano exige ADR antes de virar código (RNF-005, P8).

**Decisão.** Adotar **"todo o Design"** como cobertura-alvo; assemblies/componentes/juntas/materiais entram no escopo, entregues **por último (Fase 8)**, depois do núcleo estável.

**Consequências (4 eixos de impacto).**
1. **Data model do plano**: de "um design = N bodies" para **árvore de componentes** com ocorrências e juntas.
2. **Selectors/refs**: de `body > face` para `componente > ocorrência > body > face` (estende G2.2/G2.3).
3. **UI do card**: representar **hierarquia**, não lista linear de steps.
4. **Printability/export por componente**: peça de assembly pode exportar separada ou montada → afeta `validate_printability` e exports (um STL por componente).

As APIs de junta do Fusion são complexas e **version-sensitive** (risco G5). Por isso a Fase 8 é isolada e a última das ondas de cobertura. `g4-assemblies-decision.md` fica **superado** por este ADR.

## ADR-019 - Fronteira de segurança do script Python backend-owned (`featureType:"script"`)

**Status: Rascunho (Fase 0).** Referências: P6, P8; RF-023; formaliza DT-009.

**Contexto.** O adapter Fusion executa cada operação **enviando um script Python completo** ao Fusion via a tool de execução da Autodesk com `featureType:"script"` (`fusion_adapter.py:475-479`; script gerado por `fusion_mcp_scripts.build_autodesk_fusion_script`, `:470`). Isso é, na prática, **execução de Python no processo do Fusion** — a maior superfície de ataque do bounded context, hoje agravada por o caminho HTTP 27182 não ter auth (ver ADR-017).

**Decisão.** Formalizar que o caminho `featureType:"script"` é permitido **exclusivamente** para scripts **backend-owned, determinísticos e derivados da allowlist** — **nunca** para script fornecido pelo modelo ou pelo usuário. Controles que sustentam a decisão (já presentes, aqui tornados invariante):
- O LLM escolhe **apenas** `tool_name` + args; o **script é gerado pelo backend** de forma determinística (`fusion_mcp_scripts.build_autodesk_fusion_script`).
- `fusion.run_script` fica **fora** da allowlist do adapter (`fusion_adapter.FUSION_TOOLS` exclui `*.run_script`) e da visão do planner (`tool_registry._planner_visible()` exclui `*.run_script`) — existe só para policy/auditoria.
- Args entram como **JSON desserializado em runtime** (`json.loads` em `fusion_mcp_scripts.py`), nunca interpolados como literal Python (defesa de injeção).
- **Auditoria por tool-call** + **auth no transporte** que carrega o script (vínculo direto com ADR-017).

Isso respeita **RF-023** (sem script livre/shell/destrutivo no caminho feliz) na letra e no espírito.

**Consequências.** O gerador `fusion_mcp_scripts.py` permanece uma **fronteira controlada** (veredito `evoluir`: refatorar a forma — f-string de ~2,5k linhas — sem afrouxar a fronteira). Qualquer mudança que permita conteúdo **não-backend** chegar ao `featureType:"script"` é violação de nível constitucional (P6/P8). O **gap de auth do loopback** (DT-009) é defeito a corrigir na Fase 1 junto com ADR-017.

## ADR-020 - Motor genérico 3D: composição + verificação (visual/geométrica) em vez de macros de produto

**Status: Aceito (2026-06-02).** Referências: P3, P6, P8; spec 005 (frentes F3/F6). Origem: a virada de "macros de produto" para "motor genérico" (commits `a211826`, `146fe8f`, `1e68ab4`).

**Contexto.** A Fase 3 entregou macros paramétricas de PRODUTO (`fusion.knuckle_hinge`, `fusion.metric_screw`) como tools de alto nível. Ao expandir para mais mecanismos ficou claro que **uma macro por produto não escala** (são milhares de produtos) e concentra a inteligência no lugar errado: o difícil não é ter a feature, é **posicionar/dimensionar pela geometria real** e **saber se o resultado corresponde à intenção**.

**Decisão.**
1. **Composição genérica.** O planner compõe peças funcionais a partir de **primitivas** + **features genéricas reutilizáveis** (`thread`, `joint`, `pattern_rectangular`/`pattern_circular`, `mirror_feature`, `make_component`, `combine_bodies`), posicionando tudo pela geometria REAL consultada (`query_geometry`/F1). Os macros de produto são **deprecados do planner** — `tool_registry.DEPRECATED_PLANNER_TOOLS = {fusion.knuckle_hinge, fusion.metric_screw}` (handlers permanecem só para backward-compat/smoke; o system prompt ensina a compor: "Não existem tools de produto pronto — a peça é sempre COMPOSTA").
2. **Sanitizer determinístico pós-LLM (F6).** Camada entre planner e executor (`plan_sanitizer.py`, flag `modeling_plan_sanitizer_enabled`, **default ON**) que remove campos-fantasma e referências geométricas inventadas (`face:"X.top_face"`, `bounding_box.max_x`) que os nudges do prompt não eliminam 100%. Conservador: só descarta o que nenhum handler aceita; planos válidos passam intactos, com telemetria por aviso. (É a peça de "determinismo do LLM" reservada como ADR-020 no plan/tasks/`micro/fase-9-llm-determinism.md`.)
3. **Verificação dupla no loop.** (a) **Geométrica** — read-back de dimensões/área medidas × esperadas (`build_dimension_verifier`/`build_surface_verifier` em `agent_loop.py`); (b) **Visual** — render do viewport (`fusion.capture_viewport`) → crítica por LLM de visão (gateway multimodal F4) → replan corretivo (`visual_critique.py`, flag `modeling_visual_verification_enabled`, default OFF, teto `modeling_visual_max_rounds`). É o que faz a composição se auto-corrigir em qualquer produto, sem código por caso.

**Consequências.** Backward-compat (handlers dos macros seguem; flags de verificação OFF = comportamento atual). A robustez passa a vir de **composição + estado rico (ADR-021) + verificação**, não de catálogo de macros. `capture_viewport`/`query_timeline`/`query_geometry` ficam **fora** do `PLANNER_TOOLSET` (probes internos do loop/reconciliação). Implementação nas frentes **F3** (mecanismos genéricos) e **F6** (determinismo/sanitizer) + passo 3 do motor (verificação visual em `micro/fase-F3-mecanismos.md`).

## ADR-021 - Estado rico do modelo + planejamento agêntico/hierárquico (replan v4)

**Status: Aceito (2026-05-29).** Referências: P3, P8; spec 005 (capacidades P1–P4). Origem: replan de "cobertura de workspaces" para "capacidades de sólidos mecânicos".

**Contexto.** Os gates de 2026-05-28/29 validaram o núcleo (criação de sólidos+superfícies, loop agêntico, edição, parametrização) mas expuseram que **gerar peças mecânicas complexas** (dobradiça/knuckle, parafuso que encaixa, suporte articulado) esbarra numa **fundação rasa**, não em features faltando: (a) `query_geometry` só dá índices posicionais frágeis de face/edge; (b) o contexto entre etapas do plano é **textual** (nomes de timeline/params), não geométrico; (c) o planejamento é **one-shot e flat**. O planner não sabe *onde* colar a dobradiça nem mede o estado real entre passos.

**Decisão.**
1. **Identidade estável** de face/edge via `BRepFace.entityToken`/`BRepEdge.entityToken` (sobrevivem a recompute), expostos no `query_geometry` e aceitos pelos selectors (precedência token > índice posicional > selector semântico). (Rejeitado anexar attribute por face — não sobrevive a operações que recriam BRep.)
2. **`ModelState` estruturado** persistido em `ModelingPlan.model_state` (JSONB), capturado pós-execução via probe `query_geometry` e injetado no contexto do planner entre etapas e em edições.
3. **Planejamento hierárquico** (atrás de flag `modeling_hierarchical_planning_enabled`): o LLM decompõe o pedido em sub-objetivos e planeja cada bloco fino **observando o `ModelState` real** do bloco anterior (loop decompor→executar→observar→replanejar), reusando o `ModelingAgentLoop` para correção de step.

**Consequências.** Backward-compat total (flags OFF = comportamento atual; campos aditivos). Custo: 1 probe `query_geometry` por plano + chamadas LLM extras no modo hierárquico. **Sem rede neural** — a robustez vem de estado rico + orquestração agêntica + verificação geométrica + (F3) biblioteca de macros paramétricas. Implementação nas frentes **F1** (`micro/fase-F1-estado-rico.md`) e **F2** (`micro/fase-F2-planejamento-agentico.md`).

## ADR-022 - Posicionamento paramétrico: referência espacial declarativa + montagem nativa (Front F7)

**Status: Aceito (2026-06-03).** Referências: P1 (peças mecânicas), spec 005 Front F7; micro `micro/fase-F7-posicionamento.md`; débito `tech-debt-posicionamento.md`.

**Contexto.** Mesmo com o motor genérico (composição + loop visual) validado no Fusion real, o **posicionamento relativo de corpos** continua frágil: todo placement é **coordenada absoluta em mm** que o LLM **calcula na mão** (cada primitiva nasce na origem; mecanismos exigem ler a geometria e codificar `origin_mm`/`axis` de cada peça). Gates: knuckles no lado errado, pino flutuando, tampa solta, corpos fora de lugar, referência a corpos inexistentes. O nudge até **proíbe** as refs declarativas naturais (`Placa.top_face`, `bbox.max_x`) porque nenhum handler as suporta. É um **limite arquitetural** (o "onde colocar"), não um bug — não fecha com fixes incrementais. Decisão do dono: refatorar como Front F7.

**Decisão.**
1. **Camada de referência espacial declarativa.** Gramática que referencia geometria por **token estável** (F1) + ponto/eixo semântico (face center/normal, edge along/midpoint/direction, body bbox/center), em forma objeto e `@`-string nos campos existentes — **fazendo as refs hoje-proibidas FUNCIONAREM** (`@token('<face>').center.z`, `@edge('<edge>').along(0.2)`, `@body('X').bbox.max_z`). Fora da gramática → `fusion.spatial_ref_unresolved` (nunca chuta).
2. **Resolver determinístico no BACKEND** (pré-pass sobre `ModelState`, não in-script). Tools Fusion são one-shot sem `adsk` vivo entre passos; o backend reusa o probe `query_geometry` já validado (seam de `capture_model_state`). Resolver sobre `ModelState` é 100% testável em mock (como `plan_sanitizer`); in-script seria API-blind. A matemática de coordenada sai do LLM e vai p/ código determinístico (filosofia do sanitizer F6). (`fusion.place_body` in-script = follow-up só se a latência do probe doer.)
3. **Placement PARAMÉTRICO via montagem nativa** (escolha do dono): o resolver emite **componentes + joints** (rigid/planar p/ fixo, revolute p/ movimento) das JointGeometry resolvidas dos tokens — **sobrevive a recompute**, ao contrário de transform assado. (Rejeitado o 1º corte "baked" — o dono priorizou robustez paramétrica desde já; o custo é complexidade + API-blind, mitigado gateando a fundação de montagem antes.)
4. **Modelo assembly-aware — combine-DENTRO, joint-ENTRE.** Os nós da caixa combinam com a caixa (1 sólido imprimível) DENTRO do componente; o movimento vem de um joint ENTRE componentes. Reconcilia a tensão combine×joint que quebrou o gate da dobradiça (que combinou ENTRE componentes).

**Consequências.** Aditivo + flag `modeling_spatial_resolution_enabled` (default OFF; OFF = caminho absoluto atual intacto, step declarativo → erro claro). Reusa `_joint`/`_joint_geo_from_ref`/`_make_component`/`_pattern_*`/`_combine_bodies` + o probe + o loop visual. **Risco dominante:** a fundação de montagem (joint/make_component) é **API-blind** (escrita na F3 sem gate) — TODO o approach se apoia nela, então ela é **gateada no Fusion (P1) ANTES** da camada declarativa. Endereça `tech-debt-posicionamento.md` §3.1 (posicionamento/ancoragem) e §3.5 (combine×joint). Supersede a abordagem de coordenada absoluta como caminho principal de placement relativo.

## ADR-023 - Identidade, proveniência, auto-crítica e posicionamento por relação (Front F8)

**Status: Aceito (2026-06-08).** Referências: spec 005 Front F8; gate `specs/005-modeling-3d-fusion/gate-homologacao.md` › Gate F8. Evolui o ADR-022.

**Contexto.** O gate P6 do F7 (caixa+tampa) expôs que a infra determinística funciona, mas a **interface LLM↔geometria** é frágil em três pontos: (a) o LLM emite **token-placeholder** (`@token('<TAMPA_BOTTOM_FACE_TOKEN>')`) em vez do `entityToken` real; (b) calcula coordenada absoluta e erra (tampa em z errado); (c) o **loop de visão** "corrige" replanejando pior — cria corpos duplicados (`Caixa_fixed`/`Caixa (1)`) e trava deletes. A matemática de identidade e posição ainda mora no LLM. O dono pediu: referenciar cada entidade de forma robusta, referenciar cada operação e suas mudanças, e o sistema saber pelo histórico o que faltou/foi demais/errado/certo.

**Decisão.** A matemática de IDENTIDADE e POSIÇÃO sai do LLM e vira **código que MEDE o B-Rep**, em 4 subsistemas (mock-primeiro, flag-gated, default OFF):
1. **Referência por role/predicado** (`entity_ref`): o LLM ecoa `{body:"Tampa", role:"bottom_planar"}` ou um predicado `{face:{type:"cylindrical", radius_mm:5}}`; o backend resolve o handle estável **medindo** o `ModelState`, com desambiguação determinística → `AmbiguousRefError`. **Nunca copia hash.**
2. **Proveniência de operações** (`provenance`): cada passo mutativo emite um `ChangeRecord` determinístico (criou/modificou/consumiu/deletou + delta), casando entidades pelos handles que JÁ existem; cruza com a categoria do tool p/ marcar `uncertain` em vez de afirmar errado sob edição paramétrica.
3. **Auto-crítica estruturada** (`model_critique`): dado o esperado (`IntentSpec` derivado do plano) + o histórico + o estado, produz um `ModelVerdict` (faltou/demais/errado/certo) por checagem 100% determinística (contagem, órfão, interferência). **INVARIANTE: REPORTA, nunca auto-executa correção** — era a causa do loop ruim. Permite **desligar o juiz-de-visão**.
4. **Posicionamento por relação genérica** (`relation_derive`/`geometry_verifier`): vocabulário FECHADO (`flush_mate`/`cover_opening`/`coaxial_insert`/...) que o backend **deriva medindo** e expande nas primitivas F7 provadas. **Cada `kind` = composição de primitivas mensuráveis** (barreira codificada contra macro-por-produto). O verificador geométrico mede contato/interferência/DOF e **só reporta**; o reparo de offset é **proposto**, não aplicado.

**Invariantes (inegociáveis).** NUNCA chuta (erro tipado fora da gramática). O verificador/avaliador REPORTA, nunca corrige no escuro. Relação = composição de primitivas (não derivação por produto). Verificador geométrico é primário; o visual vira opt-in/OFF. Honestidade do crítico: não prometer o que não entrega — limitações documentadas (veredito só em build one-shot; eixo de junta default Z explícito; curvas atrás de spike; `is_open_boundary` com fallback). Mock-primeiro + flag-gated (default OFF) + **zero regressão com flag OFF**.

**Geometria × visão (um veredito, duas percepções).** Com a auto-crítica ligada, o loop visual deixa de ser um ATUADOR paralelo (que replanejava recriando corpos — a causa de `BoxOuter (1)`/`Lid (2)`) e vira um SENSOR read-only: `assess_visual_findings` renderiza + critica e devolve `Finding(source="semantic")` que entram no MESMO `ModelVerdict` (a geometria mede o quantificável — duplicata/interferência/DOF; a visão informa o que ela não mede — proporção/orientação). Nenhuma das duas replaneja sozinha. **O replan visual destrutivo (atuador) é OPT-IN explícito** (`modeling_visual_autocorrect_enabled`, default OFF): com só `modeling_visual_verification_enabled` ON, a visão PERCEBE mas NÃO recria corpos — mata o footgun de reaproveitar a env do gate F7 (visual ON) e ver a explosão de duplicados quando a visão alucina ("tampa ausente"/"groove inexistente"). O loop legado só roda com o opt-in ligado e a auto-crítica OFF.

**Consequências.** Flags próprias por subsistema (`modeling_provenance_enabled`, `modeling_self_critique_enabled`, `modeling_relation_placement_enabled`) desacoplam os gates; `fusion.relate_bodies` fica **dark no planner** (`UNRELEASED_PLANNER_TOOLS`) até o gate validar. Reusa o resolver F7 (place_body/align_axis/joint) — a relação não é motor novo. **Débitos honestos:** veredito cross-bloco (acúmulo a nível de turno) e curvas de sketch ficam pós-spike; medir o eixo de cilindro e `is_open_boundary` reais são trabalho do gate (enriquecer `query_geometry`). Gates pendentes: F8.D1 (proveniência+crítica), F8.R1 (relação), Spike de identidade sob edição paramétrica.

## DT-011 / DT-012 - Bloqueios de plataforma (sheet metal e sculpt)

**Status: Confirmado no Fusion real (2026-05-29).**

- **DT-011 — Sheet metal.** A API Python do Fusion expõe só `flangeFeatures` (coleção **read-only**, sem `add`/`createInput`); `convertToSheetMetalFeatures`/`bend`/`unbend`/`rebend` **não existem**. Sheet metal é UI-only na API → **Fase 6 congelada**; as 5 tools implementadas foram **removidas** (commit `877ac23`) para não deixar o planner escolher tools mortas.
- **DT-012 — Sculpt/T-Spline.** O workspace Form/Sculpt exige **direct mode** (timeline desabilitado), conflitando com o pipeline parametric/timeline-based; a API não expõe criação de T-Spline como feature (só "base features, sketches, combine" são custom-computáveis) → **Fase 7 congelada**. Forma orgânica é coberta por superfícies NURBS (Fase 5).

Ambos reabrem **apenas** se a Autodesk expor as APIs correspondentes ao Python parametricamente. Não são defeitos do produto — são tetos da plataforma, documentados para não serem reimplementados às cegas.
