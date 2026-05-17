# MVP readiness

Status em 2026-05-14.

## Já encaminhado sem depender de decisão externa

- Monorepo com backend FastAPI, web React/Vite/TypeScript, wrappers Tauri/Capacitor, pacotes compartilhados e infraestrutura Docker.
- Desenvolvimento principal dentro de container via `infra/docker-compose.yml` + `infra/docker-compose.dev.yml`.
- Postgres como storage transacional no ambiente containerizado, com fallback JSON para desenvolvimento leve.
- Qdrant, Valkey, health checks e scripts de dev/teste.
- Gateway LLM com contratos para OpenAI, Anthropic, Google e fallback dev local habilitado por configuração.
- Configuração local de API keys por provedor com armazenamento cifrado em `.local/state`.
- Cost Governor inicial com política editável, estimativa por tokens e auditoria de chamadas.
- RAG para arquivos e documentos com storage em `.local/files`, parsing de PDF/Markdown/TXT/CSV/DOCX/HTML, OCR opcional de imagens, chunking, embedding local, indexação em background, Qdrant e fallback por metadados.
- Biblioteca `Arquivos` com upload, CRUD, download/preview, filtros, paginacao e deduplicacao.
- Bases de conhecimento curadas, associadas a projetos, agentes e contexto da conversa.
- Importacao local de historico do ChatGPT a partir de `conversations.json`, shards ou ZIP, com deduplicacao, assets e job em background.
- UI inicial responsiva em português BR: sidebar, historico paginado, projetos/pastas, chat, anexos, modos de execucao, painel de contexto/auditoria/prompts/configurações/RAG/arquivos/bases/agentes/3D e estado mobile.
- Geracao de imagem via OpenAI Images API, Deep Research via Responses API e resumo oficial de raciocinio opt-in.
- Modo multiagente por contexto: agente principal/orquestrador, agente solicitado e agentes de apoio entram no prompt e na auditoria.
- Modelagem 3D local por MCP com Blender real quando configurado, Fusion 360 por add-in loopback quando instalado, snapshots, rollback, tool calls e printability.
- Governança SDD com checklist obrigatório de entrega, confirmação prévia de branch/commit semântico e specs separadas por domínio.

## Lacunas que ainda fazem parte do MVP funcional

- Persistir workers em uma fila externa se o volume de OCR/indexacao/importacao crescer alem do processo local.
- Criar fluxo automatico assistido para transformar historico importado do ChatGPT em bases de conhecimento revisadas.
- Implementar sandbox real para `python.run` e `filesystem.write`; hoje o runtime avalia permissao, exige aprovacao quando necessario e retorna erro seguro para essas ferramentas.
- Memoria duravel da JUDITE/agentes e workflows LangGraph reais com checkpoints humanos.
- Pareamento mobile por QR local, cache offline completo e acesso fora da máquina local por rede privada/VPN.
- Testes de interface com navegador real e screenshots/recordings em desktop/mobile.
- Provider registry preenchido/revisado com IDs reais de modelos e custos atuais escolhidos pelo usuário.
- Configuração real de chaves OpenAI, Anthropic e Google pelo usuário.
- Empacotamento Tauri/Capacitor ainda é scaffold, não instalador final.

## Estética atual

A direção visual está adequada para um MVP estilo ChatGPT/local workspace: escura, densa, focada em chat, com painel lateral para contexto operacional. A paleta foi ajustada para carvão neutro com acentos âmbar/azul, evitando uma interface monocromática azul-slate. Os controles principais têm dimensões estáveis, rótulos acessíveis em botões com ícone e layout mobile-first com menu lateral recolhível.

Antes de chamar a UI de finalizada, ainda falta validação visual em navegador real com screenshots em pelo menos `390x844`, `768x1024` e `1440x900`.
