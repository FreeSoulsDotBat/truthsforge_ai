# Micro-plano — Fase 6: Sheet metal

**Fase**: 6 | **Spec**: [`../spec.md`](../spec.md) (RF-016 sheet metal) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 5. Onda de cobertura.

## Objetivo

Cobrir o workspace **Sheet Metal** do Fusion: regras de chapa (espessura, raio de dobra, alívios), flanges, dobras, conversão para chapa, e planificação (flat pattern), com verificação dimensional adequada.

## Estado atual (ponto de partida)

- Cobertura de sheet metal inexistente no adapter.
- Pipeline de sólido + selectors + verificação disponíveis.

## Decisões-chave

1. **Regra de chapa** (sheet metal rule) como entidade do plano: espessura, raio de dobra, tipo de alívio.
2. **Tools**: criar face base, flange, dobra (bend), unfold/refold, flat pattern; conversão de sólido para sheet metal quando aplicável.
3. **Verificação**: espessura constante, ângulos de dobra, e flat pattern gerado.
4. **Export**: flat pattern para DXF como artifact quando o destino for fabricação (liga com RF-026/artifacts).

## Tarefas atômicas

- **T6.1** — Modelar a **regra de chapa** no plano + tool de configuração.
- **T6.2** — Tools de face base, flange, bend, unfold/refold.
- **T6.3** — Flat pattern + export DXF como artifact.
- **T6.4** — Verificação dimensional (espessura/ângulo) + testes (mock).

## Contratos / invariantes

- Allowlist de fonte única; verificação por passo; artifacts/printability conforme contrato (P8).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- **Gate do dono (Fusion real)**: peça **Nível 3** (chapa dobrada com flanges e alívios + flat pattern) modelada por chat.

## Riscos

- **Regras de chapa específicas** (material/processo) → parametrização extensa. Mitigação: começar com regra default + override; expandir conforme demanda do dono.

## Definição de pronto (Fase 6)

- [ ] Regra de chapa + flanges/dobras + flat pattern.
- [ ] Export DXF como artifact.
- [ ] Verificação dimensional; testes verdes; gate do dono (Nível 3) aprovado.
