# MVP readiness

Status em 2026-05-03.

## Já encaminhado sem depender de decisão externa

- Monorepo com backend FastAPI, web React/Vite/TypeScript, wrappers Tauri/Capacitor, pacotes compartilhados e infraestrutura Docker.
- Desenvolvimento principal dentro de container via `infra/docker-compose.yml` + `infra/docker-compose.dev.yml`.
- Postgres como storage transacional no ambiente containerizado, com fallback JSON para desenvolvimento leve.
- Qdrant, Valkey, health checks e scripts de dev/teste.
- Gateway LLM com contratos para OpenAI, Anthropic, Google e fallback dev local habilitado por configuração.
- Configuração local de API keys por provedor com armazenamento cifrado em `.local/state`.
- Cost Governor inicial com política editável, estimativa por tokens e auditoria de chamadas.
- RAG inicial para texto/Markdown com storage em `.local/files`, chunking, embedding determinístico local e indexação/consulta no Qdrant.
- Importacao local de historico do ChatGPT a partir de `conversations.json` ou ZIP com deduplicacao.
- UI inicial responsiva em português BR: sidebar, chat, painel de contexto/auditoria/prompts/configurações/RAG e estado mobile.

## Lacunas que ainda fazem parte do MVP funcional

- Upload real de arquivos, parsing por tipo, OCR e jobs longos de indexação.
- Indexacao opcional do historico importado do ChatGPT como base de conhecimento/RAG.
- Fluxo de agentes com aprovação humana para ferramentas sensíveis.
- Autenticação/pareamento para acesso mobile fora da máquina local.
- Testes de interface com navegador real e screenshots em desktop/mobile.
- Provider registry preenchido com IDs reais de modelos e custos atuais escolhidos pelo usuário.
- Configuração real de chaves OpenAI, Anthropic e Google pelo usuário.
- Empacotamento Tauri/Capacitor ainda é scaffold, não instalador final.

## Estética atual

A direção visual está adequada para um MVP estilo ChatGPT/local workspace: escura, densa, focada em chat, com painel lateral para contexto operacional. A paleta foi ajustada para carvão neutro com acentos âmbar/azul, evitando uma interface monocromática azul-slate. Os controles principais têm dimensões estáveis, rótulos acessíveis em botões com ícone e layout mobile-first com menu lateral recolhível.

Antes de chamar a UI de finalizada, ainda falta validação visual em navegador real com screenshots em pelo menos `390x844`, `768x1024` e `1440x900`.
