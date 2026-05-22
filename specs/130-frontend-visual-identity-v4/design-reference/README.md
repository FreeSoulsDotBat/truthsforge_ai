# Referência de design — Identidade visual v4 "Hearth"

Cópia (somente leitura, fora do build do Vite) dos arquivos do **bundle de handoff do Claude Design** relevantes para a **Fase 0** desta frente.

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

## Regra de autoridade

Onde `themes.jsx` e `TOKEN_MAP` divergirem (ex.: `--bg-card`, `--ok`, `--err`), **vale `themes.jsx`** — é o que todos os frames renderizam via `var(--…)`.

## Não versionado aqui (ainda)

Os demais frames (`frames/*.jsx`), tutoriais (`tutorial/v4-*.jsx`), transcrições de chat e PDFs de logo só são necessários a partir da Fase 1; serão copiados quando a fase correspondente for implementada (ou recuperados do bundle pela URL acima).
