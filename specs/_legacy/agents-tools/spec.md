# spec.md

## Título

Agentes, tools, sandbox e memória operacional

## Status

Decisões de produto aprovadas; implementação futura.

## Objetivo

Transformar JUDITE e os agentes em uma camada de orquestração multi-etapa com delegação de contexto, checkpoints humanos, memória ampla e execução segura de tools.

## Requisitos funcionais

- QUANDO uma tarefa exigir múltiplas etapas, JUDITE DEVE coordenar o workflow, delegar contexto a agentes especialistas e registrar checkpoints.
- QUANDO um agente executar uma ação de adição permitida pela policy, O SISTEMA PODE executar sem aprovação humana.
- QUANDO uma ação alterar ou deletar estado, arquivos, artifacts, dados locais ou recursos externos, O SISTEMA DEVE pedir aprovação humana antes de executar.
- QUANDO uma tool de escrita ou execução rodar, O SISTEMA DEVE usar diretório isolado por projeto.
- QUANDO uma tool mutável executar, O SISTEMA DEVE registrar auditoria e manter rollback obrigatório quando aplicável.
- QUANDO a JUDITE ou agentes aprenderem contexto útil, O SISTEMA DEVE persistir memória de preferências, decisões, histórico resumido, contexto por projeto e demais memórias úteis ao workspace.

## Requisitos não funcionais

- Rede é permitida no sandbox do MVP.
- Timeout recomendado inicial: 60 segundos para execução interativa curta e 5 minutos para jobs explicitamente longos.
- Limite recomendado inicial: 100 MB por artifact gerado e 500 MB por workspace temporário de execução, ajustável por configuração.
- Policies continuam rastreáveis por agente, domínio e tool.

## Fora do escopo imediato

- Integração com marketplace externo de tools.

## Fontes

- `AGENTS.md`
- `docs/decisions.md`
- `docs/implementation-plan.md`
- `specs/repo-foundation/spec.md`
