# Especificação: Frontend Web (shell)

**Pasta da spec**: `specs/090-frontend-web-shell/` | **Criada em**: 2026-05-22 | **Status**: Rascunho

**Entrada**: Cobrir o frontend web inteiro (React/Vite/TS), hoje sem spec (só `features/modeling-3d` tinha cobertura).

> Onda 9 do refactor SDD. Documenta o shell web e a dívida dos monólitos `App.tsx`/`lib/api.ts` e do contrato de tipos manual. O padrão-ouro é `features/modeling-3d/`.

## Cenários de usuário e testes

### História 1 — Shell único, multi-plataforma (Prioridade: P1) 🎯 MVP

Uma base React serve web, desktop (Tauri) e mobile (Capacitor), com UX dark/densa/mobile-first.

**Teste independente**: rodar `apps/web` e navegar pelas áreas (chat, dashboards, 3D).

**Cenários de aceitação**:

1. **Dado** o app web, **Quando** o operador navega, **Então** todas as áreas (chat, agentes, RAG/arquivos, prompts, importação, imagem, 3D) ficam acessíveis com UX consistente.

### História 2 — Consumo do backend via cliente de API (Prioridade: P1)

O frontend fala com o FastAPI via uma camada de cliente, com tipos alinhados ao contrato.

**Cenários de aceitação**:

1. **Dado** uma chamada de API, **Quando** o tipo de resposta muda no backend, **Então** o frontend deve refletir o contrato (hoje manual — ver dívida).

### História 3 — Streaming de chat na UI (Prioridade: P1)

A UI consome o SSE de `/api/chat/stream` e renateriza tokens/estados.

### Casos de borda

- Estados de loading/erro/vazio revisados por tela (P9; checklist frontend).

## Requisitos

### Requisitos funcionais

- **RF-001**: O SISTEMA DEVE renderizar todas as áreas de produto numa base React única (`apps/web/src/App.tsx`, `features/*`).
- **RF-002**: O SISTEMA DEVE consumir o backend via uma camada de cliente (`apps/web/src/lib/api.ts`) com tipos do contrato (`apps/web/src/types/api.ts`).
- **RF-003**: QUANDO o chat transmitir via SSE, O SISTEMA DEVE renderizar tokens/estados incrementais.
- **RF-004**: QUANDO o contrato de API mudar no backend, O SISTEMA DEVE alinhar tipos e consumo no mesmo conjunto de mudanças (`AGENTS.md` Frontend).

### Requisitos não funcionais

- **RNF-001**: Preservar UX dark, densa e mobile-first; rótulos acessíveis e consistência visual (P9; `AGENTS.md`).
- **RNF-002**: Não introduzir dependências pesadas sem necessidade clara.

## Critérios de sucesso

- **CS-001**: Build web (`pnpm --filter @truths-forge/web build`) e typecheck verdes.
- **CS-002**: Novas features seguem o padrão de `features/<dominio>/` (api/store/types/hooks/components).

## Premissas

- `features/modeling-3d/` é o padrão de organização a ser replicado.

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `apps/web/src/App.tsx`, `apps/web/src/main.tsx`, `apps/web/src/lib/api.ts`, `apps/web/src/types/api.ts`, `apps/web/src/types/openapi.json`, `apps/web/src/app/store.ts`, `apps/web/src/app/queries/app-data.ts`, `apps/web/src/app/hooks/`, `apps/web/src/features/` (agents, chat, dashboard, files, modeling-3d, projects, sidebar), `apps/web/src/components/`, `apps/web/src/shared/utils/`
- Docs: `docs/local-dev.md`, `docs/application-map.md`, `AGENTS.md` (Frontend)
- Testes: `apps/web/src/app/store.test.ts`, `apps/web/src/lib/message-content.test.tsx` (+ testes em `features/modeling-3d/`)
- Specs relacionadas: `specs/010-chat-orchestration/`, `specs/005-modeling-3d-fusion/`

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: `apps/web/src/App.tsx` é um **monólito de 3400 linhas** (roteamento, fetch, estado, streaming, uploads, config de agentes, importação, contexto 3D). Direção: decompor por feature/hooks, espelhando `features/modeling-3d/`. Esforço: L.
- **DT-002**: `apps/web/src/lib/api.ts` (449 linhas) é um cliente monolítico. Direção: dividir por domínio (`apiChat`, `apiFiles`, `apiModeling3d`, ...) como já feito em `features/modeling-3d/api/`. Esforço: M.
- **DT-003**: `apps/web/src/types/api.ts` (740 linhas) é mantido **à mão** apesar de `types/openapi.json` (6681 linhas) existir e não ser usado. Direção: gerar tipos do OpenAPI (ex.: `openapi-typescript`) para eliminar drift. Esforço: M. ADR? recomendado (nova ferramenta de build).
- **DT-004**: Estado fragmentado (Zustand + muitos `useState` em App.tsx) e fetch monolítico de snapshot (`app/queries/app-data.ts`). Direção: React Query por entidade + camadas de estado claras. Esforço: L.

## Verificação de qualidade da spec

- [x] Requisitos testáveis com Fontes válidas
- [x] Constituição referenciada
- [x] Dívida documentada (não executada)
