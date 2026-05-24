# Micro-plano — Fase 2: Núcleo agêntico

**Fase**: 2 | **Spec**: [`../spec.md`](../spec.md) (RF-005/006/007, RF-008/009/010/011, RF-012/013, RF-019, RF-024/025) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 1 (servidor MCP standalone + gate). Insumos: `chat-flow-redesign.md` (fluxo) e `observability-plan.md` (observabilidade).

## Objetivo

Construir o cérebro do produto: após o usuário aprovar o plano, o motor **executa do início ao fim, sem parar**, com um **loop interno de auto-correção** (`executa → inspeciona → corrige`, teto 5) e **verificação geométrica por read-back** (esperado × medido). Persistir chat + histórico de modelagem de forma reconstituível e tornar a observabilidade legível para o dono.

## Estado atual (ponto de partida)

- `chat_orchestrator.py` + `chat_state.py` — state machine descoberta → planejamento → execução → edição.
- `discovery.py` — clarificação; `planner.py`/`planner_service.py` — geração de plano; `policy.py` — risco/aprovação.
- `executor.py` — executa passos (base do loop).
- `observability.py` — traces; `snapshot_service.py` — snapshots/rollback.
- **Absorvido do fidelity-roadmap** (a integrar na branch — ver `plan.md` › Pendências): `agent_loop.py` (`ModelingAgentLoop`, teto duro 5), `tool_schemas.py` (a LLM vê args/unidades/exemplos) e `planner.build_correction_context` (edit-context + falhas). O loop **existe em andaime**, mas: (a) não está ligado ao stream; (b) só corrige em `status=failed`, sem verificação geométrica; (c) bloqueia corretivo high-risk (contra a decisão do dono).

## Decisões-chave

1. **Oráculo de verificação**: cada `ModelingStep` carrega valores dimensionais **esperados**; após executar, o motor lê a geometria (bbox, volume, contagens, dimensões) via tool de read-back e compara. Divergência alimenta a correção (RF-012/013).
2. **Loop**: teto **5 iterações** por ponto de falha; término **sempre explícito** (sucesso ou falha reportada); ao esgotar, **rollback** ao último snapshot seguro (RF-010/011).
3. **Execução atômica**: sem pausa nem validação passo-a-passo após a aprovação; aprovação única cobre high-risk (RF-008/009).
4. **Persistência (P5)**: chat + plano + passos executados + verificações + traces em Postgres (fallback JSON dev) — reconstituível (RF-019).
5. **Observabilidade**: trace por passo + logs legíveis pelo dono na UI; **doc de scripts de terminal de debug** (RF-024/025).

## Tarefas atômicas

- **T2.1** — Estender o contrato de `ModelingStep`/plano com **geometria esperada** por passo (dimensões/contagens/bbox quando aplicável).
- **T2.2** — Implementar tool de **read-back geométrico** (query de bbox/volume/contagens/dimensões) exposta pelo servidor MCP. _(dependente do adapter; validada no gate)_
- **T2.3** — Partir do `ModelingAgentLoop` (`agent_loop.py`) absorvido: **ligá-lo ao stream** após a aprovação (item pendente do fidelity), com término explícito e rollback ao esgotar; manter teto 5.
- **T2.3b** — **Estender `_needs_correction`**: disparar correção também em **divergência geométrica** (read-back esperado × medido), não só em `status=failed`.
- **T2.3c** — Adotar `tool_schemas.py` no planner (a LLM recebe args/unidades/exemplos canônicos) — pré-requisito de fidelidade.
- **T2.4** — Garantir **execução fim-a-fim sem pausa** após aprovação; aprovação única cobrindo high-risk, **inclusive deltas corretivos** (ajustar `agent_loop` para não bloquear corretivo high-risk — DT-010, decisão do dono).
- **T2.5** — **Persistência** do histórico de modelagem (esquema Postgres + fallback JSON; impacto em `postgres`/`json`/`auto` explicitado).
- **T2.6** — **Observabilidade**: trace por passo + relatório de verificação na UI; superfície de logs legível ao dono.
- **T2.7** — Escrever a **doc de scripts de debug** (terminal) por classe de erro (em `docs/` ou `observability-plan.md`).
- **T2.8** — Testes: loop (sucesso, correção, esgotamento+rollback), verificação (conforme/divergente), persistência, fluxo fim-a-fim com adapter mock.

### Correções estruturais achadas na varredura

- **T2.9 (DT-006, clean architecture)** — Consolidar o fluxo na `ModelingChatOrchestrator`; remover regra de negócio e a state machine duplicada de `api/routes/chat_modeling.py` (rota fica fina). Execução passa a ocorrer pelo chat (não por `card.approve`+`card.execute`).
- **T2.10 (DT-005)** — Redesenhar snapshot/rollback para capturar **estado nativo do Fusion** (timeline/B-Rep), não cópia de filesystem — pré-condição do rollback de RF-011.
- **T2.11 (DT-007)** — Persistência **explícita**: em produção, falha do Postgres não cai em JSON silenciosamente (logar/observar/erro claro); JSON só em dev/test.
- **T2.12 (DT-008)** — Adicionar transição de **falha/rollback** distinta em `chat_state` (não tratar `EXECUTION_FAILED` igual a sucesso).

## Contratos / invariantes

- Nenhuma pausa para o usuário entre aprovação e término (RF-008).
- Teto de 5 iterações respeitado; falha terminal nunca deixa modelo inconsistente silencioso (RF-011).
- Snapshot/rollback/auditoria obrigatórios; allowlist de fonte única (P8/RF-022/023).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- Web: `format:check`, `lint`, `test:unit`, `typecheck`, `build` (UI de diagnóstico/verificação).
- **Gate do dono (Fusion real)**: modelar **uma peça Nível 1** (suporte paramétrico com furos e fillets) por chat, do pedido ao resultado, sem intervenção manual; revisar trace por passo + relatório esperado × medido.

## Riscos

- **Read-back limitado pelo adapter** → oráculo fraco. Mitigação: validar a tool de read-back no Fusion real cedo; degradar para verificação parcial declarada.
- **Loop custoso/instável** → custo e tempo. Mitigação: teto 5 + métricas de iteração + término explícito.
- **Esquema de persistência** mexe em storage → P5. Mitigação: explicitar `postgres`/`json`/`auto`; migração isolada.

## Definição de pronto (Fase 2)

- [ ] Loop agêntico com teto 5, término explícito e rollback.
- [ ] Verificação geométrica esperado × medido por passo.
- [ ] Execução fim-a-fim sem pausa; aprovação única cobre high-risk.
- [ ] Persistência de chat + histórico de modelagem (Postgres/JSON).
- [ ] Observabilidade legível + doc de scripts de debug.
- [ ] Rota fina + fluxo consolidado no orchestrator (DT-006); snapshot nativo (DT-005); persistência explícita (DT-007); estado de falha no `chat_state` (DT-008).
- [ ] Testes verdes; gate do dono (Nível 1) aprovado.
