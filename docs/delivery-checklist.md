# Checklist obrigatório de entrega

Este checklist deve acompanhar toda implementação relevante enviada ao dono do produto, seja no resumo final, no PR ou no handoff.

## Regras antes de alterar

- Confirmar com o dono do produto o nome da branch.
- Confirmar com o dono do produto a mensagem de commit em formato semântico.
- Confirmar qual spec/task cobre a mudança ou criar/atualizar uma spec quando o escopo exceder ajuste pontual.

## Itens obrigatórios em toda entrega

- [ ] Branch e commit semântico usados.
- [ ] Spec/task relacionada.
- [ ] Resumo objetivo do que mudou na plataforma.
- [ ] Arquivos e bounded contexts tocados.
- [ ] Impacto de negócio ou regra de domínio alterada.
- [ ] Impacto em contrato de API, tipos compartilhados ou payloads.
- [ ] Impacto em storage, migração, dados locais, Qdrant ou Valkey.
- [ ] Impacto em segurança, privacidade, permissões, custo ou auditoria.
- [ ] Documentação e specs atualizadas quando comportamento, contrato ou fluxo mudou.
- [ ] Validações automatizadas executadas, com comandos e resultado.
- [ ] Testes manuais, visuais ou e2e executados, com evidência quando aplicável.
- [ ] Riscos, trade-offs, rollback e pendências fora do escopo.

## Itens condicionais por contexto

### Backend/FastAPI

- [ ] Rotas, contratos Pydantic e códigos de erro revisados.
- [ ] Testes em `backend/tests` adicionados ou atualizados.
- [ ] Impacto nos modos `postgres`, `json` e `auto` explicitado.

### Frontend/React

- [ ] Estados de tela, loading, erro e vazio revisados.
- [ ] Tipos de API e consumo alinhados.
- [ ] Acessibilidade e responsividade preservadas.

### RAG, arquivos e dados sensíveis

- [ ] Upload, parsing, chunking, indexação, bases e recuperação diferenciados.
- [ ] Classificação sensível manual e heurística considerada.
- [ ] Envio a provedores externos, quando houver, explicitado na entrega.

### Agentes, tools e sandbox

- [ ] Ação classificada como adição, alteração ou deleção.
- [ ] Alteração/deleção exige aprovação humana antes de executar.
- [ ] Diretório isolado por projeto, timeout, limites e rollback descritos.
- [ ] Tool calls auditáveis.

### 3D, Blender e Fusion

- [ ] Planner, policy, aprovação, snapshot e rollback preservados.
- [ ] Diferença entre mock, adapter ausente, execução real e erro mantida clara.
- [ ] Printability, exports e artifacts considerados.

### Mobile, desktop e pareamento

- [ ] QR local e cliente mobile sem autenticação de usuário no MVP considerados.
- [ ] Cache offline completo considerado.
- [ ] Impacto em Tauri/Capacitor e conectividade local explicitado.

### Artifacts/export

- [ ] Markdown, código, JSON, HTML, Mermaid, PDF, DOCX e PPTX considerados quando o fluxo envolver exportação.
- [ ] Versionamento e rastreabilidade dos artifacts considerados.

### Observabilidade e qualidade

- [ ] Eventos de LLM, custo, tool calls, documentos, export/delete, pairing e indexação avaliados.
- [ ] Golden paths relevantes definidos ou executados.
