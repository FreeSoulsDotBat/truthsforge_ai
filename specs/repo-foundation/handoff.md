# handoff.md

## Objetivo

Registrar continuidade de trabalho entre humanos, Codex, Claude Code e Devin.

Este arquivo não substitui `tasks.md`, issues ou PRs. Ele existe para evitar perda de contexto quando uma frente de trabalho muda de executor.

## Registro atual

### Estado

- Última frente trabalhada: governança SDD por domínio.
- Executor anterior: Devin.
- Executor recomendado para continuação: qualquer agente compatível após leitura de `AGENTS.md`, `spec.md`, `plan.md` e `tasks.md`.
- Branch/PR relacionado: `devin/sdd-domain-specs-governance`.
- Spec relacionada: `specs/repo-foundation/spec.md`.
- Task relacionada: `Foundation SDD` e specs de domínio.

### Decisões tomadas

- `AGENTS.md` é o contrato comum para Codex, Claude Code, Devin e humanos.
- `CLAUDE.md` é apenas adaptador mínimo para Claude Code.
- `specs/repo-foundation/` é o baseline do produto; specs futuras devem usar `specs/<slug>/`.
- Skills ficam em `.agents/skills/` e começam como instruction-only.
- O baseline SDD foi ajustado ao estado atual já documentado: upload/parsing/OCR, workers, geração de imagem e Fusion bridge existem em níveis iniciais e não devem voltar a ser tratados como inexistentes.
- Toda alteração relevante deve confirmar branch e commit semântico com o dono do produto antes de editar.
- Specs devem ser separadas por domínio quando excederem ajuste pontual.
- Checklist obrigatório de entrega vive em `docs/delivery-checklist.md` e no template de PR.
- JUDITE deve evoluir como orquestradora multi-etapa com checkpoints, memória ampla e delegação de contexto.
- Adições por tools podem executar sem aprovação quando a policy permitir; alterações e deleções exigem aprovação.
- Sandbox de tools deve ser por projeto, com rede permitida, timeout, limite, auditoria e rollback obrigatório.
- RAG sensível combina marcação manual e heurística; provedores externos podem receber contexto indexado permitido.
- Mobile MVP usa QR local, sem autenticação de usuário, com cache offline completo.
- Blender real e Fusion bridge são obrigatórios para a trilha 3D atual.
- Todos os formatos de artifacts/export têm mesma prioridade.
- Eventos de LLM, custo, tool calls, documentos, export/delete, pairing e indexação devem ser auditáveis.

### Arquivos tocados

- `AGENTS.md`
- `CLAUDE.md`
- `.agents/skills/**`
- `.github/pull_request_template.md`
- `README.md`
- `apps/mobile/README.md`
- `docs/api.md`
- `docs/application-map.md`
- `docs/architecture.md`
- `docs/decisions.md`
- `docs/delivery-checklist.md`
- `docs/implementation-plan.md`
- `docs/knowledge-bases.md`
- `docs/mvp-readiness.md`
- `docs/roadmap.md`
- `specs/**`

### Validação executada

- `git diff --check`
- `python -m ruff check backend/app backend/tests`
- `pnpm --filter @truths-forge/web typecheck`
- `pnpm --filter @truths-forge/docs build`
- CI do PR #12: GitGuardian e Devin Review verdes no primeiro envio.

### Pendências

- Implementar as tasks funcionais abertas nas specs de domínio.
- Automatizar verificação de links entre specs, docs e PR template.

### Riscos conhecidos

- O SDD pode ficar duplicado em relação a `docs/` se futuras mudanças copiarem conteúdo completo em vez de referenciar docs.
- Tasks marcadas como concluídas no baseline dependem do estado documentado atual; se o código divergir, o código vence.

### Próximo passo recomendado

- Escolher uma spec de domínio e abrir PR funcional pequeno com referência explícita à task.

## Regras

- Atualize este arquivo quando uma tarefa ficar incompleta ou for transferida para outro agente.
- Não registre segredos, tokens, chaves ou dados pessoais sensíveis.
- Não use este arquivo para decisões arquiteturais permanentes; decisões permanentes devem virar docs, ADR ou spec.
- Se o handoff contradisser código, docs ou spec, trate o handoff como contexto temporário e valide antes de agir.
