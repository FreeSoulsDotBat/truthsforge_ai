# AGENTS.md

## Objetivo do repositório

Truth's Forge AI é um workspace pessoal local-first para chat multi-modelo, JUDITE, agentes, RAG, prompt library, arquivos, importação do ChatGPT, geração de imagens, artifacts/canvas e modelagem 3D supervisionada.

## Ordem de prioridade do contexto

Use esta ordem quando houver conflito entre fontes:

1. Código versionado e contratos atuais do repositório.
2. Documentação versionada em `README.md` e `docs/`.
3. Specs SDD em `specs/`.
4. Materiais externos ou históricos não versionados.
5. Conversas antigas e transcrições.

## Agentes de implementação

Este repositório pode ser trabalhado por Codex, Claude Code, Devin e humanos. Nenhum agente é fonte de verdade isolada.

- Use `AGENTS.md` como contrato comum de arquitetura, qualidade e estilo de entrega.
- Use `CLAUDE.md` apenas como adaptador do Claude Code para carregar `AGENTS.md` e regras específicas dele.
- Use `specs/repo-foundation/handoff.md` para registrar continuidade entre agentes quando uma tarefa for interrompida, transferida ou retomada.
- Não aceite decisões arquiteturais apenas porque uma IA anterior sugeriu; valide contra código, docs e specs.
- Quando continuar trabalho iniciado por outro agente, leia primeiro a spec relevante, `tasks.md`, o handoff mais recente e o diff atual.

## Constituição e SDD (Spec Kit)

- A camada curta de invariantes vive em `.specify/memory/constitution.md` (princípios P1–P9). Este `AGENTS.md` é o "como trabalhar" detalhado; a constituição é "o inegociável". Em conflito, vale a constituição + a ordem de prioridade de contexto acima.
- O repositório segue o padrão **GitHub Spec Kit**: specs em `specs/NNN-<slug>/` (ver `specs/README.md`), templates em `.specify/templates/`, scripts em `.specify/scripts/`, e as fases SDD como skills do Claude Code em `.claude/skills/speckit-*` (constitution → specify → clarify → plan → analyze → tasks → implement). Codex, Devin e humanos seguem os mesmos templates/constituição (agnósticos de agente).
- Toda frente que exceda ajuste pontual nasce de uma spec (`speckit-specify`) e passa pelo Constitution Check no `plan`.

## Princípios obrigatórios

- Preserve a arquitetura atual antes de propor reescritas.
- Não troque stack sem aprovação explícita.
- Mantenha o produto em PT-BR, salvo quando arquivo, API ou convenção exigir inglês.
- Prefira mudanças pequenas, testáveis e auditáveis.
- Atualize documentação e specs quando comportamento, contrato ou fluxo mudar.
- Antes de alterar a plataforma, pergunte ao dono do produto o nome da branch e a mensagem de commit em formato semântico.
- Quando houver dúvida de domínio, consulte primeiro `docs/application-map.md`, `docs/architecture.md`, `docs/decisions.md` e `docs/implementation-plan.md`.
- Caso ainda existam conflitos ou dúvidas de como desenvolver, pergunte ao dono do prompt antes de gerar código.

## Guardrails de arquitetura

- Monorepo com `pnpm` workspaces na raiz.
- Backend principal em Python/FastAPI.
- Frontend principal em React/Vite/TypeScript.
- Desktop como wrapper Tauri.
- Mobile como wrapper Capacitor.
- Stack local preferencial: Postgres + Qdrant + Valkey.
- Fallback JSON é apenas modo de desenvolvimento/teste, não destino arquitetural.
- Modelagem 3D é um bounded context separado; não a reduza a tool genérica.

## Regras por área

### Backend

- Preserve prefixos de rota existentes.
- Adicione ou atualize testes em `backend/tests` ao alterar contratos.
- Prefira mudanças orientadas a domínio, não espalhadas por arquivos aleatórios.
- Se tocar storage, explicite impacto em `postgres`, `json` e `auto`.

### Frontend

- Preserve UX dark, densa e mobile-first.
- Não introduza dependências pesadas sem necessidade clara.
- Mantenha rótulos acessíveis e consistência visual.
- Se mudar contrato de API, alinhe tipos e consumo no mesmo conjunto de mudanças.

### RAG e arquivos

- Conteúdo indexado pode compor prompts para provedores externos configurados; registre e sinalize conteúdo sensível por classificação manual e heurística.
- Diferencie claramente upload, parsing, chunking, indexação, vinculação a bases e recuperação em prompt.

### Agentes e ferramentas

- Ações de adição podem executar sem aprovação quando a policy permitir.
- Alterações e deleções exigem aprovação humana antes da execução.
- Tools com escrita ou execução devem operar em diretório isolado por projeto, com timeout, limite de tamanho, auditoria e rollback obrigatório.

### Modelagem 3D

- Preserve human-in-the-loop para deleções, ações destrutivas e ações high-risk.
- Adições e alterações normais via tools 3D allowlistadas podem autoexecutar no fluxo fluido do chat.
- Não libere script livre, shell ou operações destrutivas no caminho feliz.
- Snapshots manuais, rollback, auditoria e printability são parte do contrato, não detalhe opcional.

## Qualidade obrigatória

Antes de concluir uma tarefa relevante:

- rode os checks equivalentes a `scripts/quality.ps1` para as áreas alteradas;
- valide backend e frontend impactados;
- confirme se documentação e spec continuam coerentes;
- registre no `specs/repo-foundation/tasks.md` o que foi concluído e o que ficou pendente quando a tarefa fizer parte do SDD.
- envie ao dono do produto o checklist de entrega definido em `docs/delivery-checklist.md`.

## Estilo de entrega

Sempre devolva:

- branch e commit semântico usados;
- resumo do que mudou;
- arquivos tocados;
- riscos ou trade-offs;
- comandos de validação usados;
- gaps que ficaram fora do escopo;
- status de handoff quando outro agente precisar continuar.
