"""Tracer e logging estruturado do módulo de modelagem 3D.

Provê ``ModelingTracer`` para emitir eventos estruturados ao longo do
pipeline (planner → executor → MCP → Fusion/Blender), correlacionados por
um ``trace_id`` sortable propagado via ``contextvars``. O mesmo trace_id
é injetado automaticamente em todos os ``logger.info/error/...`` do
namespace ``app.modeling.*`` via ``TraceContextFilter``, e logs do
módulo são serializados como JSON via ``JsonFormatter`` (sem afetar logs
do resto do app).

Decisões de design (registradas inline para não duplicar com o plano):

- **ULID-like trace_id**: timestamp millis + 8 bytes random, hex. Sortable
  por timestamp para ordenação trivial em queries. Não usa ``uuid4`` para
  não confundir com IDs de domínio do app.
- **Batch buffer**: eventos são acumulados em memória e flushed em spans
  fechados ou a cada N eventos. Evita N+1 INSERTs em loops do executor.
- **Truncate por tamanho**: payloads > 50KB são truncados com marker
  ``_truncated: true``. Protege o JSONB do Postgres e a memória do
  DevStore (que carrega o arquivo inteiro em RAM).
- **Best-effort em fail**: erros do próprio tracer (ex: DB indisponível
  na hora do flush) são engolidos com log e nunca quebram o fluxo do
  usuário. Observabilidade não pode ser fonte de incidente.
"""

from __future__ import annotations

import contextvars
import json
import logging
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol

from app.core.config import settings
from app.core.contracts import (
    MODELING_TRACE_PAYLOAD_LIMIT_BYTES,
    ModelingTraceEvent,
    ModelingTraceLevel,
    ModelingTraceSource,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context propagation
# ---------------------------------------------------------------------------

# Variáveis contextuais bindadas no início de cada trace e lidas pelo filter
# de logging + pelo tracer. Funciona em sync e async (FastAPI propaga
# automaticamente em request handlers e tasks).
_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "modeling_trace_id", default=None
)
_plan_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "modeling_plan_id", default=None
)
_session_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "modeling_session_id", default=None
)
_project_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "modeling_project_id", default=None
)
_sequence_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    "modeling_trace_sequence", default=0
)


def current_trace_id() -> str | None:
    """Retorna o trace_id ativo no contexto atual, ou ``None`` se não houver."""

    return _trace_id_var.get()


def current_plan_id() -> str | None:
    return _plan_id_var.get()


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def generate_trace_id() -> str:
    """Gera um ID sortable lexicograficamente: ``<48bit_ms_hex>-<64bit_rand_hex>``.

    Não é ULID estrito (não usa Crockford base32) mas tem a mesma
    propriedade essencial: ordenação alfabética == ordenação temporal,
    facilitando debug. Prefixado com ``mt`` para distinguir de outros
    IDs do app em logs visuais.
    """

    ts_ms = int(time.time() * 1000)
    rand = secrets.token_hex(8)
    return f"mt_{ts_ms:012x}_{rand}"


def generate_event_id() -> str:
    """ID de evento individual. Não precisa ser sortable globalmente."""

    return f"mte_{secrets.token_hex(8)}"


# ---------------------------------------------------------------------------
# Payload sizing
# ---------------------------------------------------------------------------


def _truncate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Trunca payloads JSON que excedam ``MODELING_TRACE_PAYLOAD_LIMIT_BYTES``.

    Estratégia: serializa o payload, mede tamanho, e se exceder substitui
    pelo dict ``{"_truncated": True, "_original_size_bytes": N, "preview": "..."}``
    com um preview dos primeiros caracteres da serialização original.
    Preserva o nome dos top-level keys originais como ``_keys`` para
    facilitar debug.
    """

    try:
        encoded = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return {"_truncated": True, "_reason": "non_serializable", "_keys": list(payload.keys())}

    size = len(encoded.encode("utf-8"))
    if size <= MODELING_TRACE_PAYLOAD_LIMIT_BYTES:
        return payload

    preview = encoded[: MODELING_TRACE_PAYLOAD_LIMIT_BYTES // 4]
    return {
        "_truncated": True,
        "_original_size_bytes": size,
        "_keys": list(payload.keys()),
        "preview": preview,
    }


# ---------------------------------------------------------------------------
# Store protocol
# ---------------------------------------------------------------------------


class TraceEventStore(Protocol):
    """Interface mínima que ``ModelingTracer`` espera de uma store.

    Implementada por ``PostgresStore`` e ``DevStore`` (ver task #3).
    Mantida como protocol em vez de import direto para não criar ciclo
    de dependência e permitir substituição em testes.
    """

    def record_trace_events_bulk(self, events: list[ModelingTraceEvent]) -> None: ...


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


@dataclass
class _TraceBuffer:
    """Buffer in-memory por trace. Flushed em close ou ao atingir batch size."""

    events: list[ModelingTraceEvent] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)


class ModelingTracer:
    """Tracer central do módulo de modelagem 3D.

    Uso típico::

        tracer.start_trace(session_id=..., project_id=..., plan_id=...)
        tracer.record(
            "planner.model_resolved", source="backend", payload={"model_id": "openai/default-chat"}
        )
        with tracer.record_span(
            "planner.llm_request", source="backend", payload={"model_id": ...}
        ) as span:
            response = await llm.call(...)
            span.attach({"tokens": response.tokens})
        # ... ao final do request, o buffer é flushed automaticamente.

    Notas:
    - Métodos são síncronos no caller; o flush para a store também é
      síncrono (rápido — bulk insert). Se a store estiver lenta isso
      vira gargalo; aceitável nesta iteração dada a escala (≈50 eventos
      por trace).
    - O ``record_span`` mede ``duration_ms`` e emite um evento ``<name>``
      no início (level=debug) e um ``<name>.completed`` no fim com
      a duração. Em caso de exceção emite ``<name>.failed`` com
      ``exc_info`` e propaga a exceção.
    """

    DEFAULT_BATCH_SIZE = 25
    # PR#28 review (issue 2): bounded capacity defensiva. O design espera
    # que ``close_trace()`` seja chamado no fim de cada request (agora wired
    # em chat.py finally block), mas se algum caller esquecer, o buffer
    # ficaria preso. Quando atingimos o limite, eviccionamos o trace mais
    # antigo (flush + remove) antes de criar um novo.
    DEFAULT_MAX_BUFFERS = 1000

    def __init__(
        self,
        store: TraceEventStore | None,
        *,
        batch_size: int | None = None,
        max_buffers: int | None = None,
    ) -> None:
        self._store = store
        self._batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        self._max_buffers = max_buffers or self.DEFAULT_MAX_BUFFERS
        # Buffers por trace_id. dict normal (insertion-ordered no Py3.7+)
        # para conseguir evictar FIFO se atingirmos o cap.
        self._buffers: dict[str, _TraceBuffer] = {}
        self._buffers_lock = Lock()

    # ------------------------------------------------------------------ lifecycle

    def start_trace(
        self,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
        plan_id: str | None = None,
        existing_trace_id: str | None = None,
    ) -> str:
        """Inicia um novo trace e bind o ``trace_id`` no contexto atual.

        Se ``existing_trace_id`` é passado, reusa-o (caso de continuação
        de trace iniciado em outro nível). Senão gera novo via
        ``generate_trace_id``. Retorna o trace_id para uso explícito.

        Sempre emite um evento ``trace.started`` (level=info) com o
        snapshot dos identificadores anchorados.
        """

        trace_id = existing_trace_id or generate_trace_id()
        _trace_id_var.set(trace_id)
        _plan_id_var.set(plan_id)
        _session_id_var.set(session_id)
        _project_id_var.set(project_id)
        _sequence_var.set(0)

        self.record(
            "trace.started",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.info,
            message="Modeling trace started",
            payload={
                "session_id": session_id,
                "project_id": project_id,
                "plan_id": plan_id,
            },
        )
        return trace_id

    def bind_plan(self, plan_id: str) -> None:
        """Atualiza o plan_id contextual depois que o plano é criado.

        Útil quando ``start_trace`` é chamado antes do plano ter ID,
        permitindo que eventos subsequentes carreguem o plan_id no
        registro mesmo sem o caller passar explicitamente.

        Também faz **backfill** dos eventos já buffered deste trace que
        ainda estão sem plan_id (ex.: spans do planner — ``model_resolved``,
        ``llm_request`` — gravados ANTES do plano existir). Sem isto eles
        ficam com ``plan_id=None`` e o diagnóstico-por-plano não os acha,
        deixando o trace "vazio" mesmo tendo eventos. O buffer só dá flush
        em ``batch_size`` (25) ou no ``close``, então no propose típico
        (≈5–8 eventos) eles ainda estão em memória aqui.
        """

        _plan_id_var.set(plan_id)
        tid = current_trace_id()
        if tid is None:
            return
        with self._buffers_lock:
            buffer = self._buffers.get(tid)
        if buffer is None:
            return
        with buffer.lock:
            for index, event in enumerate(buffer.events):
                if event.plan_id is None:
                    buffer.events[index] = event.model_copy(update={"plan_id": plan_id})

    def flush(self, trace_id: str | None = None) -> None:
        """Persiste eventos buffered para a store.

        Se ``trace_id`` é passado, flusha apenas aquele trace; senão
        flusha todos os buffers conhecidos. Best-effort: erros são
        logados mas não propagados.
        """

        if trace_id:
            targets = [trace_id]
        else:
            with self._buffers_lock:
                targets = list(self._buffers.keys())
        for tid in targets:
            with self._buffers_lock:
                buffer = self._buffers.get(tid)
            if buffer is None:
                continue
            with buffer.lock:
                pending = buffer.events
                buffer.events = []
            if not pending or self._store is None:
                continue
            try:
                self._store.record_trace_events_bulk(pending)
            except Exception:  # noqa: BLE001 - observability never crashes flow
                logger.exception(
                    "Falha ao persistir %d trace events (trace_id=%s); descartando.",
                    len(pending),
                    tid,
                )

    def close_trace(self, trace_id: str | None = None) -> None:
        """Flush + remove o buffer. Chame ao final de um request handler."""

        tid = trace_id or current_trace_id()
        if tid is None:
            return
        self.flush(tid)
        with self._buffers_lock:
            self._buffers.pop(tid, None)

    # ------------------------------------------------------------------ recording

    def record(
        self,
        event_type: str,
        *,
        source: ModelingTraceSource | str = ModelingTraceSource.backend,
        level: ModelingTraceLevel | str = ModelingTraceLevel.info,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        plan_id: str | None = None,
        trace_id: str | None = None,
    ) -> ModelingTraceEvent | None:
        """Registra um evento. Retorna o objeto persistido (útil pra testes).

        Se ``modeling_observability_enabled`` é False, vira no-op.
        Se não há trace_id no contexto e nenhum foi passado, retorna None
        silenciosamente (evita emitir órfãos em chamadas pré-start_trace).
        """

        if not settings.modeling_observability_enabled:
            return None

        tid = trace_id or current_trace_id()
        if tid is None:
            return None

        if isinstance(source, str):
            source = ModelingTraceSource(source)
        if isinstance(level, str):
            level = ModelingTraceLevel(level)

        sequence = _sequence_var.get() + 1
        _sequence_var.set(sequence)

        event = ModelingTraceEvent(
            id=generate_event_id(),
            trace_id=tid,
            plan_id=plan_id or current_plan_id(),
            session_id=_session_id_var.get(),
            project_id=_project_id_var.get(),
            event_type=event_type,
            source=source,
            level=level,
            message=message,
            payload=_truncate_payload(payload or {}),
            duration_ms=duration_ms,
            sequence=sequence,
            created_at=datetime.now(UTC),
        )

        # Espelha no logger Python — TraceContextFilter injeta trace_id
        # e JsonFormatter serializa. Eleva o nível conforme severity.
        log_method = {
            ModelingTraceLevel.debug: logger.debug,
            ModelingTraceLevel.info: logger.info,
            ModelingTraceLevel.warn: logger.warning,
            ModelingTraceLevel.error: logger.error,
        }[level]
        log_method(
            "modeling.trace event_type=%s message=%s",
            event_type,
            message or "",
            extra={
                "trace_event_type": event_type,
                "trace_source": source.value,
                "trace_level": level.value,
                "trace_payload": event.payload,
                "trace_duration_ms": duration_ms,
            },
        )

        # Bufferiza e flush ao atingir batch size.
        buffer = self._get_buffer(tid)
        with buffer.lock:
            buffer.events.append(event)
            if len(buffer.events) >= self._batch_size:
                pending = buffer.events
                buffer.events = []
            else:
                pending = []
        if pending and self._store is not None:
            try:
                self._store.record_trace_events_bulk(pending)
            except Exception:  # noqa: BLE001 - observability never crashes flow
                logger.exception("Falha ao flush trace events em batch.")

        return event

    @contextmanager
    def record_span(
        self,
        event_type: str,
        *,
        source: ModelingTraceSource | str = ModelingTraceSource.backend,
        level: ModelingTraceLevel | str = ModelingTraceLevel.info,
        payload: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> Iterator[_SpanContext]:
        """Mede a duração de uma operação. Emite ``<event_type>`` no start (debug)
        e ``<event_type>.completed`` / ``<event_type>.failed`` no fim.

        Uso::

            with tracer.record_span("planner.llm_request", payload={...}) as span:
                resp = call_llm()
                span.attach({"tokens": resp.tokens})
        """

        start = time.perf_counter()
        span_payload = dict(payload or {})
        self.record(
            event_type,
            source=source,
            level=ModelingTraceLevel.debug,
            payload=dict(span_payload),
            message=message,
        )
        ctx = _SpanContext(payload=span_payload)
        try:
            yield ctx
        except BaseException as exc:
            # PR#28 review (issue 9): captura BaseException ao inves de
            # Exception para tambem fechar spans em CancelledError
            # (asyncio.CancelledError em Python 3.9+ herda de BaseException,
            # nao Exception). Sem isso, spans cancelados ficavam orfaos
            # (apenas o start event, sem .completed nem .failed), poluindo
            # o trace e dificultando o diagnostico.
            duration_ms = int((time.perf_counter() - start) * 1000)
            is_cancel = exc.__class__.__name__ in ("CancelledError",)
            self.record(
                f"{event_type}.cancelled" if is_cancel else f"{event_type}.failed",
                source=source,
                level=ModelingTraceLevel.warn if is_cancel else ModelingTraceLevel.error,
                payload={**ctx.payload, "exception": exc.__class__.__name__, "error": str(exc)},
                duration_ms=duration_ms,
            )
            raise
        else:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.record(
                f"{event_type}.completed",
                source=source,
                level=level,
                payload=ctx.payload,
                duration_ms=duration_ms,
            )

    def ingest_external_events(
        self,
        raw_events: list[dict[str, Any]],
        *,
        default_source: ModelingTraceSource = ModelingTraceSource.fusion,
    ) -> None:
        """Drena uma lista de eventos vinda de um adapter externo (Fusion/Blender).

        O addin/runner acumula eventos em ``trace_events: []`` no response
        do JSON-RPC e o backend chama este método para incorporá-los ao
        buffer do trace ativo. Cada item é tratado como dict cru — campos
        ausentes ganham defaults razoáveis.
        """

        for raw in raw_events or []:
            try:
                event_type = str(raw.get("event_type", "external.unknown"))
                source = ModelingTraceSource(raw.get("source", default_source.value))
                level = ModelingTraceLevel(raw.get("level", "info"))
                self.record(
                    event_type,
                    source=source,
                    level=level,
                    message=raw.get("message"),
                    payload=raw.get("payload") or {},
                    duration_ms=raw.get("duration_ms"),
                )
            except Exception:  # noqa: BLE001 - tolerate malformed adapter events
                logger.exception("Evento externo malformado descartado: %r", raw)

    # ------------------------------------------------------------------ helpers

    def _get_buffer(self, trace_id: str) -> _TraceBuffer:
        evicted: tuple[str, list[ModelingTraceEvent]] | None = None
        with self._buffers_lock:
            buffer = self._buffers.get(trace_id)
            if buffer is None:
                # PR#28 review (issue 2): evict FIFO se atingimos o cap.
                # Caller deveria chamar close_trace() ao fim de cada request,
                # mas se esquecer, isto evita leak ilimitado. O buffer e
                # removido sob lock, mas o flush acontece fora dele para nao
                # serializar todos os record() em I/O lento.
                if len(self._buffers) >= self._max_buffers:
                    oldest_tid = next(iter(self._buffers))
                    evicted = self._pop_buffer_events_locked(oldest_tid)
                buffer = _TraceBuffer()
                self._buffers[trace_id] = buffer
        if evicted is not None:
            self._flush_evicted_events(*evicted)
        return buffer

    def _pop_buffer_events_locked(
        self, trace_id: str
    ) -> tuple[str, list[ModelingTraceEvent]] | None:
        """Remove o buffer e extrai eventos. Caller MUST hold ``_buffers_lock``."""

        buffer = self._buffers.pop(trace_id, None)
        if buffer is None:
            return None
        with buffer.lock:
            pending = buffer.events
            buffer.events = []
        return trace_id, pending

    def _flush_evicted_events(self, trace_id: str, pending: list[ModelingTraceEvent]) -> None:
        """Persiste eventos evictados sem segurar ``_buffers_lock``."""

        if pending and self._store is not None:
            try:
                self._store.record_trace_events_bulk(pending)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Falha ao flush %d eventos antes de evictar buffer trace_id=%s",
                    len(pending),
                    trace_id,
                )


@dataclass
class _SpanContext:
    """Handle exposto ao corpo do ``record_span`` para anexar metadados."""

    payload: dict[str, Any]

    def attach(self, extra: dict[str, Any]) -> None:
        self.payload.update(extra)


# ---------------------------------------------------------------------------
# Logging integration
# ---------------------------------------------------------------------------


class TraceContextFilter(logging.Filter):
    """Injeta ``trace_id`` e ``plan_id`` do contexto em todo LogRecord.

    Não filtra nada — apenas decora. Aplicar ao logger ``app.modeling``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = current_trace_id()
        record.plan_id = current_plan_id()
        return True


class JsonFormatter(logging.Formatter):
    """Serializa LogRecord como JSON estável para consumo via ``docker logs``.

    Inclui apenas campos relevantes para correlação (não dump LogRecord
    inteiro). Campos custom registrados via ``extra=`` são surfaceados
    no top-level desde que prefixados com ``trace_``.
    """

    DEFAULT_KEYS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "trace_id",
        "plan_id",
        "message",
        "taskName",
        "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            payload["trace_id"] = trace_id
        plan_id = getattr(record, "plan_id", None)
        if plan_id:
            payload["plan_id"] = plan_id

        # Surface custom fields prefixed with ``trace_`` (set via extra=).
        for key, value in record.__dict__.items():
            if key in self.DEFAULT_KEYS:
                continue
            if key.startswith("trace_"):
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            # Fallback: never crash the logger.
            return json.dumps(
                {"ts": payload["ts"], "level": payload["level"], "message": payload["message"]}
            )


def configure_modeling_logging() -> None:
    """Aplica filter + formatter aos loggers ``app.modeling.*``.

    Chamado na inicialização do app. Idempotente — se o handler já está
    instalado, não duplica. Não toca em outros loggers do app (chat, rag,
    etc.) para evitar mudança disruptiva fora do escopo desta iteração.
    """

    target = logging.getLogger("app.modeling")
    if any(getattr(h, "_modeling_json", False) for h in target.handlers):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceContextFilter())
    handler._modeling_json = True  # type: ignore[attr-defined]
    target.addHandler(handler)
    target.propagate = False  # evita duplicação se root logger também tem handler


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_tracer_instance: ModelingTracer | None = None
_tracer_lock = Lock()


def get_tracer(store: TraceEventStore | None = None) -> ModelingTracer:
    """Retorna o tracer global. Lazy-init na primeira chamada.

    A store é injetada na primeira chamada e cached. Chamadas
    subsequentes ignoram o parâmetro ``store`` — para trocar (ex: em
    testes) use ``reset_tracer``.
    """

    global _tracer_instance
    with _tracer_lock:
        if _tracer_instance is None:
            _tracer_instance = ModelingTracer(store)
            configure_modeling_logging()
        return _tracer_instance


def reset_tracer() -> None:
    """Limpa o singleton (útil em testes)."""

    global _tracer_instance
    with _tracer_lock:
        _tracer_instance = None


__all__ = [
    "JsonFormatter",
    "ModelingTracer",
    "TraceContextFilter",
    "TraceEventStore",
    "configure_modeling_logging",
    "current_plan_id",
    "current_trace_id",
    "generate_event_id",
    "generate_trace_id",
    "get_tracer",
    "reset_tracer",
]
