# Specs

Esta pasta guarda as especificações vivas do repositório.

## Convenção

Cada spec fica em uma pasta própria:

- `spec.md` — o que o sistema ou feature deve fazer.
- `plan.md` — como a implementação deve acontecer no repositório atual.
- `tasks.md` — decomposição em trabalho atômico e verificável.
- `handoff.md` — estado de continuidade quando humanos, Codex, Claude Code ou Devin alternarem a execução (extensão local do Spec Kit).

Artefatos opcionais do Spec Kit, por feature, quando agregarem: `research.md`, `data-model.md`, `quickstart.md`, `contracts/` e `checklists/`.

## Padrão GitHub Spec Kit

O repositório adota o padrão **GitHub Spec Kit**:

- Pastas de spec usam numeração `specs/NNN-<slug>/` (ex.: `010-chat-orchestration`). A migração das specs legadas para `NNN-` está em andamento; specs absorvidas por um domínio novo são arquivadas em `specs/_legacy/<slug>/`.
- Invariantes em `.specify/memory/constitution.md`; templates em `.specify/templates/`; scripts auxiliares em `.specify/scripts/` (powershell + bash).
- Fases SDD como skills do Claude Code em `.claude/skills/speckit-*`. Use `create-new-feature` (em `.specify/scripts/`) para criar uma spec a partir do template.

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
- Specs por domínio seguem o padrão `specs/NNN-<slug>/` e devem ser criadas para frentes que excedam ajuste pontual (use `speckit-specify`).
- Toda task relevante deve nascer de uma spec ou atualizar uma spec existente.
- Quando mais de uma IA atuar na mesma frente, registre contexto de continuidade em `handoff.md`.

## Specs de domínio aprovadas

- `specs/agents-tools/`
- `specs/rag-sensitive-data/`
- `specs/mobile-pairing/`
- `specs/artifacts-export/`
- `specs/modeling-3d-fusion/`
- `specs/observability-quality/`
