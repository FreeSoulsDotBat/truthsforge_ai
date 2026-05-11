# Roadmap

## M0 - Bootstrap

- Git, monorepo, docs e scripts.
- FastAPI com OpenAPI e endpoints de saude/status.
- React/Vite responsivo, dark mode e shell visual.
- Docker Compose com Postgres/pgvector, Qdrant e Valkey.
- Tauri/Capacitor scaffoldados.

## M1 - Chat e Historico

- Provider gateway real para OpenAI, Anthropic e Google.
- Streaming SSE preparado para uso real de modelos.
- Persistencia em Postgres no modo containerizado.
- Configuracao de chaves e model registry editavel.
- Auditoria basica de tokens/modelos.

## M2 - JUDITE e Prompt Library

- JUDITE como router inicial.
- Prompt library com variaveis, tags, favoritos e versionamento.
- Projetos e associacao com chats/agentes.

## M3 - Agentes

- CRUD completo de agentes.
- LangGraph com state, memoria e human-in-the-loop.
- Permissoes por agente/ferramenta.
- Painel de aprovacoes.

## M4 - RAG

- Ingestao inicial de texto/Markdown com chunking, embedding local deterministico e Qdrant.
- Upload e storage de PDF, MD, TXT, CSV, DOCX, HTML e imagens.
- Parsing/chunking/OCR PT-BR.
- Embeddings locais para infraestrutura.
- Busca hibrida e chat com documentos.

## M5 - Custos, Auditoria e Retencao

- Cost Governor com limite de R$200/mes.
- Painel de auditoria.
- Logs sanitizados.
- Politica de historico ativo de 1 ano e compactacao/sumarizacao.

## M6 - Mobile

- Capacitor Android com pairing.
- Indicador online/offline.
- Cache local somente leitura.
- Fluxo documentado para Tailscale/WireGuard.

## M7 - Artifacts e Ferramentas

- Painel de artifacts/canvas.
- Render Markdown, codigo, JSON, Mermaid, HTML, tabelas e graficos.
- Export PDF, MD, HTML, DOCX, PPTX e JSON.
- Execucao Python/JS sandboxada.

## M8 - Hardening

- Tauri desktop maduro.
- Empacotamento do backend.
- Backups locais.
- Migrações e testes integrados.
