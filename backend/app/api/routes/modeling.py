from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.contracts import (
    ModelingApprovalDecision,
    ModelingApprovalRequest,
    ModelingCapabilities,
    ModelingExecutionResult,
    ModelingModelVersion,
    ModelingPlan,
    ModelingPlanEdit,
    ModelingPrintabilityReport,
    ModelingPrintabilityRequest,
    ModelingSession,
    ModelingSessionStart,
    ModelingSnapshot,
    ModelingSnapshotCreate,
    ModelingSnapshotRestore,
    ModelingSnapshotRestoreResult,
    ModelingToolCall,
    ModelingTraceEvent,
    ModelingTraceEventCreate,
    ModelingTraceLevel,
    ModelingTraceSource,
)
from app.modeling.chat_orchestrator import get_modeling_orchestrator
from app.modeling.chat_state import InvalidModelingStageTransition
from app.modeling.observability import _truncate_payload, get_tracer
from app.modeling.service import (
    ModelingInvalidEditTool,
    ModelingPlanNotApprovable,
    ModelingPlanNotEditable,
    ModelingPlanNotExecutable,
    ModelingRollbackUnavailable,
    ensure_plan_approvable,
    ensure_plan_executable,
    get_modeling_service,
)
from app.storage.store import get_store

router = APIRouter()


def _service():
    store = get_store()
    required = [
        "list_modeling_plans",
        "upsert_modeling_plan",
        "get_modeling_plan",
        "get_modeling_plan_by_step",
        "upsert_modeling_session",
        "upsert_modeling_snapshot",
    ]
    if not all(hasattr(store, name) for name in required):
        raise HTTPException(status_code=501, detail="Módulo 3D não suportado neste backend.")
    return get_modeling_service(store)


@router.get("/capabilities", response_model=ModelingCapabilities)
def capabilities() -> ModelingCapabilities:
    return _service().capabilities()


@router.get("/sessions", response_model=list[ModelingSession])
def list_sessions() -> list[ModelingSession]:
    store = get_store()
    if not hasattr(store, "list_modeling_sessions"):
        return []
    return store.list_modeling_sessions()


@router.post("/sessions/start", response_model=ModelingSession)
def start_session(payload: ModelingSessionStart) -> ModelingSession:
    return _service().start_session(payload)


@router.get("/plans", response_model=list[ModelingPlan])
def list_plans() -> list[ModelingPlan]:
    store = get_store()
    if not hasattr(store, "list_modeling_plans"):
        return []
    return store.list_modeling_plans()


# NOTE: ``POST /plans`` was removed in Onda 2.11 (ADR-013). Plans are now
# created exclusively by the chat-first orchestrator via the
# ``3d.propose_plan`` / ``3d.propose_edit_plan`` agent tools. External
# callers that need a plan should drive the chat instead.


@router.get("/plans/{plan_id}", response_model=ModelingPlan)
def get_plan(plan_id: str) -> ModelingPlan:
    store = get_store()
    if not hasattr(store, "get_modeling_plan"):
        raise HTTPException(status_code=501, detail="Módulo 3D não suportado neste backend.")
    plan = store.get_modeling_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.")
    return plan


def _plan_or_404(plan_id: str) -> ModelingPlan:
    store = get_store()
    if not hasattr(store, "get_modeling_plan"):
        raise HTTPException(status_code=501, detail="Módulo 3D não suportado neste backend.")
    plan = store.get_modeling_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.")
    return plan


def _modeling_chat_for_plan(plan: ModelingPlan):
    """Sessão de chat 3D dona do plano, ou ``None`` (plano standalone).

    DT-006: quando o plano pertence a um chat 3D, aprovar/rejeitar/executar
    DEVEM passar pelo ``ModelingChatOrchestrator`` — é ele que transita o
    estágio do chat (planning→approved→executing→editing/failed) e emite os
    audits ``modeling.chat.*``. O caminho via ``ModelingService`` fica só
    para planos sem chat (criados por API direta).
    """

    conversation_id = plan.conversation_id
    if not conversation_id:
        return None
    store = get_store()
    if not hasattr(store, "get_chat_session"):
        return None
    try:
        session = store.get_chat_session(conversation_id)
    except Exception:  # pragma: no cover - defensive
        return None
    if session is None or not getattr(session, "is_modeling_3d", False):
        return None
    return session


@router.post("/plans/{plan_id}/approve", response_model=ModelingPlan)
def approve_plan(plan_id: str, payload: ModelingApprovalRequest) -> ModelingPlan:
    plan = _plan_or_404(plan_id)
    try:
        ensure_plan_approvable(plan, payload.decision)
    except ModelingPlanNotApprovable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    chat = _modeling_chat_for_plan(plan)
    if chat is None:
        try:
            return _service().approve_plan(plan_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Plano 3D não encontrado.") from exc
        except ModelingPlanNotApprovable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    orchestrator = get_modeling_orchestrator(get_store())
    try:
        if payload.decision == ModelingApprovalDecision.reject:
            _, result = orchestrator.reject(chat, plan_id, reason=payload.reason or "")
        else:
            _, result = orchestrator.approve_plan_only(chat, plan_id, payload=payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.") from exc
    except InvalidModelingStageTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


@router.patch("/plans/{plan_id}", response_model=ModelingPlan)
def edit_plan(plan_id: str, payload: ModelingPlanEdit) -> ModelingPlan:
    """P4: edita um plano antes da aprovação (etapas/rationale)."""

    try:
        return _service().edit_plan(plan_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.") from exc
    except ModelingPlanNotEditable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ModelingInvalidEditTool as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/execute", response_model=ModelingExecutionResult)
def execute_plan(plan_id: str) -> ModelingExecutionResult:
    plan = _plan_or_404(plan_id)
    try:
        ensure_plan_executable(plan)
    except ModelingPlanNotExecutable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    chat = _modeling_chat_for_plan(plan)
    if chat is None:
        try:
            return _service().execute_plan(plan_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Plano 3D não encontrado.") from exc
        except ModelingPlanNotExecutable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    # DT-006/DT-008: o orchestrator transita o estágio do chat
    # (approved→executing→editing em sucesso; →failed em falha) e emite os
    # audits ``modeling.chat.execution_*`` — a rota não duplica a state machine.
    orchestrator = get_modeling_orchestrator(get_store())
    try:
        _, _, execution = orchestrator.execute_plan(chat, plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.") from exc
    except InvalidModelingStageTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        # Gate ADR-013 do orchestrator (plano não aprovado).
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return execution


@router.post("/plans/{plan_id}/rollback", response_model=ModelingExecutionResult)
def rollback_plan(plan_id: str) -> ModelingExecutionResult:
    """T3.6: desfaz a última edição revertendo a timeline ao ponto pré-edição.

    ``plan_id`` é a edição a reverter; usa ``plan.rollback_marker`` (capturado
    antes da edição). NÃO mexe no ``modeling_plan_id`` do chat — o contexto de
    edição segue apontando para o plano com histórico completo, não para o
    plano de rollback (que só contém o passo de reversão).
    """

    try:
        return _service().rollback_last_edit(plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.") from exc
    except ModelingRollbackUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# NOTE: a antiga ``_advance_chat_to_editing_after_execute`` (state machine
# duplicada na rota — DT-006) foi removida: o avanço de estágio do chat após
# aprovar/rejeitar/executar é responsabilidade exclusiva do
# ``ModelingChatOrchestrator`` (ver ``_modeling_chat_for_plan``).


# NOTE: ``POST /steps/{step_id}/approve`` was removed in Onda 2.11
# (ADR-013). Approval is now global at the plan level via the chat card;
# high-risk steps in edit plans reopen approval inline through the same
# plan-level endpoint rather than per step.


@router.get("/snapshots", response_model=list[ModelingSnapshot])
def list_snapshots(
    plan_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
) -> list[ModelingSnapshot]:
    store = get_store()
    if not hasattr(store, "list_modeling_snapshots"):
        return []
    return store.list_modeling_snapshots(plan_id=plan_id, project_id=project_id)


@router.post("/snapshots", response_model=ModelingSnapshot)
def create_snapshot(payload: ModelingSnapshotCreate) -> ModelingSnapshot:
    return _service().create_snapshot(payload)


@router.get("/snapshots/{snapshot_id}", response_model=ModelingSnapshot)
def get_snapshot(snapshot_id: str) -> ModelingSnapshot:
    store = get_store()
    if not hasattr(store, "get_modeling_snapshot"):
        raise HTTPException(status_code=501, detail="Snapshot 3D não suportado neste backend.")
    snapshot = store.get_modeling_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot 3D não encontrado.")
    return snapshot


@router.post("/snapshots/{snapshot_id}/restore", response_model=ModelingSnapshotRestoreResult)
def restore_snapshot(
    snapshot_id: str, payload: ModelingSnapshotRestore | None = None
) -> ModelingSnapshotRestoreResult:
    try:
        return _service().restore_snapshot(snapshot_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Snapshot 3D não encontrado.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tool-calls", response_model=list[ModelingToolCall])
def list_tool_calls(
    plan_id: str | None = Query(default=None),
    step_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ModelingToolCall]:
    return _service().list_tool_calls(plan_id=plan_id, step_id=step_id, limit=limit)


@router.post("/validate/printability", response_model=ModelingPrintabilityReport)
def validate_printability(payload: ModelingPrintabilityRequest) -> ModelingPrintabilityReport:
    return _service().run_printability(payload)


@router.get("/printability-reports", response_model=list[ModelingPrintabilityReport])
def list_printability_reports(
    plan_id: str | None = Query(default=None),
    file_id: str | None = Query(default=None),
) -> list[ModelingPrintabilityReport]:
    return _service().list_printability_reports(plan_id=plan_id, file_id=file_id)


@router.get("/model-versions", response_model=list[ModelingModelVersion])
def list_model_versions(project_id: str | None = Query(default=None)) -> list[ModelingModelVersion]:
    store = get_store()
    if not hasattr(store, "list_modeling_model_versions"):
        return []
    return store.list_modeling_model_versions(project_id=project_id)


# ---------------------------------------------------------------------------
# Observabilidade do módulo 3D (ver app/modeling/observability.py)
# ---------------------------------------------------------------------------

# Rate-limiter simples em memória para o endpoint POST de eventos do cliente.
# Decisão: deixar in-process (não Redis) nesta iteração — tráfego previsto é
# baixo (UI events) e cada réplica de backend mantém seu próprio bucket. Se
# o app sair de single-replica em prod, mover para Valkey/Redis.
_CLIENT_TRACE_RATE_WINDOW_SECONDS = 60
_CLIENT_TRACE_RATE_MAX_EVENTS = 60
# Bucket por client_id (ip:trace_id) com timestamps em janela deslizante.
# Dict normal (NÃO defaultdict) para evitar criação implícita de chaves em
# leitura — todo acesso passa por _get_or_create_bucket que escreve
# intencionalmente. PR#28 review (issue 1) flagrou que defaultdict +
# nunca-deletar = leak de memória conforme novos trace_ids únicos chegam.
_client_trace_timestamps: dict[str, deque[float]] = {}
_client_trace_lock = Lock()


def _require_trace_store(store: Any) -> Any:
    """Garante que a store implementa CRUD de trace events.

    Backends que rodam só com DevStore antigo não suportam — devolve 501
    para o frontend mostrar erro amigável em vez de 500.
    """

    if (
        not hasattr(store, "list_trace_events")
        or not hasattr(store, "record_trace_events_bulk")
        or not hasattr(store, "get_max_trace_sequence")
    ):
        raise HTTPException(
            status_code=501,
            detail="Observabilidade 3D não suportada neste backend.",
        )
    return store


def _parse_csv_enum_query(raw: str | None, enum_cls: type, name: str) -> list | None:
    """Converte ``?level=warn,error`` em ``[ModelingTraceLevel.warn, ...]``.

    Inválidos viram 400 explícito — evita acidentes silenciosos onde o
    filtro é ignorado e o usuário vê todos os eventos sem entender.
    """

    if not raw:
        return None
    try:
        return [enum_cls(value.strip()) for value in raw.split(",") if value.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Valor inválido em filtro {name}: {exc}",
        ) from exc


@router.get("/plans/{plan_id}/trace", response_model=list[ModelingTraceEvent])
def list_plan_trace(
    plan_id: str,
    level: str | None = Query(default=None, description="CSV: debug,info,warn,error"),
    source: str | None = Query(default=None, description="CSV: ui,backend,mcp,fusion,blender"),
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[ModelingTraceEvent]:
    """Lista trace events de um plano, ordenados por (sequence, created_at) ASC.

    Usado pelo modal de diagnóstico do frontend após receber o evento SSE
    ``modeling_plan`` (que carrega o ``trace_id``). Suporta filtros por
    nível e fonte para reduzir payload em traces longos.
    """

    store = _require_trace_store(get_store())
    levels = _parse_csv_enum_query(level, ModelingTraceLevel, "level")
    sources = _parse_csv_enum_query(source, ModelingTraceSource, "source")
    return store.list_trace_events(plan_id=plan_id, levels=levels, sources=sources, limit=limit)


@router.get("/traces/{trace_id}", response_model=list[ModelingTraceEvent])
def list_trace_events_endpoint(
    trace_id: str,
    level: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[ModelingTraceEvent]:
    """Lista eventos por ``trace_id`` direto, sem precisar do plan_id.

    Útil quando o frontend só tem o trace_id (ex: vindo de um log do
    backend) e quer reconstruir a trilha.
    """

    store = _require_trace_store(get_store())
    levels = _parse_csv_enum_query(level, ModelingTraceLevel, "level")
    sources = _parse_csv_enum_query(source, ModelingTraceSource, "source")
    return store.list_trace_events(trace_id=trace_id, levels=levels, sources=sources, limit=limit)


@router.post("/traces/events", response_model=ModelingTraceEvent)
def record_client_trace_event(
    payload: ModelingTraceEventCreate, request: Request
) -> ModelingTraceEvent:
    """Aceita eventos vindos do cliente web (clicks, modal opens, retries).

    Segurança:
    - ``source`` é forçado para ``ui`` server-side; clientes não conseguem
      forjar eventos pretendendo vir de fusion/backend.
    - Rate limit: 60 eventos por minuto por IP. UI bugged em loop não
      derruba o backend.
    """

    store = _require_trace_store(get_store())
    client_id = (
        (request.client.host if request.client else "unknown") + ":" + (payload.trace_id or "")
    )

    # Token bucket por client_id em janela deslizante.
    # PR#28 review (issue 1): após pruning, removemos a chave se ficou vazia
    # E fazemos sweep periódico (a cada N requests) para chaves órfãs que
    # ficaram com timestamps todos expirados sem serem visitadas. Sem isso,
    # cada trace_id único viraria entrada permanente.
    now = time.time()
    cutoff = now - _CLIENT_TRACE_RATE_WINDOW_SECONDS
    with _client_trace_lock:
        bucket = _client_trace_timestamps.get(client_id)
        if bucket is None:
            bucket = deque()
            _client_trace_timestamps[client_id] = bucket
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= _CLIENT_TRACE_RATE_MAX_EVENTS:
            # Não removemos o bucket aqui — ele está ativo, só limitado.
            raise HTTPException(
                status_code=429,
                detail="Rate limit excedido para eventos de trace do cliente.",
            )
        bucket.append(now)
        # Sweep barato a cada chamada: se algum bucket OUTRO virou totalmente
        # obsoleto (todos timestamps abaixo do cutoff e nenhuma escrita
        # recente), remove. Custo O(N) onde N = #clients ativos no minuto,
        # tipicamente <50. Aceitável vs alternativas mais complexas.
        stale_keys = [
            k
            for k, b in _client_trace_timestamps.items()
            if k != client_id and (not b or b[-1] < cutoff)
        ]
        for k in stale_keys:
            del _client_trace_timestamps[k]

    # PR#28 review (issue 8): atribui sequence monotonico server-side
    # baseado no maior sequence ja existente para este trace_id. Sem isso,
    # todos os eventos do cliente ficavam com sequence=0 e desorganizavam
    # a timeline do modal. Best-effort: se o lookup falhar, mantem 0.
    # PR#28 follow-up: usar query dedicada de MAX(sequence), sem carregar
    # todos os eventos do trace no endpoint.
    next_seq = 0
    try:
        max_sequence = store.get_max_trace_sequence(trace_id=payload.trace_id)
        if max_sequence is not None:
            next_seq = max_sequence + 1
    except Exception:  # noqa: BLE001 - sequence é nice-to-have, não bloqueia
        pass

    # PR#28 review (issue 3): aplica truncate_payload server-side. Evita
    # que cliente malicioso/bugged envie payload arbitrariamente grande
    # direto pro JSONB do Postgres bypassando os 50KB do tracer.record().
    safe_payload = _truncate_payload(payload.payload or {})

    # Constrói o evento server-side com defaults seguros.
    event = ModelingTraceEvent(
        trace_id=payload.trace_id,
        plan_id=payload.plan_id,
        event_type=payload.event_type,
        source=ModelingTraceSource.ui,  # forçado, ignora qualquer source do cliente
        level=payload.level,
        message=payload.message,
        payload=safe_payload,
        duration_ms=payload.duration_ms,
        sequence=next_seq,
    )
    store.record_trace_events_bulk([event])
    return event


@router.get("/plans/{plan_id}/diagnostics")
def get_plan_diagnostics(plan_id: str) -> dict[str, Any]:
    """Endpoint consolidado de diagnóstico para um plano.

    Combina o plano, tool calls, printability reports e os últimos N
    eventos de trace em um único JSON exportável — útil para gerar
    bundles de bug report (``curl ... > bug-bundle.json``).
    """

    store = get_store()
    plan = store.get_modeling_plan(plan_id) if hasattr(store, "get_modeling_plan") else None
    if plan is None:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.")
    tool_calls = (
        store.list_modeling_tool_calls(plan_id=plan_id)
        if hasattr(store, "list_modeling_tool_calls")
        else []
    )
    trace_events: list[ModelingTraceEvent] = []
    if hasattr(store, "list_trace_events"):
        trace_events = store.list_trace_events(plan_id=plan_id, limit=1000)
    printability = (
        store.list_modeling_printability_reports(plan_id=plan_id)
        if hasattr(store, "list_modeling_printability_reports")
        else []
    )
    return {
        "plan": plan.model_dump(mode="json"),
        "tool_calls": [tc.model_dump(mode="json") for tc in tool_calls],
        "trace_events": [te.model_dump(mode="json") for te in trace_events],
        "printability_reports": [pr.model_dump(mode="json") for pr in printability],
        "schema_version": 1,
    }


# PR#28 review (issue 4): wire o tracer LAZY no startup do FastAPI em vez
# de import-time. No padrão antigo, se ``get_store()`` falhasse no import
# (DB não pronto), o try silencioso engolia o erro e algum service init
# subsequente podia criar o singleton com store=None (no-op permanente
# até restart). Esta função é chamada no ``lifespan`` em ``app/main.py``.
def wire_tracer_store() -> None:
    """Re-conecta o tracer singleton à store quando o app está pronto.

    Idempotente. Se o singleton já foi criado com store válida, é no-op.
    Se foi criado com store=None (caso degradado), faz reset + reconnect.
    """

    from app.modeling.observability import reset_tracer

    try:
        store = get_store()
    except Exception:  # noqa: BLE001 - app não deve crashar no startup por isso
        return
    if not hasattr(store, "record_trace_events_bulk"):
        return
    reset_tracer()
    get_tracer(store)
