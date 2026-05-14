# spec.md

## Título

Baseline do MVP local-first da Truth's Forge AI

## Status

Baseline SDD inicial versionado no repositório.

## Objetivo

Consolidar, em um contrato executável por humanos e agentes, o baseline do produto que já aparece de forma distribuída no código e na documentação versionada.

## Problema

O repositório já possui arquitetura, decisões, roadmap, readiness e módulo 3D documentados, mas ainda não possuía uma superfície SDD explícita que:

- organize a intenção do produto em uma spec rastreável;
- traduza essa intenção em plano técnico aderente ao código atual;
- quebre o trabalho em tarefas atômicas;
- dê contexto reutilizável a agentes de implementação.

## Usuário primário

- Operador único do sistema.
- Mesmo operador usando desktop Windows como centro do sistema.
- Mesmo operador usando Android como cliente pareado.

## Escopo incluído

### Núcleo do produto

- Chat multi-modelo com streaming.
- Registry de modelos e configuração de provedores.
- Persistência de chats, mensagens e histórico.
- Projetos, prompts e organização do workspace.
- Biblioteca de arquivos, importação e bases de conhecimento.
- Recuperação RAG baseada em bases ativas.
- Auditoria local e Cost Governor.
- Agentes com policy de ferramentas e aprovação humana.
- Geração de imagem, Deep Research e resumo oficial quando provider/modelo suportarem.
- Modelagem 3D com MCP local e bounded context próprio.
- Shells desktop/mobile alinhados ao frontend web.

### Escopo organizacional do SDD

- Criar uma entrada formal `spec → plan → tasks`.
- Tornar o repositório operável por agentes com `AGENTS.md`, `CLAUDE.md` e skills.
- Usar documentação versionada como backing context do SDD.
- Permitir continuidade de trabalho entre Codex, Claude Code, Devin e humanos sem depender de conversa histórica.

## Escopo excluído neste baseline

- Reescrita completa de storage.
- Replataformização de frontend/backend.
- Exposição pública ingênua do backend desktop na internet.
- Automação sem aprovação para operações destrutivas.
- Mudança de stack apenas para seguir arquitetura histórica.
- Empacotamento final e publicação de apps como requisito de curto prazo.

## Requisitos funcionais

### Chat e modelos

- QUANDO o usuário enviar uma mensagem em um chat, O SISTEMA DEVE responder com streaming e persistir a interação.
- QUANDO o modelo ou provider não estiver configurado, O SISTEMA DEVE falhar de forma explícita ou cair em provider dev apenas quando o ambiente permitir.
- QUANDO houver múltiplos modelos disponíveis, O SISTEMA DEVE manter um registry editável de modelos, custos e capacidade.

### Organização do workspace

- QUANDO o usuário criar ou editar projetos, prompts e agentes, O SISTEMA DEVE persistir esses artefatos e permitir sua recuperação posterior.
- QUANDO um chat pertencer a um projeto, O SISTEMA DEVE permitir que esse projeto influencie o contexto e a busca em bases associadas.

### Arquivos, importação e RAG

- QUANDO um arquivo entrar no sistema, O SISTEMA DEVE registrá-lo na biblioteca de arquivos.
- QUANDO o usuário optar por indexar um arquivo ou importação, O SISTEMA DEVE extrair conteúdo, criar chunks, vincular metadados e enviá-los ao índice vetorial.
- QUANDO uma base de conhecimento estiver ativa para um projeto ou agente, O SISTEMA DEVE buscar apenas no escopo permitido antes de montar contexto para a LLM.
- QUANDO o conteúdo for sensível, O SISTEMA DEVE exigir decisão explícita antes de envio para provedores externos.

### Agentes, ferramentas e segurança

- QUANDO um agente solicitar o uso de uma ferramenta sensível, O SISTEMA DEVE aplicar a policy configurada por agente ou domínio.
- QUANDO uma ação envolver escrita local, execução de código ou integrações de maior risco, O SISTEMA DEVE exigir aprovação humana, registrar auditoria e expor resultado rastreável.
- QUANDO a ferramenta for somente leitura e classificada como segura, O SISTEMA PODE executá-la automaticamente se a policy permitir.

### Modelagem 3D

- QUANDO o usuário abrir um fluxo 3D, O SISTEMA DEVE operar por plano estruturado, execução incremental e auditoria.
- QUANDO uma etapa 3D for mutável ou high-risk, O SISTEMA DEVE exigir aprovação humana.
- ANTES de executar uma mudança significativa no workspace 3D, O SISTEMA DEVE permitir snapshot e rollback.
- QUANDO houver export ou validação de printability, O SISTEMA DEVE registrar tool calls e artefatos gerados.

### Mobile e shells

- QUANDO o frontend web for empacotado para desktop, O SISTEMA DEVE continuar tratando o desktop como centro local do produto.
- QUANDO o mobile acessar o backend, O SISTEMA DEVE operar como cliente pareado do desktop.
- ENQUANTO o mobile estiver sem servidor acessível, O SISTEMA DEVE degradar de forma clara, com cache offline somente leitura quando essa capacidade estiver pronta.

## Requisitos não funcionais

### Arquitetura e plataforma

- O SISTEMA DEVE permanecer local-first.
- O SISTEMA DEVE preservar o monorepo como unidade de evolução.
- O SISTEMA DEVE manter Postgres como store transacional preferencial em uso real local.
- O SISTEMA DEVE manter Qdrant como índice vetorial principal até decisão explícita em contrário.
- O SISTEMA DEVE tratar Valkey/Redis como infraestrutura local preparada para cache/fila, mesmo que workers atuais ainda rodem em memória.

### Qualidade e manutenção

- Toda mudança relevante DEVE ter validação automatizada compatível com backend e frontend impactados.
- Toda mudança de contrato DEVE atualizar documentação e/ou spec correspondente.
- Toda task concluída DEVE poder ser rastreada até um item do `tasks.md` quando fizer parte do roadmap SDD.

### Segurança, privacidade e custo

- Chaves e segredos DEVEM ficar no backend ou storage local protegido, nunca no browser.
- O acesso remoto fora da máquina local DEVE priorizar VPN/pareamento, não exposição pública ingênua.
- O sistema DEVE continuar a explicitar custos estimados e registrar auditoria mínima das chamadas.
- Operações com MCP, scripts e comandos DEVEM seguir least privilege e aprovação explícita quando sensíveis.
- Decisões tomadas por agentes DEVEM ser rastreáveis em spec, task, PR ou handoff, sem depender da memória interna de uma ferramenta específica.

## Critérios de sucesso do baseline

- Existe uma fonte SDD clara e navegável na árvore do repositório.
- Um agente novo consegue entender o repositório via `AGENTS.md` + skills sem depender de conversa histórica.
- Claude Code consegue carregar o mesmo contrato comum via `CLAUDE.md`.
- Devin, Codex e humanos conseguem retomar trabalho pelo mesmo `tasks.md` e `handoff.md`.
- O baseline do produto fica alinhado ao estado real do código e docs.
- As lacunas do MVP ficam listadas como trabalho decomposto e priorizado, não como intenção difusa.

## Fontes de verdade para esta spec

- `README.md`
- `docs/application-map.md`
- `docs/architecture.md`
- `docs/decisions.md`
- `docs/implementation-plan.md`
- `docs/roadmap.md`
- `docs/mvp-readiness.md`
- `docs/3d-mcp-modeling.md`
