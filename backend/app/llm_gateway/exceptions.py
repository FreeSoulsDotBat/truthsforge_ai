"""Hierarquia tipada de exceções do LLM gateway.

Antes desta refatoração, ``planner_service`` envolvia chamadas ao LLM em
``except Exception`` genérico, perdendo a distinção entre falhas de
autenticação (raiz do bug original — ``audit-cost-model`` inexistente),
timeouts retentáveis e respostas inválidas. O ``ModelingTracer`` mapeia
cada subclasse para um ``event_type`` distinto na trilha de observabilidade
(``planner.llm_timeout`` vs ``planner.llm_auth_error`` etc.), facilitando
diagnóstico e retry inteligente.

Providers ainda lançam exceções genéricas das SDKs (``openai.AuthenticationError``,
``anthropic.APIError`` etc.); os call sites devem traduzir para esta
hierarquia próximo ao boundary. Ver ``planner_service._build_plan`` para
o ponto de tradução adotado nesta iteração.
"""

from __future__ import annotations


class LLMProviderError(Exception):
    """Base para falhas vindas do gateway LLM.

    O atributo ``retryable`` orienta o caller sobre se vale a pena tentar
    novamente sem intervenção humana. O atributo ``provider_error_code``
    captura o código original do provider quando disponível (útil para
    logs estruturados sem precisar serializar a exceção inteira).
    """

    retryable: bool = False
    provider_error_code: str | None = None

    def __init__(
        self,
        message: str,
        *,
        provider_error_code: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        if provider_error_code is not None:
            self.provider_error_code = provider_error_code
        if retryable is not None:
            self.retryable = retryable


class LLMAuthError(LLMProviderError):
    """API key ausente, inválida ou sem permissão para o modelo solicitado.

    Foi este o caso da raiz do bug original: o ``provider_model_id``
    ``audit-cost-model`` não existia na OpenAI, fazendo a chamada falhar
    com 401/404 sem o usuário ver. Mapeado para o trace event
    ``planner.llm_auth_error`` com ``level=error``.
    """

    retryable = False


class LLMTimeoutError(LLMProviderError):
    """Provider não respondeu no tempo limite. Retry costuma resolver."""

    retryable = True


class LLMInvalidResponseError(LLMProviderError):
    """Provider respondeu mas o conteúdo não passa na validação Pydantic do plano.

    Indica drift do contrato de saída do LLM (ex: campo obrigatório
    ausente, JSON malformado). Não é retryable sem mudar o prompt.
    """

    retryable = False


class LLMRateLimitError(LLMProviderError):
    """Provider sinalizou rate limit (429). Retry com backoff exponencial."""

    retryable = True


def classify_provider_exception(exc: BaseException) -> LLMProviderError:
    """Best-effort: traduz exceções genéricas dos SDKs para a hierarquia tipada.

    Inspeciona o nome da classe e a mensagem para detectar autenticação,
    timeout, rate limit. Em último caso retorna ``LLMProviderError`` cru
    preservando a mensagem original. Não importa as SDKs diretamente para
    evitar acoplamento e quebrar em ambientes onde algum provider não
    está instalado.
    """

    name = exc.__class__.__name__.lower()
    message = str(exc) or exc.__class__.__name__

    if any(token in name for token in ("auth", "permission", "forbidden")):
        return LLMAuthError(message)
    if "timeout" in name or "timed out" in message.lower():
        return LLMTimeoutError(message)
    if "rate" in name and "limit" in name:
        return LLMRateLimitError(message)
    if "ratelimit" in name:
        return LLMRateLimitError(message)
    if "validation" in name or "pydantic" in name:
        return LLMInvalidResponseError(message)
    return LLMProviderError(message)


__all__ = [
    "LLMAuthError",
    "LLMInvalidResponseError",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "classify_provider_exception",
]
