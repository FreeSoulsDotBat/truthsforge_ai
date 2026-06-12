# Tasks (índice vivo): Modelagem 3D chat-first autônoma (v4)

**Spec**: [`spec.md`](./spec.md) | **Macro**: [`plan.md`](./plan.md) | **Micro**: [`micro/`](./micro/) | **Homologação**: [`gate-homologacao.md`](./gate-homologacao.md)

> Este arquivo é o **índice de progresso** do v4. O detalhe de cada fase vive no micro-plano correspondente, escrito just-in-time. Cada fase só é dada como concluída após o **gate de validação do dono no Fusion real**. Marque o status conforme avança.
>
> 🧪 **Roteiro de homologação dos gates pendentes** (prompts prontos + pré-voo + reporte): [`gate-homologacao.md`](./gate-homologacao.md).

## Legenda de status

`[ ]` não iniciada · `[~]` em andamento · `[x]` concluída (gate passado) · `[!]` bloqueada/aguardando dono

## Definição de Pronto global (vale para TODA fase)

Além do gate do dono, nenhuma fase fecha sem cumprir as **Regras transversais** (detalhe em [`plan.md`](./plan.md)):

1. **Clean Architecture / qualidade** não-negociável (camadas testáveis, sem regra de negócio em rota).
2. **Documentação dupla**: Docusaurus (`apps/docs`) + SDD (`specs/005-...`).
3. **Unit tests** cobrindo a capacidade entregue.
4. **UI conforme `homolog-new-ui`** — _pendente do merge na `master`_ (ver `plan.md` › Pendências de ambiente).

## Mapa de fases e gates

| Fase | Tema | Micro-plano | Status | Gate (dono valida no Fusion real) |
|---|---|---|---|---|
| 0 | Specs + Auditoria | [`micro/fase-0-specs-auditoria.md`](./micro/fase-0-specs-auditoria.md) · [`micro/fase-0-auditoria.md`](./micro/fase-0-auditoria.md) | `[x]` | ✅ Dono aprovou inventário + ADR-017/018/019 (2026-05-24) |
| 1 | Servidor MCP standalone (ADR-017) | [`micro/fase-1-mcp-standalone.md`](./micro/fase-1-mcp-standalone.md) | `[~]` | Código + CI ✅; **aguardando gate do dono**: cliente externo conecta + smoke de tools no Fusion real |
| 2 | Núcleo agêntico (loop + verificação + persistência + observabilidade) | [`micro/fase-2-nucleo-agentico.md`](./micro/fase-2-nucleo-agentico.md) | `[~]` | Estrutural ✅; **loop agêntico VALIDADO end-to-end no Fusion real (2026-05-29)**: cubo+fillet 16mm impossível → corretor LLM reduziu p/ 8mm+vertical → completed (Gate 4). Falta: snapshot nativo (DT-005, `rollback_skipped`) + read-back geométrico fiado no loop em peça real |
| 3 | Edição manual (read-back/reconciliação) | [`micro/fase-3-edicao-manual.md`](./micro/fase-3-edicao-manual.md) | `[x]` | ✅ **Gate do dono APROVADO (2026-05-26)**: edição à mão + reconciliação + "Desfazer última edição" reverteu no Fusion real. Código T3.1–T3.6 + testes verdes. Achados do gate corrigidos (envelope HTTP, `kind` no metadata do chat, `query_timeline` fora do planner, rollback em edição falha, `deleteMe` robusto). |
| 4 | Parametrização real + selectors + features de sólido | [`micro/fase-4-param-selectors-solido.md`](./micro/fase-4-param-selectors-solido.md) | `[x]` | ✅ **DT-002 validado no Fusion real (2026-05-29)**: placa paramétrica recomputou 120→160; stable_id de body. Resíduo: posição de furo paramétrica (G1.2 estendido) |
| 5 | Superfícies (NURBS) | [`micro/fase-5-superficies.md`](./micro/fase-5-superficies.md) | `[~]` | **Validado autônomo no Fusion real (2026-05-29)**: revolve_surface/patch/stitch→sólido/thicken/offset/extend/unstitch/query+stable_id ✅ (3 bugs corrigidos no caminho); `trim` known-issue (cells). Falta aprovação visual do dono na UI |
| 6 | Sheet metal | [`micro/fase-6-sheet-metal.md`](./micro/fase-6-sheet-metal.md) | `[!]` | ⛔ **CONGELADA — bloqueada por API** (DT-011): Fusion Python só expõe `flangeFeatures` read-only. Tools removidas. Reabrir só se a Autodesk expor a API |
| 7 | Sculpt / T-Spline | [`micro/fase-7-sculpt.md`](./micro/fase-7-sculpt.md) | `[!]` | ⛔ **CONGELADA — bloqueada por API** (DT-012): Form/Sculpt exige direct-mode (sem timeline) e a API não cria T-Spline parametricamente. Fora do foco (sólidos). Forma orgânica = NURBS (Fase 5) |

## Frentes de capacidade (REPLAN 2026-05-29 — substituem cobertura 6/7/8)

> Reorientação de "cobertura de workspaces" para **capacidades de sólidos mecânicos** (ver [`plan.md`](./plan.md) › Frentes de capacidade). Objetivo: P1 peças mecânicas funcionais, P2 planejamento minucioso + estado rico entre etapas, P3 image-to-model, P4 edição robusta. Gates oficiais = caixa+tampa knuckle, parafuso, suporte de monitor.

> ⏸️ **PAUSA ESTRATÉGICA (2026-06-02).** O motor genérico (composição + loop
> visual) foi **validado no Fusion real** (render→crítica→replan funcionam). Mas
> o **posicionamento relativo de bodies** é arquitetural e **não fecha com fixes
> incrementais** — vai numa **refatoração grande dedicada** (a planejar pelo
> dono). Todo o resíduo está congelado como débito em
> [`tech-debt-posicionamento.md`](./tech-debt-posicionamento.md). Os fixes
> incrementais das frentes F3–F6/MG ficam **pausados** até essa refatoração.

| Frente | Tema | Micro-plano | Status | Gate (dono valida no Fusion real) |
|---|---|---|---|---|
| F1 | Estado rico do modelo (entityToken face/edge + ModelState entre etapas) | [`micro/fase-F1-estado-rico.md`](./micro/fase-F1-estado-rico.md) | `[x]` | ✅ **Gate Fusion real APROVADO (2026-05-29)**: fillet por edge_token (query→uso), token de corpo intocado sobrevive, stale→erro claro. 426 testes. Aprendizado: re-query após features que recriam geometria |
| F2 | Planejamento agêntico/hierárquico (decompõe→executa→observa→replaneja) | [`micro/fase-F2-planejamento-agentico.md`](./micro/fase-F2-planejamento-agentico.md) | `[x]` | ✅ **Gate Fusion+LLM APROVADO (2026-05-29)**: decompôs em 4 sub-objetivos; furo Ø10 e pino Ø10 com MESMO raio (encaixe via ModelState entre blocos). 429 testes |
| F3 | Mecanismos funcionais (thread/joint/make_component + composição genérica) | [`micro/fase-F3-mecanismos.md`](./micro/fase-F3-mecanismos.md) | `[~]` | **Código + testes mock ✅** (thread modelada, make_component, joint; o planner **compõe** mecanismos de primitivas + features genéricas — **ADR-020**). **Pivot:** as macros `knuckle_hinge`/`metric_screw` foram **deprecadas do planner** (`DEPRECATED_PLANNER_TOOLS`; handlers só p/ backward-compat/smoke); `snap_fit` nunca existiu. **Aguardando os 3 gates oficiais do dono no Fusion real**: dobradiça abre · parafuso encaixa · suporte paramétrico |
| F4 | Image-to-model (gateway multimodal + vision real) | [`micro/fase-F4-image-to-model.md`](./micro/fase-F4-image-to-model.md) | `[~]` | **Código + testes mock ✅** (gateway multimodal backward-compat; `_call_vision` real; builders por provedor; 14 testes F4 + 99 consumidores verdes). **Aguardando gate do dono**: foto → peça fiel no Fusion+LLM real |
| F5 | Edição robusta com contexto (evolui Fase 3 sobre ModelState) | [`micro/fase-F5-edicao-robusta.md`](./micro/fase-F5-edicao-robusta.md) | `[~]` | **Código + testes mock ✅** (reconciliação por geometria AO VIVO: `_read_live_geometry` + `_build_live_state_block` injetam ModelState atual na edição, flag default OFF; 8 testes F5 + 71 consumidores verdes). **Aguardando gate do dono**: editar peça após mudança manual no Fusion real |
| F6 | Determinismo do LLM (ex-Fase 9; Structured Outputs + sanitizer + retry) | [`micro/fase-9-llm-determinism.md`](./micro/fase-9-llm-determinism.md) | `[~]` | **9.2 (sanitizer determinístico) entregue + testado** (`plan_sanitizer.py`: strip de campos-fantasma/refs geométricas, remap de alias, flag default ON, telemetria por aviso; 11 testes + 94 consumidores verdes). 9.1 (Structured Outputs) já no planner; 9.3 (retry) no agent_loop. **Aguardando gate do dono**: cenários A/B/C reproduzíveis sem ajuste manual de prompt (ADR-020) |
| MG | Motor genérico — loop de verificação visual (render → crítica de visão → replan corretivo) | [`gate-homologacao.md`](./gate-homologacao.md) (Gate Visual) | `[~]` | **Código + gate-doc prontos e loop validado no Fusion real** (`visual_critique.py` + `fusion.capture_viewport`; render→crítica→replan funcionam; flag `modeling_visual_verification_enabled` default OFF; teto `modeling_visual_max_rounds`=2; **ADR-020**). Suporta a composição genérica (sem macros de produto) a se auto-corrigir. ⏸️ **PAUSADO**: o resíduo é o **posicionamento relativo de bodies** (arquitetural → refatoração grande; ver pausa estratégica acima + `tech-debt-posicionamento.md`) |
| F7 | Posicionamento paramétrico (referência espacial declarativa + montagem nativa) | [`micro/fase-F7-posicionamento.md`](./micro/fase-F7-posicionamento.md) | `[~]` | **Refatoração da pausa estratégica — aprovada (2026-06-03, ADR-022).** Resolve o posicionamento relativo de bodies: LLM declara placement por referência à geometria real (`@token(...).center`, ancorar/distribuir/alinhar); resolver determinístico no backend emite **componentes + joints paramétricos** (combine-dentro, joint-entre — reconcilia o gate da dobradiça). **Código P0/P2/P3/P4/P5 entregue + mock-verde** atrás da flag `modeling_spatial_resolution_enabled` (default OFF): `spatial_ref.py` (resolver puro), `spatial_resolver.py` (inline + expansão `place_body`/`align_axis`/`distribute_along`), enriquecimento do `query_geometry` (bbox abs + pontas de aresta), wiring no executor (probe→resolve→dispatch), nudge flag-aware, sanitizer poupa `@`-refs. Commits `8657971`/`e643dcb`/`575d330`/`5ac207c`/`f1cab09`; suíte local 529 verdes. **Aguardando só os gates Fusion do dono** (P1 fundação de montagem API-blind, P2 números do probe, P6 placement + dobradiça que abre) — recipe em [`gate-homologacao.md`](./gate-homologacao.md) › Gate F7 |
| F8 | Identidade por role/predicado + proveniência + auto-crítica + relação genérica | [`gate-homologacao.md`](./gate-homologacao.md) (Gate F8) | `[~]` | **Refatoração aprovada (2026-06-08, ADR-023).** A matemática de identidade/posição sai do LLM e vira código que MEDE o B-Rep: `entity_ref` (role/predicado→handle), `provenance` (ChangeRecord por passo), `model_critique` (ModelVerdict faltou/demais/errado/certo — REPORTA, não corrige; permite desligar o juiz-de-visão), `relation_derive`/`geometry_verifier` (relação genérica = composição de primitivas). **Código mock-verde** atrás de flags próprias (`modeling_provenance_enabled`/`self_critique`/`relation_placement`, default OFF). **Gates Fusion (2026-06-09):** F8.D1 (proveniência+crítica) ✅ de-facto validado (visível em todo plano); F8.R1 (relação `relate_bodies` flush_mate) ✅ **APROVADO** via plano literal (`scripts/gate_f8r1.ps1` — derivou medindo, tampa encostou flush z=20). **Falta só** o F8.Spike (identidade sob edição paramétrica) — recipe em [`gate-homologacao.md`](./gate-homologacao.md) › Gate F8 |
| F9 | Posicionamento relativo declarativo + estado semântico passo-a-passo + enforcement | [`gate-homologacao.md`](./gate-homologacao.md) (Gate F9) | `[x]` | **✅ GATE FUSION REAL APROVADO (2026-06-09, ADR-024).** Amplia o vocabulário de relação (deixa de ser só "centro"), passa SEMÂNTICA entre steps e RECUSA a coordenada chutada: `align` no place_body (center/coplanar/gap/edge/corner), `semantic_state` (roles/touches/body_label, injetados no `<model-state>`), `enforce_relative_coord` (Gate B). **Validado no Fusion real:** P1 align (tampa centrada + 2mm acima, `m3d_plan_330842271a884d5d`), P3 enforcement, edição idempotente (delta-zero=no-op), P2 roles + `container`/`is_open_boundary` (detector de abertura por loop-com-furo em sólido ocado). Atrás de 3 flags (default OFF; zero regressão). **Achados do gate corrigidos:** schema expõe align/gap_mm; gap segue normal do destino + recentraliza; place_body idempotente; discovery pergunta sobre montagem; is_open_boundary detecta shell. Recipe em [`gate-homologacao.md`](./gate-homologacao.md) › Gate F9. Confirmação opcional: lid/touches num build flush |
| F | QA, docs e handoff finais | [`micro/fase-final-qa-docs.md`](./micro/fase-final-qa-docs.md) | `[ ]` | Checklist de entrega completo |

## Fase 0 — itens (detalhe em `micro/fase-0-specs-auditoria.md`)

- [x] T0.1 — Reescrever `spec.md` (produto, só-3D, v4)
- [x] T0.2 — Reescrever `plan.md` (macro: arquitetura-alvo + roadmap de fases + Constitution Check)
- [x] T0.3 — Reescrever `tasks.md` (este índice vivo)
- [x] T0.4 — Escrever `micro/fase-0-specs-auditoria.md`
- [x] T0.5 — Auditoria peça-a-peça do `backend/app/modeling/` (veredito confiar/reescrever) → [`micro/fase-0-auditoria.md`](./micro/fase-0-auditoria.md) §1
- [x] T0.6 — Inventário do status real-Fusion das ~50 tools do adapter → `fase-0-auditoria.md` §4 (+ candidatas de smoke da Fase 1)
- [x] T0.6b — Assets do fidelity (`agent_loop.py`/`tool_schemas.py`/`build_correction_context`) confirmados **ausentes** nesta branch; convergência de branches registrada → §5
- [x] T0.7 — Rascunho do ADR-017 (servidor MCP standalone, local-first + auth) em `docs/decisions.md`
- [x] T0.8 — Rascunho do ADR-018 (reabrir assemblies / cobertura "todo o Design"); `g4-assemblies-decision.md` marcado como superado
- [x] T0.9 — Rascunho do ADR-019 (fronteira de segurança do script backend-owned — DT-009)
- [x] T0.10 — Catalogar inconsistências de doc v2/v3→v4 para a Fase final → §6 (D1–D6; inclui caminho pessoal vazado em `docs/local-dev.md:5`)
- [x] T0.11 — Reavaliado: **desbloqueado** (re-skin v4 mergeado na `master` via PR #42; base inclui a UI nova). Passada de refactor de `features/modeling-3d/` movida para as fases que tocam UI (2+) → §7
- [x] T0.12 — **Gate Fase 0**: dono **aprovou** inventário + ADRs (2026-05-24) → Fase 1 liberada

## Disposição dos documentos auxiliares (herdados do v3)

| Documento | Disposição no v4 |
|---|---|
| `adapter-gaps-roadmap.md` | Insumo das fases de cobertura (4–8) |
| `adapter-tools-mvp.md` | Insumo/histórico do conjunto de tools |
| `chat-flow-redesign.md` | Insumo do núcleo agêntico (Fase 2) |
| `observability-plan.md` | Insumo da observabilidade (Fase 2) |
| `g4-assemblies-decision.md` | **Reaberto** — escopo mudou; vira ADR-018 (Fase 0 → Fase 8) |
| `fidelity-roadmap.md` (em `master`) | **Absorvido pelo v4** — insumo das Fases 2/4/8; código (`agent_loop.py`, `tool_schemas.py`, `build_correction_context`) entra na auditoria da Fase 0 e vira andaime da Fase 2 |
| `handoff.md` | Continuidade entre agentes (mantido) |

## Notas de continuidade

- Decisões do dono (2026-05-23): cobertura = todo o Design; código v3 = auditar e aproveitar; MCP = standalone reutilizável desde já; edição manual = leitura sob demanda; verificação = asserções geométricas; validação = gate por fase; **execução autônoma fim-a-fim sem interrupção mid-run**; Blender = congelar e manter.
- Regras transversais adicionadas (2026-05-23): clean architecture; documentação dupla (Docusaurus + SDD); unit tests; UI conforme `homolog-new-ui`. Ver "Definição de Pronto global".
- Varredura de consistência (2026-05-23) feita; achados viraram DT-005..009 e tarefas nas Fases 0/2/final. Docusaurus serve `docs/` cru (`apps/docs` → `path: ../../docs`).
- Plano de UI: o dono vai mergear `homolog-new-ui` na `master`; depois, passada de refactor de UI (T0.11) para alinhar `apps/web/src/features/modeling-3d/` (RNF-009). **Nota**: o merge feito pelo dono não chega a este container efêmero (sem remote); requer sessão nova / clone fresco.
- Reconciliação de planos (2026-05-23): **v4 absorve o fidelity-roadmap v3**; em conflito de escopo vence o v4 (cobertura ampla). High-risk corretivo durante o loop: **coberto pela aprovação do plano** (loop não pausa) → ajustar `agent_loop.py` (DT-010).
- Convergência de branches: ✅ **resolvida** — os assets do fidelity (`agent_loop.py`/`tool_schemas.py`/`build_correction_context`) já estão **commitados e integrados** nesta branch (`06b2d2e`); loop validado no Fusion real (Gate 4, `9b4fd4b`). Não há mais worktree divergente.
- **Follow-ups da deliberação do conselho sobre o PR #50 (2026-06-12):**
  - **Cobertura da suíte ≠ homologação 3D.** Os 745 testes backend cobrem FORMA/CONTRATO dos scripts e a lógica Python-side (geração, schemas, resolução de refs), **não** o encaixe físico que só roda DENTRO do Fusion. As heurísticas Fusion-side (ex.: o limiar `0.5` de `_face_is_open_boundary`) não são executadas em CI — exigem `adsk`. Não ler "mock-verde" como "validado no Fusion".
  - **Pré-condição de LIGAR cada flag F7/F8/F9 em produção:** o gate Fusion correspondente (linhas acima / [`gate-homologacao.md`](./gate-homologacao.md)). Manter a flag default OFF até o gate do dono daquela capacidade.
  - **Higiene de pré-flip ENTREGUE neste follow-up:** `geometry_core` unifica `bbox_overlap_volume` (eliminada a 2ª cópia divergente em `model_critique` — corte estrito vs `eps=1e-3` agora é parâmetro explícito, fim do drift de 1 µm sobre "interferência/contato"); `_safe_error_detail` allowlista os `ValueError` tipados de edição (`InvalidEditStage`/`NotAModelingChat`), sem readmitir `ValueError` cru (que ecoaria saída do LLM).
- Branch: `feat/3d-modelling-updates`.
