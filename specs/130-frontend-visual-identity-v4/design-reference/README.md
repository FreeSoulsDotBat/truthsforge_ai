# Referência de design — Identidade visual v4 "Hearth"

Cópia (somente leitura, fora do build do Vite) dos arquivos do **bundle de handoff do Claude Design** relevantes para as **Fases 0–7** desta frente (todas implementadas).

## Origem

Bundle `Truth's Forge AI-handoff.tar.gz`, exportado de [claude.ai/design]. Recuperável via:

```
GET https://api.anthropic.com/v1/design/h/NgMLP7DAsEBp-YUTqn8How
```

## Arquivos aqui

| Arquivo | Papel |
|---|---|
| `themes.jsx` | **Fonte única da verdade** dos tokens — `HEARTH` + `themeVars()`. Os CSS vars em `apps/web/src/styles.css` foram declarados a partir daqui. |
| `v4-tokens.jsx` | Tabela `TOKEN_MAP` (nomes Tailwind ↔ CSS var) + specs canônicas (aside 360px, avatar JUDITE, composer pill 18px, type stack, bordas). Referência humana. |
| `Visual Identity Manual v4.html` | Shell que o dono tinha aberto no handoff. Define as base styles globais (scrollbar ember, keyframes `tf*`) replicadas em `styles.css` e lista os frames das Fases 1–7. |
| `parts.jsx`, `icons.jsx`, `v4-atoms.jsx`, `v4-molecules.jsx`, `forms.jsx`, `minor-components.jsx` | **Fase 1** — átomos/moléculas genéricos e controles de formulário. |
| `sidebar.jsx`, `shell.jsx` | **Fase 2** — sidebar 248px (brandmark, nav, footer JUDITE) + composição do shell (sidebar + main + dock). |
| `chat.jsx` | **Fase 3** — frame do Chat (composer pill, mensagens, empty-state). |
| `panel.jsx`, `tweaks-panel.jsx` | **Fases 3–4** — aside de contexto / dock e painel de ajustes ("Modo de execução"). |
| `dashboards.jsx` | **Fase 4** — corpo dos dashboards (cabeçalho, glifos, selos). |
| `modals.jsx`, `image-preview.jsx` | **Fase 6** — modais/forms (ModalShell) + família ImagePreview com lightbox. |
| `modeling-cards.jsx` | **Fase 7** — cards 3D (amethyst como cor secundária). |
| `v4-shared.jsx` | Helpers/constantes compartilhados pelos frames v4. |

## Regra de autoridade

Onde `themes.jsx` e `TOKEN_MAP` divergirem (ex.: `--bg-card`, `--ok`, `--err`), **vale `themes.jsx`** — é o que todos os frames renderizam via `var(--…)`.

## Não versionado aqui

Com as Fases 0–7 implementadas, todos os frames já estão versionados na tabela acima. Permanecem fora apenas materiais auxiliares que não viram código de produção: tutoriais (`tutorial/v4-*.jsx`), transcrições de chat e PDFs de logo — recuperáveis do bundle pela URL acima (a URL `h/<id>` retorna o `.tar.gz` completo do handoff).
