# Micro-plano — Fase 8: Assemblies / componentes / juntas / materiais (ADR-018)

**Fase**: 8 | **Spec**: [`../spec.md`](../spec.md) (RF-016 assemblies, RNF-005; DT-003) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fases 4–7 + **ADR-018 aceito**. Reverte a decisão "single-body" (`g4-assemblies-decision.md`). É a onda de **maior impacto no data model**.

## Objetivo

Sair do mundo single-body e cobrir **montagens**: componentes e ocorrências (component tree), **juntas** (rígida, revoluta, deslizante, cilíndrica, planar, etc.), **materiais físicos** por corpo/componente, e export/printability **por componente**. Isso muda o data model do plano, os selectors/refs (que passam a atravessar ocorrências) e a UI do card.

## Estado atual (ponto de partida)

- Modelo do plano assume **corpo único** (decisão v3 em `g4-assemblies-decision.md`).
- Selectors/refs locais a um corpo; UI do card single-body; printability por corpo.

## Decisões-chave (a fixar no ADR-018)

1. **Data model**: plano passa a representar **árvore de componentes/ocorrências**; passos referenciam o componente alvo.
2. **Refs/selectors atravessam ocorrências** (qualificação por componente/ocorrência).
3. **Juntas** como entidade de primeira classe (tipo + origens + limites).
4. **Materiais físicos** atribuíveis por corpo/componente.
5. **Export/printability por componente** (cada componente vira artifact próprio quando o destino for impressão — liga RF-026).
6. **Estratégia**: bottom-up (componentes → juntas) como caminho default; as-built quando aplicável.

## Tarefas atômicas

- **T8.1** — **Migração do data model** do plano para árvore de componentes/ocorrências (impacto em `postgres`/`json`/`auto` explicitado).
- **T8.2** — Tools de componente (criar/ativar/inserir ocorrência) + qualificação de refs por ocorrência.
- **T8.3** — Tools de **junta** (tipos + origens + limites) com verificação (graus de liberdade/posição).
- **T8.4** — Atribuição de **material físico** por corpo/componente.
- **T8.5** — UI do card de plano/diagnóstico para múltiplos componentes.
- **T8.6** — Export/printability **por componente**.
- **T8.7** — Testes (mock) de árvore, juntas, materiais; marcar `g4-assemblies-decision.md` como superado por ADR-018.

## Contratos / invariantes

- Allowlist de fonte única; juntas/montagem sob aprovação do plano; auditoria/snapshot/rollback mantidos com escopo de componente.
- Verificação por passo adaptada a montagem (posição/DOF de junta, contagem de componentes).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- Web: `format:check`, `lint`, `test:unit`, `typecheck`, `build` (UI multi-componente).
- Docs: ADR-018 aceito; `docs/3d-mcp-modeling.md` atualizado; `pnpm --filter @truths-forge/docs build`.
- **Gate do dono (Fusion real)**: peça **Nível 5** (caixa + tampa + parafusos como componentes com junta) modelada por chat.

## Riscos

- **Migração de data model** quebra fluxos das fases anteriores. Mitigação: ADR-018 primeiro; migração isolada + testes de regressão dos Níveis 1–4.
- **Refs atravessando ocorrências** é fonte clássica de fragilidade. Mitigação: estratégia de qualificação validada no Fusion real cedo.

## Definição de pronto (Fase 8)

- [ ] Data model de componentes/ocorrências migrado.
- [ ] Juntas + materiais + refs por ocorrência.
- [ ] Export/printability por componente.
- [ ] ADR-018 aceito; `g4-assemblies-decision.md` superado.
- [ ] Testes verdes; gate do dono (Nível 5) aprovado.
