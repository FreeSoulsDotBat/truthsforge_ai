# Plano de implementação: Frontend Web (shell)

**Pasta da spec**: `specs/090-frontend-web-shell/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Doc-only. Documenta o shell web e registra dívida (DT-001..004).

## Resumo

`App.tsx` (3400 linhas) concentra o app; `lib/api.ts` (449) é o cliente; tipos manuais em `types/api.ts` (740) apesar do `openapi.json`. `features/modeling-3d/` é o padrão de organização a replicar.

## Contexto técnico

- **Linguagem/Versão**: TypeScript 5.x / React 18 / Vite.
- **Plataforma-alvo**: web + Tauri + Capacitor · **Testes**: vitest.

## Constitution Check

- [x] P1 Local-first (shell é cliente do desktop).
- [x] P3 Preservar arquitetura/UX (doc-only).
- [x] P9 Qualidade/PT-BR; UX dark/densa/mobile-first preservada.

Sem violações. (DT-003 introduz ferramenta de build — recomenda ADR antes de executar.)

## Estrutura

```text
apps/web/src/App.tsx        # monólito atual
apps/web/src/features/*     # padrão por feature (modeling-3d é o ouro)
apps/web/src/lib/api.ts     # cliente monolítico
apps/web/src/types/*        # tipos manuais + openapi.json não usado
```

## Estratégia / Ondas

1. Esta onda: spec + dívida.
2. Futuro: decompor App.tsx; dividir api.ts por domínio; gerar tipos do OpenAPI; estado por React Query.

## Validação

- Doc-only: cross-links resolvem. Futuro: `pnpm --filter @truths-forge/web build`, `lint`, `typecheck`, `test:unit` verdes.

## Riscos e trade-offs

- Geração de tipos (DT-003) é mudança de toolchain — exige ADR e cuidado com CI.

## Rastreamento de complexidade

| Violação | Por que é necessária | Alternativa simples rejeitada porque |
|----------|----------------------|--------------------------------------|
| Nova ferramenta de tipos (DT-003) | eliminar drift manual de 740 linhas | tipos manuais divergem do backend silenciosamente |
