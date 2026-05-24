# Micro-plano — Fase 4: Parametrização real + selectors finos + features de sólido restantes

**Fase**: 4 | **Spec**: [`../spec.md`](../spec.md) (RF-016 sólido, RF-018; DT-002) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 3. Insumo detalhado dos gaps: [`../adapter-gaps-roadmap.md`](../adapter-gaps-roadmap.md) (G1–G3). Primeira onda de cobertura.

## Objetivo

Levar o workspace **Sólido** à cobertura completa e paramétrica de verdade: dimensões vinculadas a parâmetros/expressões (não "assadas"), **selectors estáveis** de faces/arestas/corpos, e as **features de sólido restantes** (chanfro, draft, shell, padrões, rib, thread, combine, etc. conforme o roadmap de gaps).

## Estado atual (ponto de partida)

- `fusion_mcp_scripts.py`/`fusion_adapter.py` — features de sólido parciais; parametrização "assada" via `createByReal` sem vínculo a parâmetro (DT-002); selectors grosseiros.
- `adapter-gaps-roadmap.md` cataloga G1 (parametrização), G2 (selectors), G3 (features faltantes).

## Decisões-chave

1. **Parametrização real**: parâmetros de usuário + expressões; dimensões de sketch e features referenciam parâmetros (encerra DT-002).
2. **Selectors estáveis**: referência robusta a faces/arestas/corpos resistente a recompute (estratégia a fixar — ex.: por critério geométrico/atributo, não índice volátil).
3. **Cobertura de features**: implementar as features de sólido restantes priorizadas pelo roadmap de gaps, cada uma com verificação geométrica (Fase 2).

## Tarefas atômicas

- **T4.1** — Parametrização real ponta-a-ponta (parâmetros/expressões) em sketches e features.
- **T4.2** — Estratégia de selectors estáveis + aplicação nas features que dependem de seleção.
- **T4.3** — Implementar features de sólido restantes (lista priorizada de G3 em `adapter-gaps-roadmap.md`), com geometria esperada para verificação.
- **T4.4** — Testes por feature (mock) + asserções de verificação; atualizar `adapter-gaps-roadmap.md` marcando o que foi fechado.

## Contratos / invariantes

- Toda nova feature entra pela allowlist de fonte única (`tool_registry.py`).
- Operação não suportada falha explicitamente (RF-018), sem script livre (RF-023).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- **Gate do dono (Fusion real)**: peça **Nível 1 aprofundada** (suporte totalmente paramétrico — alterar um parâmetro recomputa corretamente furos/fillets) modelada por chat.

## Riscos

- **Selectors frágeis** quebram em recompute → retrabalho. Mitigação: validar estratégia no Fusion real cedo.
- **APIs version-sensitive** (G5) → tools falham no real. Mitigação: smoke por tool no gate; herdar achados da auditoria (Fase 0).

## Definição de pronto (Fase 4)

- [ ] Parametrização real (DT-002 encerrada).
- [ ] Selectors estáveis aplicados.
- [ ] Features de sólido restantes (G3) implementadas e verificadas.
- [ ] Testes verdes; gate do dono (Nível 1 aprofundado) aprovado.
