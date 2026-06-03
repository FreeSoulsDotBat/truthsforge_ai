# Plano de implementação (MACRO): Modelagem 3D chat-first autônoma no Fusion 360 (v4)

**Pasta da spec**: `specs/005-modeling-3d-fusion/` | **Data**: 2026-05-23 | **Spec**: [`spec.md`](./spec.md)

**Entrada**: `specs/005-modeling-3d-fusion/spec.md`

> Este é o **plano macro**: a arquitetura-alvo e o roadmap de fases. Os detalhes de implementação por fase vivem em `micro/fase-N-*.md`, escritos **just-in-time** antes de cada fase (não pré-detalhamos fases distantes). O `tasks.md` é o índice vivo do progresso e dos gates.

## Resumo

Tornar o módulo 3D um produto de **autonomia de criação por chat** no Fusion 360: descoberta dirigida → plano aprovável/editável → **execução autônoma do início ao fim** com loop interno de auto-correção (teto 5) e **verificação geométrica** (read-back) → edição contínua com reconciliação de alterações manuais. As operações 3D ficam atrás de um **servidor MCP standalone reutilizável**. A cobertura-alvo é **todo o workspace Design** (sólido, superfície, sheet metal, sculpt, assemblies), entregue em ondas. O código v3 é **auditado e aproveitado** (nada confiado sem auditoria + teste + validação real). Cada fase termina em **gate de validação do dono no Fusion real** (o container é mock).

## Contexto técnico

- **Linguagem/Versão**: Python 3.11 (backend); TypeScript 5.x / React + Vite (web).
- **Dependências principais**: FastAPI, MCP (servidor/cliente), Fusion 360 add-in/bridge; gateway LLM (vision para anexos).
- **Storage**: Postgres (produção) + fallback JSON (dev/test) — ver P5. Histórico de chat + modelagem persistido e reconstituível.
- **Testes**: pytest (backend), vitest (web). CI cobre o verificável em container; o real é validado pelo dono.
- **Plataforma-alvo**: desktop Windows local-first (Fusion roda na máquina do dono); web/Tauri como cliente.
- **Tipo de projeto**: backend FastAPI + frontend web + servidor MCP + add-in Fusion.
- **Restrições**: container remoto é **mock** (sem Fusion/Windows); local-first (sem exposição pública ingênua); custo/iteração do loop limitado (teto 5).

## Constitution Check

*GATE: passar antes da fase de tasks; rechecar após o design de cada fase.*

- [x] **P1 Local-first** — o servidor MCP standalone DEVE ser local-first (loopback/VPN/pareamento + auth). Exposição pública ingênua é proibida. → **ADR-017** registra a arquitetura/exposição.
- [x] **P2 Stack invariável** — sem troca de stack. Adição do servidor MCP standalone é componente novo dentro da stack atual; formalizada por **ADR-017**.
- [x] **P3 Preservar arquitetura antes de reescrever** — estratégia "auditar e aproveitar": reescreve só o frágil/nunca-validado. Fase 0 inventaria antes de tocar.
- [x] **P4 Spec/Doc rastreável** — esta spec + macro + micro-planos + ADRs; cross-links válidos.
- [x] **P5 Postgres-prod / JSON dev-only** — persistência de chat+modelagem em Postgres; JSON só dev.
- [x] **P6 Aprovação humana p/ alteração-deleção** — aprovação única do plano cobre high-risk; sem script livre no caminho feliz; snapshot/rollback/auditoria mantidos.
- [ ] **P7 RAG com escopo** — não aplicável diretamente a esta frente (sem mudança de RAG).
- [x] **P8 3D human-in-the-loop** — reabrir "single-body" para assemblies muda o data model do plano → **ADR-018** antes de codar. Allowlist de fonte única preservada.
- [x] **P9 Qualidade + PT-BR** — gates de qualidade por fase; artefatos PT-BR. Reforçado pelas Regras transversais (clean architecture, documentação dupla, unit tests).

> Violações a justificar (novos componentes/decisões) → "Rastreamento de complexidade".

## Regras transversais de implementação (Definição de Pronto global)

**Estas quatro regras valem para a DoD de TODA fase** (0→F). Nenhuma fase é dada como concluída sem cumpri-las. Encodadas aqui (fonte única) em vez de repetidas em cada micro-plano — coerente com a própria regra de clean code.

1. **Qualidade / Clean Architecture (não-negociável)** — código limpo, camadas separadas (domínio / casos de uso / adapters / interface), sem regra de negócio em rotas, sem acoplamento que impeça teste. Gates `scripts/quality.ps1` verdes. (RNF-006; corrige DT-006.)
2. **Documentação dupla** — toda capacidade documentada no **Docusaurus** (`apps/docs`, que serve `docs/`) **e** no **SDD** (`specs/005-...`), coerentes entre si e com o código. (RNF-007.)
3. **Testes unitários** — toda capacidade com unit tests cobrindo o comportamento, verdes nos gates. (RNF-008.)
4. **Nova UI (`homolog-new-ui`)** — toda UI 3D conforme a nova UI em homologação. (RNF-009; **desbloqueado** — re-skin v4 mergeado na `master` via PR #42 / `tasks.md` T0.11; a passada de refactor de UI vive nas fases 2+ — ver "Pendências de ambiente".)

## Estrutura

### Documentação (esta feature)

```text
specs/005-modeling-3d-fusion/
├── spec.md                     # produto (o quê) — reescrito v4
├── plan.md                     # este arquivo — macro (como, em fases)
├── tasks.md                    # índice vivo: status por fase + gates
├── handoff.md                  # continuidade entre agentes
├── micro/
│   ├── fase-0-specs-auditoria.md
│   └── fase-N-*.md             # escritos just-in-time por fase
├── adapter-gaps-roadmap.md     # insumo das fases de cobertura
├── adapter-tools-mvp.md        # insumo (histórico do MVP de tools)
├── chat-flow-redesign.md       # insumo do núcleo agêntico (fluxo)
├── observability-plan.md       # insumo da observabilidade
└── g4-assemblies-decision.md   # A REABRIR (escopo mudou) → ADR-018
```

### Código afetado (caminhos reais)

```text
backend/app/modeling/           # bounded context 3D (auditar e aproveitar)
backend/app/modeling/mcp_servers/   # evoluir p/ servidor MCP standalone (ADR-017)
backend/app/api/routes/modeling.py, chat_modeling.py
apps/web/src/features/modeling-3d/  # UI do chat 3D, cards, diagnóstico
apps/fusion-addin/              # executor no Fusion (bridge)
docs/3d-mcp-modeling.md, docs/decisions.md (ADR-017/018), docs/infra-observability.md
```

**Decisão de estrutura**: preservar o bounded context atual em `backend/app/modeling/` e evoluí-lo; o servidor MCP standalone nasce da camada `mcp_servers/` existente. A UI permanece em `features/modeling-3d/`.

## Estratégia / Fases

Cada fase = um ou mais PRs com testes CI verdes + docs atualizadas, encerrada por **gate de validação do dono no Fusion real**. A próxima fase não começa antes do gate (decisão do dono). O **micro-plano** de cada fase é escrito antes de iniciá-la.

- **Fase 0 — Specs + Auditoria** _(sem código de produto novo)_
  Reescrever a tríade do 005 (feito neste passo). Auditar peça-a-peça o v3 (`tool_registry`, `planner`, `executor`, `chat_orchestrator`/`chat_state`, `fusion_adapter`/`fusion_mcp_scripts`, `mcp_servers`, `attachment_analyzer`, `observability`, `snapshot_service`, `printability`) com veredito *confiar / reescrever* e status real-Fusion das ~50 tools. **Auditar e absorver os assets do fidelity-roadmap v3** (`agent_loop.py`, `tool_schemas.py`, `planner.build_correction_context`) como base das Fases 2/4. Rascunhar **ADR-017** (MCP standalone), **ADR-018** (reabrir assemblies / cobertura "todo o Design") e **ADR-019** (fronteira de segurança do script backend-owned via `featureType:"script"` — DT-009). Catalogar as **inconsistências de documentação** v2/v3→v4 (saída da varredura) para reconciliação na Fase final. Entregável: `micro/fase-0-*.md` + inventário de auditoria. _Gate:_ dono revê inventário + ADRs.

- **Fase 1 — Servidor MCP standalone** _(ADR-017)_
  Evoluir `mcp_servers/` para servidor MCP-compliant com transport HTTP/SSE + auth, local-first; expor as tools Fusion já confiadas; backend vira **cliente**. _Gate:_ conectar um cliente externo (ex.: Claude) + smoke das tools no Fusion real.

- **Fase 2 — Núcleo agêntico** _(constrói sobre o `agent_loop.py` absorvido)_
  Partir do andaime `ModelingAgentLoop` (já entregue, teto duro 5) e: **ligá-lo ao stream após a aprovação** (item pendente do fidelity); **estender `_needs_correction`** para disparar também em **divergência geométrica** (read-back esperado × medido), não só em erro de tool; aplicar a decisão do dono de que a **aprovação do plano cobre o delta corretivo high-risk** (loop não pausa — DT-010); adotar `tool_schemas.py` (a LLM vê args/unidades/exemplos). Mais: **execução autônoma fim-a-fim** (sem parada mid-run), persistência forte chat+histórico, observabilidade (trace por passo + logs legíveis pelo dono) e doc de scripts de debug. Inclui as correções estruturais achadas na varredura: **consolidar rota×orchestrator** (DT-006), **snapshot/rollback nativo do Fusion** em vez de cópia de filesystem (DT-005), **persistência explícita** (sem fallback JSON silencioso, DT-007) e **estado de falha/rollback** distinto no `chat_state` (DT-008). _Gate:_ fluxo completo de peça única (Nível 1) no Fusion real.

- **Fase 3 — Edição manual (read-back/reconciliação sob demanda)**
  Antes de planejar edição, ler timeline+geometria atuais e reconciliar. _Gate:_ dono altera à mão e o motor continua corretamente.

- **Fase 4 — Parametrização real + selectors + features de sólido** ✅ validado (DT-002 fechado no Fusion real; G1/G2/G3 + stable_id de body).
- **Fase 5 — Superfícies (NURBS)** — validado autônomo (probe direto no adapter) no Fusion real (revolve/patch/stitch/thicken/offset/extend/unstitch; `trim` known-issue); **aprovação visual do dono na UI pendente**. 7 surface tools implementadas no registry.

> **REPLAN (2026-05-29) — de "cobertura de workspaces" para "capacidades".** Os gates mostraram que (a) o núcleo de criação de sólidos + superfícies está robusto, e (b) **sheet metal e sculpt são bloqueados pela API do Fusion** (UI-only; ver DT-011/DT-012). O dono reorientou o objetivo: **gerar sólidos mecânicos complexos por chat** (peças com mecanismos), medido por 4 capacidades, não por cobertura de workspaces. As fases de cobertura 6/7/8 são substituídas por **frentes de capacidade F1–F6**. Detalhe vivo nos micro-planos.

- **Fase 6 — Sheet metal** ⛔ **CONGELADA** — bloqueada pela API Python do Fusion (DT-011; só `flangeFeatures` read-only). Tools removidas. Reabrir só se a Autodesk expor a API.
- **Fase 7 — Sculpt / T-Spline** ⛔ **CONGELADA** — Form/Sculpt exige direct-mode (sem timeline) e a API não expõe criação de T-Spline parametricamente (DT-012). Fora do foco do dono (peças são sólidos). Alternativa de forma orgânica = superfícies NURBS (Fase 5, já temos).

### Frentes de capacidade (substituem a cobertura 6/7/8)

Cada frente = micro-plano just-in-time + gate no Fusion real. Capacidades-alvo: **P1** peças mecânicas funcionais (dobradiça/knuckle, parafuso, suporte articulado), **P2** planejamento minucioso + estado rico entre etapas, **P3** image-to-model, **P4** edição robusta com contexto.

- **F1 — Estado rico do modelo** _(fundação; começa aqui)_: `entityToken` de face/edge no `query_geometry` + topologia (adjacências, raio/eixo), selectors por token estável, e um `ModelState` estruturado capturado pós-execução e injetado no contexto do planner entre etapas. Destrava P1/P2/P4. _Gate:_ body→fillet→re-query: token de face não-tocada sobrevive; fillet por `face_tokens` acerta a face.
- **F2 — Planejamento agêntico/hierárquico** _(com F1)_: decompor o pedido em sub-objetivos e rodar loop planejar→executar→observar(ModelState)→replanejar, em vez de one-shot flat. Reusa o `ModelingAgentLoop`. Atrás de flag `modeling_hierarchical_planning_enabled`. _Gate:_ parafuso que ENCAIXA (furo da fêmea planejado com diâmetro real medido do macho).
- **F3 — Mecanismos funcionais** _(P1)_: o planner **compõe** mecanismos a partir de **primitivas + features genéricas** — `thread` (`ThreadFeatures` Modeled), `joint` (revolute/rigid/slider), `make_component` (componentes/ocorrências), `pattern_*`, `combine_bodies` — em vez de macros de produto. **Decisão (ADR-020):** as macros `knuckle_hinge`/`metric_screw` foram **deprecadas do planner** (`DEPRECATED_PLANNER_TOOLS`; handlers mantidos só para backward-compat/smoke); `snap_fit` **nunca foi implementado**. O motor genérico ganha um **loop de verificação visual** (render → crítica de visão → replan corretivo: `visual_critique.py` + `fusion.capture_viewport`, atrás de `modeling_visual_verification_enabled`, teto `modeling_visual_max_rounds`) e o **sanitizer determinístico** (F6) como apoios da composição. _Gates:_ caixa+tampa knuckle que abre, parafuso, suporte de monitor.
- **F4 — Image-to-model** _(P3)_: estender o gateway LLM para multimodal, implementar `attachment_analyzer._call_vision` real, pipeline imagem→entendimento→plano (reusa F2). _Gate:_ foto → peça fiel.
- **F5 — Edição robusta com contexto** _(P4)_: evolui a Fase 3 sobre o `ModelState` (F1) + reconciliação estruturada. _Gate:_ editar peça pronta via contexto.
- **F6 — Determinismo do LLM** _(ex-Fase 9; suporte transversal)_: Structured Outputs + sanitizer determinístico + retry agêntico com guidance + verifier opcional + templates. Permeia F2/F3. Pode entrar cedo. _Gate:_ cenários reproduzíveis sem ajuste manual de prompt. (ADR-020.)

- **Fase final — QA, docs e handoff** consolidados: regressão das capacidades validadas, reconciliação documental v2/v3→v4 (remover `safe_auto`/endpoints mortos, superar ADR-012/013 com 017/018), landing 3D no Docusaurus (RNF-007).

> **Ordem aprovada pelo dono (2026-05-29):** **F1+F2 primeiro** (fundação), validada com 1 mecanismo real; os 3 exemplos (caixa+tampa knuckle, parafuso, suporte) viram **gates oficiais**. Depois F3 (mecanismos) → F4 (vision) / F5 (edição) → F6 permeando. **Sem rede neural** (LLM multimodal + orquestração + macros + verificação geométrica).

## Sequenciamento

- 0 → 1 → 2 → 3 sequenciais (feitas; Fase 1 gate adiado). 4, 5 ✅ validadas.
- 6, 7 ⛔ congeladas (API). 8 (assemblies) absorvida pela F3 (mecanismos/joints/componentes sob demanda dos gates).
- **F1 → F2** (fundação) primeiro; F3/F4/F5 dependem de F1+F2; F6 permeia.
- ADRs: ADR-017 (Fase 1, feito), ADR-019 (script boundary, feito); **ADR-021** (estado rico + planejamento hierárquico + replan "capacidades", F1/F2) e **ADR-020** (motor genérico: composição + sanitizer determinístico + verificação visual/geométrica, F3/F6) já **criados e aceitos** em `docs/decisions.md`. ADR-018 (assemblies) permanece **rascunho** (escopo absorvido pela F3).

## Validação

Comandos reais (ver `scripts/quality.ps1` e `docs/delivery-checklist.md`):

- Backend: `ruff format --check`, `ruff check`, `pytest`
- Web: `format:check`, `lint`, `test:unit`, `typecheck`, `build`
- Docs (se `docs/` mudar): `pnpm --filter @truths-forge/docs build`
- Cross-links: todos os caminhos citados em spec/plan/tasks/micro existem.
- **Regras transversais (DoD global)** por fase: clean architecture (sem regra de negócio em rota; camadas testáveis) · documentação dupla (Docusaurus `apps/docs` + SDD) · unit tests cobrindo a capacidade · UI conforme `homolog-new-ui`.
- **Gate por fase**: validação do dono no Fusion real (checklist no micro-plano de cada fase) — pré-requisito para a fase seguinte.

## Riscos e trade-offs

- **Container mock** não roda Fusion → confiabilidade real só no gate do dono. Mitigação: testes de contrato/compile no CI + smoke roteirizado por tool no Fusion real.
- **Reabrir single-body (assemblies)** muda data model do plano, refs, UI e printability → risco de retrabalho. Mitigação: ADR-018 + Fase 8 isolada, depois do núcleo estável.
- **Servidor MCP exposto** → risco de segurança. Mitigação: local-first + auth (RNF-001/ADR-017); sem exposição pública ingênua.
- **Tools nunca validadas (C-F)** → falham no Fusion real. Mitigação: auditoria na Fase 0 + smoke na Fase 1/2.
- **Loop agêntico custo/loop infinito** → teto 5 + término explícito + rollback (RF-010/011).
- **"Auditar e aproveitar" herdar dívida** → veredito explícito por peça na Fase 0; reescreve o frágil.

## Rastreamento de complexidade

| Violação | Por que é necessária | Alternativa simples rejeitada porque |
|----------|----------------------|--------------------------------------|
| Novo servidor MCP standalone (ADR-017) | Requisito do dono: reuso por outros clientes (ex.: Claude) sem reengenharia futura | Manter stdio interno não atende reuso externo nem desacoplamento |
| Reabrir "single-body" → assemblies (ADR-018) | Cobertura-alvo "todo o Design" inclui montagens/juntas/materiais | Manter single-body não cobre o escopo aprovado pelo dono |
| Gate de validação manual por fase | Container é mock; só o dono valida no Fusion real | CI puro não prova comportamento real no Fusion |

## Pendências de ambiente

- **Nova UI (`homolog-new-ui`)** — RNF-009 exige que a UI 3D siga a nova UI em homologação. **Estado (atualizado)**: **desbloqueado** — o re-skin v4 já foi **mergeado na `master` via PR #42** (`tasks.md` T0.11), de modo que a base já inclui a nova UI. A passada de refactor de `apps/web/src/features/modeling-3d/` (componentes, padrões visuais, navegação) foi movida para as fases que tocam UI (2+). _(Nota: um container efêmero sem remote pode não enxergar o merge; nesse caso, usar sessão nova / clone fresco.)_
- **Sem Fusion no container** — execução real só no ambiente do dono (gate por fase). O CI cobre contrato/compile/unit; o real é validado pelo dono.
- **Convergência de branches (fidelity)** — ✅ **resolvida.** `agent_loop.py`, `tool_schemas.py` e as mudanças no `planner` (`build_correction_context`) já estão **commitados e integrados** nesta branch (`feat/3d-modelling-updates`, commit `06b2d2e`); o loop foi validado end-to-end no Fusion real (Gate 4, commit `9b4fd4b`). Não há mais worktree divergente nem fonte de verdade dupla para esses assets.
