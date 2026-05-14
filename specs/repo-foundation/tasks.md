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
- [ ] [P1] [human] Criar checklist de PR com referência obrigatória a spec/task quando aplicável.

## Chat, modelos, auditoria e custo

- [ ] [P1] [any] Confirmar no SDD os contratos mínimos de chat streaming em specs futuras por feature quando mudarem.
- [ ] [P1] [any] Garantir que model registry, custos e settings tenham rastreabilidade explícita em specs de mudanças futuras.
- [ ] [P1] [any] Enriquecer a task list do núcleo com erros por provider/modelo e preflight de custo quando esses fluxos forem alterados.
- [x] [P1] [any] Validar persistência de chats, sessões, anexos e projetos como baseline documentado.

## Arquivos, importação e RAG

- [x] [P1] [any] Registrar upload real de arquivos como parte do baseline implementado.
- [x] [P1] [any] Registrar parsing por tipo: PDF, DOCX, Markdown, TXT, CSV, HTML e imagem.
- [x] [P1] [any] Registrar OCR opcional como parte do baseline implementado.
- [x] [P1] [any] Registrar status de indexação e retries de jobs longos como baseline implementado.
- [x] [P1] [any] Registrar indexação opcional do histórico/importações do ChatGPT como pipeline existente.
- [x] [P1] [any] Registrar filtros mínimos de recuperação por base/projeto/tags/tipo como baseline existente.
- [ ] [P1] [human] Definir UX/policy explícita para indexação/anexação de conteúdo sensível.

## Agentes, tools e approvals

- [x] [P1] [any] Consolidar policy por agente: `allow`, `ask`, `deny`.
- [ ] [P1] [any] Implementar fluxo end-to-end de aprovação para tools sensíveis fora do módulo 3D.
- [ ] [P1] [any] Implementar runtime real seguro de ferramentas por allowlist além de `rag.search`.
- [x] [P1] [any] Garantir logs e auditoria por tool call nos fluxos já implementados.
- [ ] [P2] [any] Definir contratos para rollback quando a ferramenta alterar estado local fora do 3D.

## Modelagem 3D

- [x] [P1] [any] Preservar no SDD o módulo 3D como epic própria.
- [ ] [P1] [any] Melhorar UX para distinguir `mock`, adapter ausente, execução real e erro.
- [ ] [P1] [any] Evoluir validações geométricas e printability.
- [ ] [P2] [any] Evoluir Fusion 360 em ambientes desktop reais com add-in/bridge operacional.
- [ ] [P2] [any] Registrar versões nomeadas de modelos e exports como artifacts.
- [ ] [P2] [any] Criar feature-spec própria para `fusion-bridge` quando essa frente for retomada.

## Mobile, desktop e pareamento

- [ ] [P1] [any] Criar fluxo de pareamento mobile por QR/código.
- [ ] [P1] [any] Emitir identidade ou token por dispositivo pareado.
- [ ] [P1] [any] Implementar indicador online/offline real.
- [ ] [P1] [any] Definir cache local somente leitura para histórico básico no mobile.
- [ ] [P2] [any] Endurecer Tauri desktop para empacotamento mais maduro.
- [ ] [P2] [human] Formalizar estratégia de distribuição sem expor o backend publicamente.

## Artifacts, canvas e export

- [ ] [P2] [any] Consolidar canvas para Markdown, código, JSON, HTML preview e Mermaid.
- [ ] [P2] [any] Fechar export inicial para Markdown, HTML, JSON e PDF.
- [ ] [P2] [any] Planejar DOCX/PPTX como ciclo posterior.
- [ ] [P2] [any] Criar versionamento simples de artifacts.

## Hardening e observabilidade

- [ ] [P1] [any] Criar baseline de screenshots/validação visual para resoluções mobile, tablet e desktop.
- [ ] [P1] [human] Revisar e documentar limites de orçamento mensal e comportamento de bloqueio.
- [ ] [P1] [any] Revisar política de retenção e sumarização para histórico.
- [ ] [P2] [any] Normalizar tabelas críticas se JSONB virar gargalo.
- [ ] [P2] [any] Criar índices e métricas de uso nas áreas mais quentes.

## Qualidade contínua

- [x] [P0] [any] Tornar `scripts/quality.ps1` o gate documentado antes de commit/merge.
- [x] [P1] [any] Garantir que cada skill e cada spec nova apontem para comandos reais de validação.
- [x] [P1] [any] Criar regra de feature relevante nascer de spec própria.
- [ ] [P2] [any] Considerar verificação automatizada de links entre `specs/` e `docs/`.
