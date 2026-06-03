# MVP readiness

Status em 2026-06-02.

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
- Modelagem 3D local chat-first por MCP com Blender real quando configurado e Fusion 360 pelo Fusion MCP Server oficial (`/mcp`), com o add-in loopback como fallback legado; planner LLM + heurístico, snapshots, rollback, tool calls, printability e trace. As capacidades v4 (loop agêntico, verificação geométrica/visual, image-to-model, reconciliação ao vivo) existem atrás de flags, a maioria default OFF até o gate do dono no Fusion real.
- Governança SDD com checklist obrigatório de entrega, confirmação prévia de branch/commit semântico e specs separadas por domínio.

## Lacunas que ainda fazem parte do MVP funcional

- Operacionalizar/ligar por padrão a fila externa Redis/Valkey (já disponível opt-in via `TRUTHS_FORGE_QUEUE_BACKEND=redis|valkey`) se o volume de OCR/indexacao/importacao crescer além do processo local.
- Criar fluxo automatico assistido para transformar historico importado do ChatGPT em bases de conhecimento revisadas.
- Implementar sandbox real para `python.run` e `filesystem.write`; hoje o runtime avalia permissao, exige aprovacao quando necessario e retorna erro seguro para essas ferramentas.
- Memoria duravel da JUDITE/agentes e workflows LangGraph reais com checkpoints humanos.
- Pareamento mobile por QR local, cache offline completo e acesso fora da máquina local por rede privada/VPN.
- Testes de interface com navegador real e screenshots/recordings em desktop/mobile.
- Provider registry preenchido/revisado com IDs reais de modelos e custos atuais escolhidos pelo usuário.
- Configuração real de chaves OpenAI, Anthropic e Google pelo usuário.
- Empacotamento Tauri/Capacitor ainda é scaffold, não instalador final.

## Estética atual

A identidade visual **v4 "Hearth"** foi aplicada ao `apps/web` (re-skin com tokens `forge-*` apontando para CSS vars; spec `130-frontend-visual-identity-v4`, PR #42 mergeado na master). A direção é escura, densa, focada em chat, com painel lateral para contexto operacional; os controles principais têm dimensões estáveis, rótulos acessíveis em botões com ícone e layout mobile-first com menu lateral recolhível.

Antes de chamar a UI de finalizada, ainda falta validação visual em navegador real com screenshots em pelo menos `390x844`, `768x1024` e `1440x900`.
