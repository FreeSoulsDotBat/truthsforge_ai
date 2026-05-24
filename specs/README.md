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

- Pastas de spec usam numeração `specs/NNN-<slug>/` (ex.: `010-chat-orchestration`). Todas as specs ativas já seguem `NNN-`; specs absorvidas por um domínio novo foram arquivadas em `specs/_legacy/<slug>/`.
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

- `specs/000-repo-foundation/` descreve o baseline atual do produto.
- Specs por domínio seguem o padrão `specs/NNN-<slug>/` e devem ser criadas para frentes que excedam ajuste pontual (use `speckit-specify`).
- Toda task relevante deve nascer de uma spec ou atualizar uma spec existente.
- Quando mais de uma IA atuar na mesma frente, registre contexto de continuidade em `handoff.md`.

## Catálogo de specs

Ativas (`specs/NNN-<slug>/`):

- `specs/000-repo-foundation/` — baseline do produto.
- `specs/005-modeling-3d-fusion/` — bounded context 3D (Blender/Fusion).
- `specs/010-chat-orchestration/` — núcleo de chat.
- `specs/020-llm-gateway-models/` — gateway multi-provider e registry de modelos.
- `specs/030-files-rag-pipeline/` — arquivos, RAG e dados sensíveis.
- `specs/040-import-workers-queues/` — importação (ChatGPT) e filas/workers.
- `specs/050-agents-tools-runtime/` — agentes, tools, sandbox e memória.
- `specs/060-cost-audit-governance/` — custo, auditoria e golden paths.
- `specs/070-storage-persistence/` — storage e abstração (proposta ADR-015).
- `specs/080-prompts-projects-workspace/` — prompts e workspace.
- `specs/090-frontend-web-shell/` — frontend web (React/Vite).
- `specs/100-mobile-desktop-shells/` — shells desktop/mobile e pareamento.
- `specs/110-artifacts-export/` — canvas e exports.
- `specs/120-sdd-spec-kit-adoption/` — meta: adoção do Spec Kit e governança SDD.
- `specs/130-frontend-visual-identity-v4/` — identidade visual v4 "Hearth" do `apps/web` (sub-spec de frontend).

Legado (arquivado e congelado em `specs/_legacy/`): `agents-tools`, `rag-sensitive-data`, `observability-quality`, `mobile-pairing` — migradas para `050`/`030`/`060`/`100`, respectivamente.
