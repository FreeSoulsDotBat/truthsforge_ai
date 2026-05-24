# Especificação: Identidade visual v4 "Hearth" (apps/web)

**Pasta da spec**: `specs/130-frontend-visual-identity-v4/` | **Criada em**: 2026-05-22 | **Status**: Implementada (Fases 0–7, "Hearth") — mergeada em `master` via PR #42

**Entrada**: Descrição do dono do produto: "Recriar no app React `apps/web` a identidade visual v4 desenhada no Claude Design (direção Hearth: warm/cozy/serifado), com re-skin completo de todas as superfícies e reshape estrutural."

> Idioma: PT-BR (nomes/comandos Spec Kit em inglês). O bundle de handoff do Claude Design é a referência canônica; cópia dos arquivos relevantes em `design-reference/`.

## Cenários de usuário e testes *(obrigatória)*

### História 1 — App inteiro adota a paleta/tom Hearth (Prioridade: P1) — **Fase 0**

Como dono do produto, abro qualquer tela do `apps/web` e vejo a identidade v4: fundos escuros quentes (oklch), marca ember (`#f7931e`), tipografia da marca (Lilita One / Inter / Instrument Serif / JetBrains Mono), foco/scrollbar ember.

**Por que esta prioridade**: é a fundação de tokens; sem ela nenhuma superfície tem as cores/fontes certas. Re-tona o app inteiro de uma vez.

**Teste independente**: redefinir o palette Tailwind para apontar a CSS vars re-tona as 30 superfícies que já usam classes `forge-*` (403 ocorrências), sem editá-las.

**Cenários de aceitação**:

1. **Dado** o app carregado, **Quando** inspeciono qualquer superfície `forge-*`, **Então** as cores resolvem para os valores de `themeVars(HEARTH)` (sem amarelo/azul antigos).
2. **Dado** um campo focado, **Quando** navego por teclado, **Então** o anel de foco é ember (`var(--ember)`), não azul.
3. **Dado** o app, **Quando** as fontes carregam, **Então** vêm self-hosted (`@fontsource`), sem `<link>` externo a `fonts.googleapis.com`.

### Histórias 2–8 — Reshape e re-skin por superfície (P2+) — **Fases 1–7 (implementadas)**

Primitivos/átomos, Shell+Sidebar, Chat, Aside de contexto/Dock, Dashboards, Modais/forms/ImagePreview, Cards 3D (amethyst). Detalhe em `design-reference/` e no plano aprovado (ultraplan).

### Casos de borda

- Wrappers `apps/desktop` (Tauri) / `apps/mobile` (Capacitor) e `packages/ui` consomem o web — verificar se há tokens compartilhados a alinhar (provável só no web).
- Hex inline (232 ocorrências em `src`) permanecem após a Fase 0; migram por superfície nas fases seguintes.

## Requisitos *(obrigatória)*

### Requisitos funcionais

- **RF-001**: O SISTEMA DEVE declarar os tokens v4 como CSS vars em `apps/web/src/styles.css` a partir de `themeVars(HEARTH)` (fonte única da verdade).
- **RF-002**: O SISTEMA DEVE mapear as cores Tailwind `forge-*` para essas CSS vars, preservando os nomes existentes (`forge-amber`, `forge-blue` etc.).
- **RF-003**: QUANDO `themes.jsx` e a tabela `TOKEN_MAP` divergirem, O SISTEMA DEVE seguir `themes.jsx`.
- **RF-004**: O SISTEMA DEVE carregar as fontes da marca self-hosted (`@fontsource`), sem dependência de rede externa em runtime.
- **RF-005**: O SISTEMA DEVE remover o script externo `mcp.figma.com/.../capture.js` do `index.html`.

### Requisitos não funcionais

- **RNF-001**: O SISTEMA DEVE preservar a UX dark, densa e mobile-first e a acessibilidade dos rótulos/foco. _(AGENTS.md · constituição.)_
- **RNF-002**: O SISTEMA DEVE ser local-first; nada essencial à renderização pode depender de CDN externa.

### Entidades-chave

- **Token v4**: par (`--var` CSS, `forge-*` Tailwind) com valor de `themeVars(HEARTH)`; cobre fundo, linha, texto, marca (ember/amethyst/azure), semântico, tipografia, raio e sombra.

## Critérios de sucesso *(obrigatória)*

- **CS-001**: 100% das 30 superfícies `forge-*` renderizam com a paleta Hearth sem editar os arquivos consumidores.
- **CS-002**: `pnpm --filter @truths-forge/web quality` (format:check + lint + test:unit + typecheck) verde.
- **CS-003**: Nenhuma requisição a `fonts.googleapis.com`/`mcp.figma.com` no carregamento.

## Premissas

- Direção Hearth e escopo (re-skin completo + reshape) confirmados pelo dono.
- Fases 1–7 foram entregues após a Fase 0 (multi-PR) e consolidadas em `homolog-new-ui`; o re-skin completo foi mergeado em `master` via PR #42.

## Fontes *(obrigatória neste repo)*

- Constituição: `.specify/memory/constitution.md`
- Docs: `docs/application-map.md`, `docs/architecture.md`
- Código (bounded context): `apps/web/src/styles.css`, `apps/web/tailwind.config.ts`, `apps/web/src/main.tsx`, `apps/web/index.html`
- Specs relacionadas: `specs/090-frontend-web-shell/`
- Referência de design: `design-reference/` (cópia dos arquivos do bundle de handoff do Claude Design)

## Dívida de código documentada *(neste repo; não executar aqui)*

- **DT-001**: 232 hex inline em `apps/web/src` → migrar para tokens conforme cada superfície é refeita (Fases 2–7). Esforço: M. ADR necessário? não.
- **DT-002**: Monolitos `App.tsx` (2553 linhas) e `dashboard-sections.tsx` (1968 linhas) → dividir durante o reshape (Fases 2 e 5). Esforço: L. ADR necessário? não.

## Verificação de qualidade da spec

- [x] Sem detalhe de implementação nos requisitos (linguagem/framework/API) além do necessário ao bounded context web
- [x] Foco em valor; requisitos testáveis e sem ambiguidade
- [x] Critérios de sucesso mensuráveis
- [x] Sem marcadores `[ESCLARECER]` pendentes
- [x] Escopo delimitado; premissas e dependências identificadas
- [x] Seção **Fontes** com caminhos válidos; constituição referenciada
