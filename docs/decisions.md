# Decisoes

## ADR-001 - Monorepo

Usar um unico repositorio com frontend compartilhado, wrappers desktop/mobile, backend e infra. Isso reduz atrito para uma aplicacao pessoal e facilita evoluir contratos entre UI e API.

## ADR-002 - FastAPI e Python

Backend em Python 3.11 com FastAPI para favorecer processamento de arquivos, RAG, engenharia de prompts, agentes e ciencia de dados.

## ADR-003 - React/Vite + Tauri + Capacitor

Uma base React responsiva gera web, desktop e mobile. Tauri fica como wrapper Windows e Capacitor como wrapper Android. Instaladores completos ficam depois do dev loop estar estavel.

## ADR-004 - Postgres + Qdrant

Postgres e a fonte transacional. Qdrant e o indice vetorial principal por performance, filtros e tuning dedicado. O backend usa a interface `VectorStore` para permitir troca futura para pgvector/LanceDB.

## ADR-005 - LangGraph/LangChain para agentes

LangGraph/LangChain entram para fluxos agentic com estado, checkpoint humano e multiplos passos. A aplicacao ainda mantem politicas, permissoes e auditoria em codigo proprio.

## ADR-006 - Seguranca mobile

O acesso remoto padrao sera por Tailscale/WireGuard. Portas HTTPS publicas ficam fora do MVP inicial para reduzir risco.

## ADR-007 - Modelos locais

Chat fica restrito a OpenAI, Anthropic e Google. Modelos locais podem ser usados para embeddings, reranking, OCR auxiliar e outras tarefas de infraestrutura que reduzam custo.
