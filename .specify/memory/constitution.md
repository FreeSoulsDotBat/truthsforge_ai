# Constituição — Truth's Forge AI

Princípios **não-negociáveis** que governam toda fase do SDD (specify → clarify → plan → analyze → tasks → implement) e toda entrega do repositório. A constituição é a camada curta do "inegociável"; o "como trabalhar" detalhado vive em `AGENTS.md`; as decisões com rationale completo vivem em `docs/decisions.md`. Esta constituição **referencia** essas fontes, não as substitui.

Em caso de conflito, vale a ordem de prioridade de contexto de `AGENTS.md` (código versionado → docs → specs → materiais externos → conversas).

## Princípios

### P1 — Local-first, desktop no centro

O produto é local-first: o desktop Windows é o centro computacional e a fonte primária de dados. O mobile é cliente pareado. Acesso remoto prioriza VPN/pareamento (Tailscale/WireGuard); exposição pública ingênua do backend é proibida.
_Fonte: ADR-001, ADR-006; `docs/architecture.md`._

### P2 — Stack invariável sem ADR

A stack é fixa: monorepo `pnpm`, backend FastAPI/Python 3.11, frontend React/Vite/TypeScript, desktop Tauri, mobile Capacitor, Postgres + Qdrant + Valkey. **Trocar de stack exige ADR novo e aprovação explícita do dono do produto** — nunca como efeito colateral de uma feature.
_Fonte: ADR-001/002/003/004; `AGENTS.md` (Guardrails de arquitetura)._

### P3 — Preservar arquitetura antes de reescrever

Preserve a arquitetura atual antes de propor reescritas. Prefira mudanças pequenas, testáveis e auditáveis. Conflito entre arquitetura histórica e o código atual resolve a favor do código versionado, não de uma sugestão de IA anterior.
_Fonte: `AGENTS.md` (Princípios obrigatórios)._

### P4 — Spec/Doc como fonte de verdade rastreável

Toda mudança relevante nasce de uma spec/task e atualiza `docs/` + `specs/` quando contrato, comportamento ou fluxo mudar. Decisões de agentes devem ser rastreáveis em spec, task, PR ou handoff — nunca dependentes da memória interna de uma ferramenta. Frentes que excedem ajuste pontual ganham spec própria em `specs/NNN-<slug>/`.
_Fonte: ADR-008; `specs/README.md`._

### P5 — Postgres é produção; JSON é só dev/test

Postgres é o store transacional de uso real; Qdrant é o índice vetorial principal; Valkey é cache/fila. O fallback JSON existe **apenas** para dev/test quando o Postgres não está disponível — nunca é destino arquitetural, formato de produção ou caminho de sincronização. Tocar storage exige explicitar impacto em `postgres`, `json` e `auto`.
_Fonte: ADR-004; `AGENTS.md` (Backend)._

### P6 — Autonomia de agentes com aprovação humana

Adições podem auto-executar quando a policy permitir. **Alterações e deleções exigem aprovação humana.** Tools de escrita/execução operam em diretório isolado por projeto, com timeout, limites de tamanho, auditoria e rollback obrigatório. Least privilege é padrão.
_Fonte: ADR-009; `AGENTS.md` (Agentes e ferramentas)._

### P7 — RAG com escopo e dados sensíveis rastreáveis

A recuperação RAG busca apenas no escopo permitido (bases ativas por projeto/agente) antes de montar contexto para a LLM. Conteúdo indexado pode compor prompts a provedores externos configurados; conteúdo sensível é classificado (manual + heurística) com rastreabilidade na auditoria antes de virar contexto.
_Fonte: ADR-010; `AGENTS.md` (RAG e arquivos)._

### P8 — Modelagem 3D é bounded context com human-in-the-loop

A modelagem 3D não é tool genérica: é bounded context próprio, conduzido por chat. Deleções, ações destrutivas e high-risk exigem aprovação humana; adições/alterações allowlistadas podem autoexecutar no fluxo fluido. Snapshots manuais, rollback explícito, allowlist de fonte única, auditoria e printability são contrato, não detalhe opcional.
_Fonte: ADR-012/013/014; `AGENTS.md` (Modelagem 3D)._

### P9 — Qualidade obrigatória e idioma PT-BR

Antes de concluir uma tarefa relevante: rodar os gates equivalentes a `scripts/quality.ps1` para as áreas alteradas e aplicar o checklist de `docs/delivery-checklist.md`. O produto e os artefatos SDD ficam em PT-BR, salvo onde arquivo, API ou convenção exija inglês (ex.: nomes/comandos do Spec Kit). Antes de alterar a plataforma, confirmar com o dono do produto o nome da branch e a mensagem de commit em formato semântico.
_Fonte: `AGENTS.md` (Qualidade obrigatória; Estilo de entrega)._

## Restrições adicionais

- **Gates de qualidade:** backend `ruff format --check`, `ruff check`, `pytest`; web `format:check`, `lint`, `test:unit`, `typecheck`, `build`. Orquestrados por `scripts/quality.ps1` (Docker Compose).
- **Entrega:** todo PR relevante segue `.github/pull_request_template.md` e o checklist de `docs/delivery-checklist.md`.
- **Continuidade:** quando uma frente passar entre Codex, Claude Code, Devin ou humanos, registre contexto em `handoff.md` da spec correspondente.

## Governança

- Esta constituição tem precedência sobre práticas e conveniências pontuais. Conflitos resolvem a favor dela e da ordem de prioridade de contexto de `AGENTS.md`.
- **Emendas:** alterar um princípio exige (1) registro como ADR em `docs/decisions.md`, (2) atualização desta constituição e (3) aprovação do dono do produto. Mudança de stack (P2) ou de guardrails de segurança (P6) nunca é implícita.
- **Versionamento semântico:** MAJOR = remoção/redefinição incompatível de princípio; MINOR = novo princípio ou seção; PATCH = ajustes de redação sem mudar significado.
- **Conformidade:** todo plano (`plan.md`) inclui um "Constitution Check" verificando aderência aos princípios antes da fase de tasks; toda spec cita esta constituição em "Fontes".

**Versão**: 1.0.0 | **Ratificada em**: 2026-05-22 | **Última emenda**: 2026-05-22
