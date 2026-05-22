# Plano de implementação: [NOME DA FEATURE]

**Pasta da spec**: `specs/[NNN-slug]/` | **Data**: [DATA] | **Spec**: [link para spec.md]

**Entrada**: `specs/[NNN-slug]/spec.md`

> Preenchido na fase `plan`. Descreve **como** implementar no repositório atual. Não duplica o "o quê" da spec.

## Resumo

[Requisito principal (da spec) + abordagem técnica em 2-4 linhas.]

## Contexto técnico

- **Linguagem/Versão**: [ex.: Python 3.11 / TypeScript 5.x]
- **Dependências principais**: [ex.: FastAPI, React/Vite, Qdrant]
- **Storage**: [Postgres / Qdrant / Valkey / filesystem / fallback JSON — ver P5]
- **Testes**: [pytest / vitest]
- **Plataforma-alvo**: [desktop Tauri / web / Android Capacitor]
- **Tipo de projeto**: [backend FastAPI / frontend web / shell]
- **Restrições**: [performance, offline, custo, segurança]

## Constitution Check

*GATE: passar antes da fase de tasks; rechecar após o design.*

Para cada princípio relevante, registre conformidade ou justificativa:

- [ ] P1 Local-first / P2 Stack invariável / P3 Preservar arquitetura
- [ ] P4 Spec/Doc rastreável / P5 Postgres-prod, JSON dev-only
- [ ] P6 Aprovação humana p/ alteração-deleção / P7 RAG com escopo
- [ ] P8 3D human-in-the-loop / P9 Qualidade + PT-BR

Violações justificáveis vão em "Rastreamento de complexidade".

## Estrutura

### Documentação (esta feature)

```text
specs/[NNN-slug]/
├── spec.md
├── plan.md            # este arquivo
├── tasks.md           # gerado na fase tasks
├── handoff.md         # continuidade entre agentes (extensão local)
├── research.md        # opcional
├── data-model.md      # opcional (se houver entidades)
└── contracts/         # opcional (contratos de API)
```

### Código afetado (caminhos reais)

```text
backend/app/...        # bounded context tocado
apps/web/src/...       # feature/área tocada
```

**Decisão de estrutura**: [diretórios reais e por quê.]

## Estratégia / Ondas

[Workstreams ou ondas médias por domínio, na ordem de dependência. Para refactor SDD: o entregável é spec/doc; dívida de código é documentada, não executada.]

## Sequenciamento

[Ordem das ondas/tarefas e dependências entre elas.]

## Validação

Comandos reais (ver `scripts/quality.ps1` e `docs/delivery-checklist.md`):

- Backend: `ruff format --check`, `ruff check`, `pytest`
- Web: `format:check`, `lint`, `test:unit`, `typecheck`, `build`
- Docs (se `docs/` mudar): `pnpm --filter @truths-forge/docs build`
- Cross-links: todos os caminhos citados em spec/plan/tasks existem.

## Riscos e trade-offs

- [Risco] → [mitigação / rollback].

## Rastreamento de complexidade

> Preencher só se o Constitution Check tiver violações a justificar.

| Violação | Por que é necessária | Alternativa simples rejeitada porque |
|----------|----------------------|--------------------------------------|
| [item]   | [necessidade]        | [motivo]                             |
