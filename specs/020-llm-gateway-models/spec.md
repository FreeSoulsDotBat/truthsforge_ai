# Especificação: LLM Gateway e Registry de Modelos

**Pasta da spec**: `specs/020-llm-gateway-models/` | **Criada em**: 2026-05-22 | **Status**: Rascunho

**Entrada**: Cobrir com spec o gateway multi-provider e o registry de modelos/custos, hoje sem spec dedicada.

> Onda 2 do refactor SDD. Documenta o contrato do gateway e a dívida de organização de providers/pricing.

## Cenários de usuário e testes

### História 1 — Resposta via provider configurado (Prioridade: P1) 🎯 MVP

O sistema fala com OpenAI/Anthropic/Google conforme o modelo do agente, com fallback dev quando permitido.

**Teste independente**: configurar um provider e enviar chat; observar resposta real; sem provider, observar fallback/erro explícito.

**Cenários de aceitação**:

1. **Dado** um agente com modelo configurado, **Quando** o chat chama o gateway, **Então** o sistema roteia para o provider correto (`LLMGateway.stream_chat`).
2. **Dado** modo imagem/Deep Research, **Quando** solicitado, **Então** o gateway usa o caminho correspondente (`generate_image`/`deep_research`).

### História 2 — Registry editável de modelos e custos (Prioridade: P1)

O sistema mantém registry de modelos, capacidades e pricing, selecionável por agente/modo.

**Cenários de aceitação**:

1. **Dado** um agente, **Quando** o runtime resolve o modelo, **Então** usa `ModelRegistry.get_for_agent`; para imagem/Deep Research usa o modelo apropriado.

### Casos de borda

- Modelo sem pricing num modo que exige (Deep Research, imagem, reasoning) → bloqueio no cost governor (ver `060-cost-audit-governance`).
- Chat restrito a OpenAI/Anthropic/Google (ADR-007); modelos locais só para infra (embeddings/rerank/OCR).

## Requisitos

### Requisitos funcionais

- **RF-001**: QUANDO o runtime precisar de um modelo, O SISTEMA DEVE resolvê-lo via `ModelRegistry` (`backend/app/llm_gateway/model_registry.py`).
- **RF-002**: QUANDO houver chamada de chat, O SISTEMA DEVE rotear pelo `LLMGateway` para o provider configurado (`backend/app/llm_gateway/gateway.py`, `providers.py`).
- **RF-003**: O SISTEMA DEVE expor configuração de providers/modelos via `api/routes/models.py` e `api/routes/settings.py`.
- **RF-004**: QUANDO o provider/modelo não estiver configurado, O SISTEMA DEVE falhar de forma explícita (`llm_gateway/exceptions.py`) ou cair no fallback dev quando permitido.
- **RF-005**: O chat DEVE ficar restrito a OpenAI/Anthropic/Google (ADR-007).

### Requisitos não funcionais

- **RNF-001**: Segredos/chaves DEVEM ficar no backend/storage local protegido, nunca no browser (P1/P9; `security/secrets.py`).
- **RNF-002**: Pricing DEVE permitir estimativa de custo determinística pelo cost governor.

## Critérios de sucesso

- **CS-001**: Todo modo que exige pricing recusa execução quando o pricing não está configurado.
- **CS-002**: Troca de modelo por agente não exige mudança de código (registry editável).

## Premissas

- `model_pricing.json` é a fonte inicial de pricing; o registry pode sobrepor.

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `backend/app/llm_gateway/gateway.py`, `providers.py`, `model_registry.py`, `pricing.py`, `model_pricing.json`, `exceptions.py`; `backend/app/api/routes/models.py`, `settings.py`; `backend/app/security/secrets.py`
- Docs: `docs/decisions.md` (ADR-002, ADR-007), `docs/api.md`, `docs/deep-research.md`, `docs/image-generation.md`, `docs/reasoning-summary.md`
- Testes: `backend/tests/test_runtime_routes.py`
- Specs relacionadas: `specs/010-chat-orchestration/`, `specs/060-cost-audit-governance/`

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: `backend/app/llm_gateway/providers.py` (654 linhas) concentra OpenAI/Anthropic/Google num único arquivo. Direção: um módulo por provider sob `llm_gateway/providers/`. Esforço: M.
- **DT-002**: Pricing estático em `model_pricing.json` vs registry editável — risco de divergência. Direção: fonte única de pricing com IDs/custos reais (ver `docs/mvp-readiness.md`). Esforço: M.
- **DT-003**: Ausência de testes de contrato por provider. Direção: testes de contrato (stream/imagem/deep research) por provider. Esforço: M.

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Dívida documentada (não executada)
