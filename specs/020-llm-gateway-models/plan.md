# Plano de implementação: LLM Gateway e Registry de Modelos

**Pasta da spec**: `specs/020-llm-gateway-models/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Doc-only. Descreve o contrato atual e registra dívida (DT-001..003).

## Resumo

`LLMGateway` (`gateway.py`) é a fachada que roteia para providers (`providers.py`) conforme o modelo resolvido por `ModelRegistry`. Pricing vem de `model_pricing.json`/`pricing.py`. Configuração exposta por `routes/models.py` e `settings.py`.

## Contexto técnico

- **Linguagem/Versão**: Python 3.11 · **Storage**: segredos em storage local protegido (`security/secrets.py`)
- **Tipo de projeto**: backend FastAPI · **Testes**: pytest

## Constitution Check

- [x] P2 Stack invariável (chat só OpenAI/Anthropic/Google — ADR-007).
- [x] P3 Preservar arquitetura (doc-only).
- [x] P9 Qualidade/PT-BR.

Sem violações.

## Estrutura

```text
backend/app/llm_gateway/   # gateway, providers, model_registry, pricing, model_pricing.json, exceptions
backend/app/api/routes/    # models.py, settings.py
```

## Estratégia / Ondas

1. Esta onda: spec + dívida.
2. Futuro: dividir `providers.py` por provider; consolidar pricing; testes de contrato.

## Validação

- Doc-only: cross-links resolvem. Futuro: `scripts/quality.ps1` verde + testes de contrato por provider.

## Riscos e trade-offs

- Dividir providers pode alterar imports — mitigar com fachada estável em `gateway.py`.

## Rastreamento de complexidade

Sem violações.
