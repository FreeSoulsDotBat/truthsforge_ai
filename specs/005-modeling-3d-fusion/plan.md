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
4. **Nova UI (`homolog-new-ui`)** — toda UI 3D conforme a nova UI em homologação. (RNF-009; **bloqueado** até a branch estar acessível — ver "Pendências de ambiente".)

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

- **Fases 4+ — Cobertura "todo o Design" em ondas** (cada uma com micro-plano + gate):
  1. **4** — Parametrização real completa + selectors finos + features de sólido restantes (consolida G1.2/G2/G3). _Gate:_ Nível 1 aprofundado.
  2. **5** — Superfícies (NURBS). _Gate:_ Nível 2.
  3. **6** — Sheet metal. _Gate:_ Nível 3.
  4. **7** — Sculpt / T-Spline. _Gate:_ Nível 4.
  5. **8** — Assemblies/componentes/juntas/materiais _(ADR-018; muda data model do plano, selectors/refs, UI do card, printability/export por componente)_. _Gate:_ Nível 5.

- **Fase final — QA, docs e handoff** consolidados (cada fase já entrega docs incrementais; aqui se fecham diagramas, `delivery-checklist` e handoff). Inclui a **reconciliação documental v2/v3→v4** catalogada na Fase 0 (remover `safe_auto` e endpoints removidos de `docs/api.md`/`docs/3d-mcp-modeling.md`, marcar 27182/stdio como legado, superar ADR-012/013 com 017/018) e a criação de uma **categoria/landing 3D no Docusaurus** cobrindo os 5 níveis e o servidor MCP (RNF-007).

> **Ordem aprovada pelo dono:** MCP standalone (Fase 1) antes do núcleo agêntico (Fase 2); Fase 0 reabre assemblies. As fases 4–8 são ondas de cobertura e podem ser reordenadas conforme a demanda real do dono.

## Sequenciamento

- 0 → 1 → 2 → 3 são sequenciais (cada uma depende da anterior e do gate).
- 4–8 dependem de 0–3 prontas; entre si são ondas paralelizáveis em planejamento, mas entregues uma a uma com gate (ordenação default por valor/risco; ajustável).
- ADR-017 precede Fase 1; ADR-018 precede Fase 8 (rascunhados na Fase 0).

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

- **Nova UI (`homolog-new-ui`)** — RNF-009 exige que a UI 3D siga a nova UI em homologação. **Estado**: a branch não está acessível neste container (sem remotes; apenas `master` e `feat/modeling-3d-v4`). **Plano combinado com o dono (2026-05-23)**: o dono vai **mergear `homolog-new-ui` na `master`**; depois disso, este plano recebe uma **passada de refactor de UI** para alinhar `apps/web/src/features/modeling-3d/` (componentes, padrões visuais, navegação) à nova UI. Até lá, todas as fases com entrega de UI ficam com a parte de UI **provisória/pendente** desse alinhamento.
- **Sem Fusion no container** — execução real só no ambiente do dono (gate por fase). O CI cobre contrato/compile/unit; o real é validado pelo dono.
- **Convergência de branches (fidelity)** — `agent_loop.py`, `tool_schemas.py` e as mudanças no `planner` estão **não-commitadas no worktree `master`** (outra sessão), não nesta branch v4. Absorvê-los exige convergir as branches (merge/clone fresco). Risco: **duas sessões editando o mesmo módulo** (inclui um `tasks.md` divergente) → escolher **uma fonte de verdade** e evitar edição simultânea. Até convergir, a Fase 0/2 referencia esses assets como alvo de auditoria/integração, sem assumi-los já presentes aqui.
