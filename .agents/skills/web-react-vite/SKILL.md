---
name: web-react-vite
description: Use ao alterar a UI principal em React/Vite/TypeScript, estados de tela, consumo de API, componentes e testes unitários de frontend.
---

## Objetivo

Manter a experiência principal do produto consistente com o baseline atual.

## Sempre consultar primeiro

- `apps/web/package.json`
- `docs/application-map.md`
- `docs/mvp-readiness.md`
- `specs/000-repo-foundation/spec.md`
- `docs/3d-mcp-modeling.md` quando a mudança tocar a aba 3D

## Regras

- Preserve a UX dark, densa e mobile-first.
- Mantenha textos da UI em PT-BR quando isso não conflitar com APIs externas.
- Não introduza dependência pesada sem justificar.
- Quando contrato de API mudar, alinhe tipos e chamadas no mesmo conjunto de mudanças.
- Se tocar componentes sensíveis, adicione ou atualize testes unitários.

## Entrega mínima

- comportamento visível explicado;
- impacto em contratos documentado;
- testes e typecheck considerados.
