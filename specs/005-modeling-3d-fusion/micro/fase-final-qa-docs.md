# Micro-plano — Fase final: QA, docs e handoff

**Fase**: F | **Spec**: [`../spec.md`](../spec.md) (todos os CS) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fases 0–8 com gates aprovados. Fecha o v4.

## Objetivo

Consolidar qualidade, documentação e continuidade: regressão completa dos cinco níveis, revisão de segurança do servidor MCP, fechamento de diagramas/docs e handoff entre agentes. Cada fase já entregou docs incrementais; aqui se amarra o todo.

## Tarefas atômicas

- **TF.1** — **Regressão ponta-a-ponta** dos Níveis 1–5 (uma peça-exemplo por nível) no Fusion real, conferindo CS-001..CS-005.
- **TF.2** — **Revisão de segurança** do servidor MCP standalone (auth, exposição local-first, allowlist) — confirmar RNF-001.
- **TF.3** — **Métricas do loop agêntico** (taxa de auto-correção, distribuição de iterações, término explícito) — confirmar CS-003.
- **TF.4** — Fechar **docs** + **reconciliação v2/v3→v4** (backlog da Fase 0/T0.10): atualizar `docs/3d-mcp-modeling.md` (remover `safe_auto` e gate "sempre PARA"; descrever execução autônoma + loop teto-5 + verificação geométrica + MCP standalone), limpar endpoints removidos de `docs/api.md`, marcar 27182/stdio como legado, remover caminho pessoal de `docs/local-dev.md:5`, aceitar ADR-017/018/019 e superar ADR-012/013 em `docs/decisions.md`, atualizar `architecture.md`/`application-map.md`/`mvp-readiness.md`/`implementation-plan.md`/`roadmap.md`. Criar **categoria/landing 3D no Docusaurus** (`apps/docs`) cobrindo os 5 níveis e o servidor MCP (RNF-007). `pnpm --filter @truths-forge/docs build`.
- **TF.5** — Atualizar `handoff.md` com o estado final e pontos abertos (ex.: paridade Blender adiada).
- **TF.6** — Rodar o **checklist de entrega** (`docs/delivery-checklist.md`) completo.

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- Web: `format:check`, `lint`, `test:unit`, `typecheck`, `build`.
- Docs: `pnpm --filter @truths-forge/docs build`.
- Cross-links: todos os caminhos em spec/plan/tasks/micro existem.
- **Gate do dono**: checklist de entrega completo + regressão dos cinco níveis aprovada.

## Riscos

- **Regressões acumuladas** entre fases. Mitigação: suíte de regressão por nível mantida desde a Fase 2.

## Definição de pronto (Fase final)

- [ ] Regressão Níveis 1–5 aprovada no Fusion real.
- [ ] Revisão de segurança do MCP concluída.
- [ ] Métricas do loop dentro do esperado.
- [ ] Docs + ADRs + diagramas fechados; handoff atualizado.
- [ ] Checklist de entrega completo (gate do dono).
