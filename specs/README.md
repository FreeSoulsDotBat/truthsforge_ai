# Specs

Esta pasta guarda as especificações vivas do repositório.

## Convenção

Cada spec fica em uma pasta própria:

- `spec.md` — o que o sistema ou feature deve fazer.
- `plan.md` — como a implementação deve acontecer no repositório atual.
- `tasks.md` — decomposição em trabalho atômico e verificável.
- `handoff.md` — estado de continuidade quando humanos, Codex, Claude Code ou Devin alternarem a execução.

## Regra de ouro

A spec não substitui o código nem a documentação arquitetural já versionada.

Ela organiza intenção, decisão técnica e trabalho em aberto com rastreabilidade explícita para:

- `README.md`
- `docs/application-map.md`
- `docs/architecture.md`
- `docs/decisions.md`
- `docs/implementation-plan.md`
- `docs/mvp-readiness.md`
- `docs/3d-mcp-modeling.md`

## Uso

- `specs/repo-foundation/` descreve o baseline atual do produto.
- Specs por domínio seguem o padrão `specs/<slug-do-dominio>/` e devem ser criadas para frentes que excedam ajuste pontual.
- Toda task relevante deve nascer de uma spec ou atualizar uma spec existente.
- Quando mais de uma IA atuar na mesma frente, registre contexto de continuidade em `handoff.md`.

## Specs de domínio aprovadas

- `specs/agents-tools/`
- `specs/rag-sensitive-data/`
- `specs/mobile-pairing/`
- `specs/artifacts-export/`
- `specs/modeling-3d-fusion/`
- `specs/observability-quality/`
