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
- Selecao explicita de agente principal, agente solicitado e agentes de apoio no chat.
- LangGraph disponivel como wrapper inicial; workflows com state duravel, memoria e human-in-the-loop ainda evoluem.
- Permissoes por agente/ferramenta com avaliacao no runtime.
- Painel de aprovacoes ainda pendente para ferramentas sensiveis fora do modulo 3D.

## M4 - RAG

- Ingestao de arquivos/documentos com chunking, embeddings locais e Qdrant.
- Upload e storage de PDF, MD, TXT, CSV, DOCX, HTML e imagens.
- Parsing/chunking/OCR PT-BR opcional.
- Busca hibrida simples: vetor + filtros + boost/fallback por metadados.
- Chat com bases de conhecimento, projetos, pastas e anexos.

## M5 - Custos, Auditoria e Retencao

- Cost Governor com limite de R$200/mes.
- Painel de auditoria.
- Logs sanitizados.
- Politica de historico ativo de 1 ano e compactacao/sumarizacao.

## M6 - Mobile

- Capacitor Android com pairing.
- Indicador online/offline.
- Cache offline completo.
- Fluxo documentado para Tailscale/WireGuard.

## M7 - Artifacts e Ferramentas

- Geracao de imagem via OpenAI Images API e registro das imagens em `Arquivos`.
- Runtime inicial de ferramentas por allowlist/permissao: `rag.search` validado, ferramentas perigosas bloqueadas/pendentes de sandbox.
- Painel de artifacts/canvas ainda pendente.
- Render Markdown/codigo/JSON/Mermaid/HTML/tabelas/graficos e export PDF/MD/HTML/DOCX/PPTX/JSON seguem como proximos passos de artifacts.
- Execucao Python/JS sandboxada segue pendente; nao usar `python.run` para codigo real ate existir sandbox.

## M8 - Hardening

- Tauri desktop maduro.
- Empacotamento do backend.
- Backups locais.
- Migrações e testes integrados.
