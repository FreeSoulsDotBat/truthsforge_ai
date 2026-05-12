# Plano de implementacao

Este plano organiza a correcao das lacunas arquiteturais identificadas nos documentos de arquitetura e no codigo atual. A ordem prioriza estabilidade, seguranca e utilidade do MVP antes de autonomia avançada.

## Fase 0 - Baseline e decisoes tecnicas

Objetivo: deixar a base segura para evoluir sem quebrar o MVP.

- Rodar baseline de qualidade: backend format/lint/test, frontend format/lint/unit/typecheck/build.
- Consolidar a decisao de storage: Postgres + Qdrant como producao local; JSON store apenas fallback dev/teste.
- Revisar configuracao local, scripts e documentacao para remover ambiguidades de arquitetura.
- Manter PRs pequenos e auditaveis.

Status inicial verificado nesta fase:

- `python -m ruff format --check backend/app backend/tests`
- `python -m ruff check backend/app backend/tests`
- `cd backend && python -m pytest -q`
- `pnpm --filter @truths-forge/web format:check`
- `pnpm --filter @truths-forge/web lint`
- `pnpm --filter @truths-forge/web test:unit`
- `pnpm --filter @truths-forge/web typecheck`
- `pnpm --filter @truths-forge/web build`

## Fase 1 - Chat, historico, custo e auditoria

Objetivo: estabilizar o nucleo do produto.

- Fortalecer mensagens de erro por provider/modelo.
- Melhorar preflight de custo antes de chamadas caras.
- Enriquecer auditoria com provider, modelo, tokens, custo, modo, anexos e contexto usados.
- Confirmar persistencia de chats, sessoes, anexos e projetos.
- Preparar metadados de arquivamento para retencao futura.

## Fase 2 - RAG real e pipeline de documentos

Objetivo: substituir o RAG prototipo por busca util em bases grandes.

- Trocar embedding deterministico por embeddings locais reais, mantendo fallback dev.
- Implementar parsing real para PDF, DOCX, Markdown, TXT, CSV e HTML.
- Implementar OCR PT-BR opcional para imagens e PDFs escaneados.
- Melhorar fila de indexacao com retry, status e logs visiveis.
- Implementar busca hibrida minima: vetorial + filtros por projeto/base/tags/tipo/data.
- Garantir decisao explicita do usuario para indexar/anexar documentos sensiveis.

## Fase 3 - Permissoes e ferramentas

Objetivo: liberar ferramentas perigosas apenas com sandbox, aprovacao e auditoria.

- Implementar runtime real de tools por allowlist.
- Criar fluxo end-to-end de aprovacao para `python.run`, `filesystem.write` e futuras tools.
- Criar painel de permissoes por agente: `allow`, `ask`, `deny`.
- Sandboxing para Python/JS antes de permitir alteracoes no PC.
- Registrar logs por tool call e rollback quando aplicavel.

## Fase 4 - JUDITE e agentes reais

Objetivo: transformar JUDITE de orquestrador simples em coordenadora operacional.

- Criar memoria da JUDITE: usuario, projetos, preferencias, decisoes e contexto tecnico.
- Implementar selecao explicita de agentes/tools com justificativa e policy.
- Implementar memoria propria por agente.
- Permitir agente chamar agente somente quando a permissao permitir.
- Usar LangGraph onde houver workflow real com estado/checkpoints, nao como camada decorativa.

## Fase 5 - Modelagem 3D/MCP

Objetivo: consolidar o modulo mais alinhado a arquitetura e remover falsas promessas.

- Manter Blender como POC real principal.
- Melhorar UI para diferenciar mock, adapter ausente, execucao real e erro.
- Melhorar validacoes de malha/printability.
- Evoluir Fusion 360 apenas quando o add-in/adapter real estiver minimamente operacional.
- Registrar versoes de modelos e exports como artifacts.

## Fase 6 - Mobile, pairing e seguranca

Objetivo: permitir Android como cliente seguro do backend desktop.

- Implementar indicador online/offline real.
- Criar pairing por QR/codigo no desktop.
- Emitir JWT por dispositivo pareado.
- Priorizar Tailscale/WireGuard; HTTPS publico fica fora do caminho padrao inicial.
- Implementar cache local somente leitura para historico basico quando desktop estiver offline.

## Fase 7 - Artifacts/canvas/export

Objetivo: entregar a area produtiva/criativa do MVP.

- Canvas para Markdown, codigo, JSON, HTML preview e Mermaid.
- Export inicial: Markdown, HTML, JSON e PDF.
- Depois: DOCX/PPTX.
- Versionamento simples de artifacts.

## Fase 8 - Retencao, compactacao e performance

Objetivo: preparar o app para milhares de chats e muitos arquivos.

- Politica de historico ativo de 1 ano.
- Fluxo perguntando antes de arquivar/remover detalhes antigos.
- Sumarizacao semantica de chats antigos.
- Normalizar tabelas criticas no Postgres se `JSONB` virar gargalo.
- Criar indices para mensagens, documentos, auditoria, tags e projetos.
