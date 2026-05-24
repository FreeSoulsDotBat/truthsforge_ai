# Tasks (índice vivo): Modelagem 3D chat-first autônoma (v4)

**Spec**: [`spec.md`](./spec.md) | **Macro**: [`plan.md`](./plan.md) | **Micro**: [`micro/`](./micro/)

> Este arquivo é o **índice de progresso** do v4. O detalhe de cada fase vive no micro-plano correspondente, escrito just-in-time. Cada fase só é dada como concluída após o **gate de validação do dono no Fusion real**. Marque o status conforme avança.

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
| 1 | Servidor MCP standalone (ADR-017) | [`micro/fase-1-mcp-standalone.md`](./micro/fase-1-mcp-standalone.md) | `[ ]` | Cliente externo conecta + smoke de tools no Fusion real |
| 2 | Núcleo agêntico (loop + verificação + persistência + observabilidade) | [`micro/fase-2-nucleo-agentico.md`](./micro/fase-2-nucleo-agentico.md) | `[ ]` | Fluxo completo Nível 1 no Fusion real |
| 3 | Edição manual (read-back/reconciliação) | [`micro/fase-3-edicao-manual.md`](./micro/fase-3-edicao-manual.md) | `[ ]` | Alteração manual + continuação correta |
| 4 | Parametrização real + selectors + features de sólido | [`micro/fase-4-param-selectors-solido.md`](./micro/fase-4-param-selectors-solido.md) | `[ ]` | Nível 1 aprofundado |
| 5 | Superfícies (NURBS) | [`micro/fase-5-superficies.md`](./micro/fase-5-superficies.md) | `[ ]` | Nível 2 |
| 6 | Sheet metal | [`micro/fase-6-sheet-metal.md`](./micro/fase-6-sheet-metal.md) | `[ ]` | Nível 3 |
| 7 | Sculpt / T-Spline | [`micro/fase-7-sculpt.md`](./micro/fase-7-sculpt.md) | `[ ]` | Nível 4 |
| 8 | Assemblies / componentes / juntas / materiais (ADR-018) | [`micro/fase-8-assemblies.md`](./micro/fase-8-assemblies.md) | `[ ]` | Nível 5 |
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
- Convergência de branches pendente: assets do fidelity estão não-commitados no worktree `master` (outra sessão ativa). Escolher uma fonte de verdade; evitar edição simultânea.
- Branch: `feat/modeling-3d-v4`.
