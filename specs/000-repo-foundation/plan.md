# plan.md

## Título

Plano técnico para consolidar o baseline SDD do `truthsforge_ai`

## Estratégia geral

Aplicar SDD como camada de governança e execução sobre a arquitetura já commitada, sem reescrever a stack atual e sem apagar a documentação existente.

## Premissas

- O repositório é a fonte primária de verdade.
- O baseline arquitetural atual é monorepo + FastAPI + React/Vite + Tauri + Capacitor + Postgres + Qdrant + Valkey.
- O módulo 3D já é um bounded context real e deve continuar separado.
- O mobile continua cliente do desktop.
- Fallback JSON é ferramenta de dev/teste, não alvo de produto.

## Decisões invariantes

### Estrutura SDD

- Usar `specs/000-repo-foundation/` como pacote baseline do produto.
- Criar specs futuras por feature em `specs/<slug>/`.
- Adotar `AGENTS.md` na raiz como contrato comum.
- Adotar `CLAUDE.md` na raiz como adaptador mínimo para Claude Code.
- Adotar `/.agents/skills/` na raiz com skills instruction-first.
- Adotar `specs/000-repo-foundation/handoff.md` para continuidade entre agentes.

### Fronteiras de arquitetura

- Backend continua como núcleo de regras de negócio.
- Frontend web continua sendo a experiência principal compartilhada.
- Tauri e Capacitor continuam wrappers finos.
- Docs em `docs/` continuam como corpus arquitetural vivo referenciado pela spec.
- Modelagem 3D continua com policy própria, snapshots, tool calls e aprovação humana.

## Workstreams

### Foundation SDD

Objetivo: criar a superfície formal de especificação e instrução de agentes.

Entregas:

- `AGENTS.md`
- `CLAUDE.md`
- `specs/README.md`
- `specs/000-repo-foundation/spec.md`
- `specs/000-repo-foundation/plan.md`
- `specs/000-repo-foundation/tasks.md`
- `specs/000-repo-foundation/handoff.md`
- `/.agents/skills/*`

### Coordenação multiagente

Objetivo: permitir que Codex, Claude Code, Devin e humanos continuem trabalho uns dos outros sem reexplicar contexto fora do repositório.

Áreas:

- contrato comum em `AGENTS.md`;
- adaptador de Claude em `CLAUDE.md`;
- handoff em specs relevantes;
- tasks pequenas e rastreáveis;
- registro explícito de decisões, validações e pendências.

### Núcleo do produto

Objetivo: refletir e endurecer o núcleo já existente.

Áreas:

- chat;
- models/settings;
- prompts/projetos;
- audit/cost;
- storage modes;
- docs sync.

### Arquivos e RAG

Objetivo: evoluir o pipeline já implementado para maior qualidade, observabilidade e governança.

Áreas:

- parsing por tipo e OCR;
- filas e status de indexação;
- vinculação entre arquivos, documentos e knowledge bases;
- recuperação restrita a bases ativas;
- decisões explícitas para conteúdo sensível.

### Agentes e ferramentas

Objetivo: transformar scaffolds em operação segura.

Áreas:

- policy por agente;
- approval flow;
- runtime de tools;
- observabilidade por tool call;
- guardrails para leitura/escrita/execução local.

### Modelagem 3D

Objetivo: manter o contexto 3D como trilha própria, sem conflitar com o núcleo do produto.

Áreas:

- UX de plano/execução;
- policy e aprovações;
- snapshots e restore;
- Blender real;
- Fusion bridge;
- printability e exports;
- artifacts derivados.

### Shells desktop e mobile

Objetivo: manter shells finos e funcionalmente coerentes com o frontend principal.

Áreas:

- Tauri maduro no desktop;
- Capacitor pareado no Android;
- indicador online/offline;
- pareamento por dispositivo;
- cache offline completo no mobile.

## Sequenciamento

### Onda A

Criar os artefatos SDD e travar as regras do repositório:

- `AGENTS.md`
- `CLAUDE.md`
- `specs/`
- `handoff.md`
- skills
- ligação explícita com `docs/`

### Onda B

Convergir documentação e código:

- revisar nomes de bounded contexts;
- revisar contratos de storage e RAG;
- revisar gaps de MVP vs readiness.

### Onda C

Atacar lacunas funcionais de maior valor:

- `specs/050-agents-tools-runtime/`: JUDITE orquestradora, workflows multi-etapa, tools, sandbox, memória e rollback.
- `specs/030-files-rag-pipeline/`: classificação sensível manual/heurística, auditoria de documentos e escopo RAG.
- `specs/005-modeling-3d-fusion/`: Blender real, Fusion bridge, snapshots, rollback, printability e artifacts.
- `specs/060-cost-audit-governance/`: auditoria obrigatória e golden paths.

### Onda D

Expandir especializações:

- `specs/100-mobile-desktop-shells/`: QR local, mobile sem autenticação no MVP, indicador online/offline e cache completo.
- `specs/110-artifacts-export/`: canvas, artifacts e exports Markdown/código/JSON/HTML/Mermaid/PDF/DOCX/PPTX.
- Retenção, compactação e performance quando houver volume real.
- Automação de rastreabilidade entre PR, spec, task e documentação.

## Estratégia de validação

### Backend

- `python -m ruff format --check backend/app backend/tests`
- `python -m ruff check backend/app backend/tests`
- `pushd backend && python -m pytest -q && popd`

### Frontend

- `pnpm --filter @truths-forge/web format:check`
- `pnpm --filter @truths-forge/web lint`
- `pnpm --filter @truths-forge/web test:unit`
- `pnpm --filter @truths-forge/web typecheck`

### Documentação e spec

- toda mudança de contrato exige atualização de spec e docs relevantes;
- toda task concluída exige referência cruzada quando fizer parte do SDD;
- toda feature nova deve nascer de uma pasta própria em `specs/` se exceder ajuste pontual;
- toda entrega relevante deve usar o checklist obrigatório de `docs/delivery-checklist.md`;
- antes de alterar a plataforma, o executor deve confirmar branch e commit semântico com o dono do produto.

## Riscos e mitigação

### Risco de duplicação documental

Mitigação:

- não copiar para a spec o conteúdo completo de `docs/`;
- usar a spec como contrato e índice de rastreabilidade.

### Risco de deriva arquitetural por agente

Mitigação:

- `AGENTS.md` explicita invariantes;
- skills por domínio;
- tasks pequenas e verificáveis.

### Risco de automação insegura

Mitigação:

- manter approval humana para operações sensíveis;
- não introduzir scripts livres como caminho padrão;
- preservar snapshots e auditoria nos contextos críticos.

### Risco de rewrites por nostalgia

Mitigação:

- conflitos entre arquitetura histórica e estado atual do código resolvem-se em favor do repositório atual;
- mudanças de stack exigem ADR e spec própria.

## Definition of done do baseline SDD

O baseline estará consolidado quando:

- os arquivos SDD existirem na árvore recomendada;
- as skills cobrirem os principais bounded contexts;
- a documentação atual estiver referenciada pela spec baseline;
- o `tasks.md` listar o backlog principal do MVP em ordem executável;
- `AGENTS.md`, `CLAUDE.md` e `handoff.md` deixarem claro como Codex, Claude Code, Devin e humanos colaboram;
- um agente novo conseguir trabalhar no repo sem depender de conversa anterior.
