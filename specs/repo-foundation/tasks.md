# tasks.md

## Convenções

- `[P0]` = bloqueante para o baseline SDD.
- `[P1]` = importante para MVP funcional.
- `[P2]` = importante, mas não bloqueante no curto prazo.
- `[any]` = qualquer executor pode assumir.
- `[codex]`, `[claude-code]`, `[devin]` = sugestão de ferramenta quando fizer sentido, não propriedade exclusiva.
- `[human]` = exige decisão, revisão ou aprovação humana.
- Cada item deve virar commit ou PR pequeno sempre que possível.
- Quando uma tarefa passar de uma IA para outra, atualizar `handoff.md` com contexto, decisões, validação e pendências.

## Foundation SDD

- [x] [P0] [any] Criar `AGENTS.md` na raiz do repositório.
- [x] [P0] [claude-code] Criar `CLAUDE.md` na raiz importando `AGENTS.md`.
- [x] [P0] [any] Criar `specs/README.md`.
- [x] [P0] [any] Criar `specs/repo-foundation/spec.md`.
- [x] [P0] [any] Criar `specs/repo-foundation/plan.md`.
- [x] [P0] [any] Criar `specs/repo-foundation/tasks.md`.
- [x] [P0] [any] Criar `specs/repo-foundation/handoff.md`.
- [x] [P0] [any] Criar `/.agents/skills/README.md`.
- [x] [P0] [any] Criar skill `repo-map`.
- [x] [P0] [any] Criar skill `dev-quality-gates`.
- [x] [P0] [any] Criar skill `backend-fastapi`.
- [x] [P0] [any] Criar skill `web-react-vite`.
- [x] [P0] [any] Criar skill `rag-knowledge-bases`.
- [x] [P0] [any] Criar skill `modeling-3d`.
- [x] [P0] [any] Criar skill `mobile-shells`.
- [x] [P0] [any] Referenciar `specs/` no `README.md` e em `docs/application-map.md`.
- [x] [P0] [any] Documentar no SDD que Codex, Claude Code, Devin e humanos compartilham o mesmo contrato arquitetural.
- [x] [P0] [any] Definir rotina de handoff quando um agente continuar trabalho de outro.

## Convergência entre docs e código

- [x] [P0] [any] Revisar se o baseline SDD reflete `Postgres + Qdrant + Valkey` como stack principal.
- [x] [P0] [any] Revisar se o baseline SDD reflete o fallback JSON como dev/test only.
- [x] [P0] [any] Consolidar, no SDD, os bounded contexts já nomeados no backend e nos docs.
- [x] [P1] [any] Criar regra documental: toda mudança de contrato atualiza `docs/` e `specs/`.
- [ ] [P1] [human]

## Chat, modelos, auditoria e custo

- [x] [P1] [any] Registrar streaming de chat como contrato mínimo do baseline.
- [x] [P1] [any] Registrar model registry, custos e settings como parte do baseline.
- [x] [P1] [any] Registrar provider/modelo e preflight de custo como áreas do núcleo já documentadas.
- [x] [P1] [any] Validar persistência de chats, sessões, anexos e projetos como baseline documentado.

## Arquivos, importação e RAG

- [x] [P1] [any] Registrar upload real de arquivos como parte do baseline implementado.
- [x] [P1] [any] Registrar parsing por tipo: PDF, DOCX, Markdown, TXT, CSV, HTML e imagem.
- [x] [P1] [any] Registrar OCR opcional como parte do baseline implementado.
- [x] [P1] [any] Registrar status de indexação e retries de jobs longos como baseline implementado.
- [x] [P1] [any] Registrar indexação opcional do histórico/importações do ChatGPT como pipeline existente.
- [x] [P1] [any] Registrar filtros mínimos de recuperação por base/projeto/tags/tipo como baseline existente.
- [ ] [P1] [human]

## Agentes, tools e approvals

- [x] [P1] [any] Consolidar policy por agente: `allow`, `ask`, `deny`.
- [ ] [P1] [any]
- [ ] [P1] [any]
- [x] [P1] [any] Garantir logs e auditoria por tool call nos fluxos já implementados.
- [ ] [P2] [any]

## Modelagem 3D

- [x] [P1] [any] Preservar no SDD o módulo 3D como epic própria.
- [ ] [P1] [any]
- [ ] [P1] [any]
- [ ] [P2] [any]
- [ ] [P2] [any]
- [ ] [P2] [any]

## Mobile, desktop e pareamento

- [ ] [P1] [any]
- [ ] [P1] [any]
- [ ] [P1] [any]
- [ ] [P1] [any]
- [ ] [P2] [any]
- [ ] [P2] [human]

## Artifacts, canvas e export

- [ ] [P2] [any]
- [ ] [P2] [any]
- [ ] [P2] [any]
- [ ] [P2] [any]

## Hardening e observabilidade

- [ ] [P1] [any]
- [ ] [P1] [human]
- [ ] [P1] [any]
- [ ] [P2] [any]
- [ ] [P2] [any]

## Qualidade contínua

- [x] [P0] [any] Tornar `scripts/quality.ps1` o gate documentado antes de commit/merge.
- [x] [P1] [any] Garantir que cada skill e cada spec nova apontem para comandos reais de validação.
- [x] [P1] [any] Criar regra de feature relevante nascer de spec própria.
- [ ] [P2] [any]
