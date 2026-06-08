"""Plan execution service extracted from the v1 :class:`ModelingService`.

ADR-013 splits the modeling backend into focused services. This module owns
plan execution end-to-end: routing steps to the MCP client (or the
in-process ``project_store`` handler), wrapping outputs in tool-call records
and updating the plan status when a step fails / completes / stays blocked.

The :class:`ModelingService` facade keeps the same public ``execute_plan``
method and delegates here.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from app.core.contracts import (
    AuditEvent,
    ModelingErrorEnvelope,
    ModelingExecutionResult,
    ModelingPlan,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingSnapshotCreate,
    ModelingStepStatus,
    ModelingToolCall,
    ModelingToolCallStatus,
    ModelingTraceLevel,
    ModelingTraceSource,
    now_utc,
)
from app.modeling.artifacts import ModelingArtifactService
from app.modeling.mcp_client import LocalMCPClient
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.snapshot_service import ModelingSnapshotService
from app.modeling.spatial_ref import SpatialRefError


def _unwrap_inner_fusion_result(output: dict[str, Any]) -> dict[str, Any]:
    """Detecta e propaga falhas do adapter Fusion que vinham mascaradas.

    Bug observado via trace (porta-figurinhas WC2026, 11/05/2026): o
    fusion_adapter HTTP retorna ``ok: true`` na camada de transporte mesmo
    quando o tool falhou — o ``ok: false`` real fica num **JSON stringificado**
    dentro de ``output["message"]`` (e duplicado em ``result.message``).
    O executor antes checava só o ``output["ok"]`` externo e marcava todos os
    steps como verdes. Resultado: o card do chat mostrava "concluído" para
    16/16 steps mas o Fusion estava vazio porque 11/16 falharam silenciosamente.

    Esta função detecta o padrão e, quando o inner result indica falha,
    promove ``error_code``, ``message`` e ``ok: false`` ao nível externo para
    que ``execute_plan`` consiga decidir corretamente. Idempotente: se o
    output já está no formato direto (sem stringified inner), retorna sem
    modificações.

    Não toca em outros transportes (stdio, in_process, mock) — eles já
    retornam o dict no formato direto.
    """

    if not isinstance(output, dict):
        return output

    # Já marcado como falha no nível externo — nada a fazer.
    if output.get("ok") is False:
        return output

    message = output.get("message")
    if not isinstance(message, str):
        return output

    stripped = message.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return output

    try:
        inner = json.loads(stripped)
    except json.JSONDecodeError:
        return output

    if not isinstance(inner, dict):
        return output
    if inner.get("ok") is not False:
        return output

    # Inner result é uma falha — promove campos ao topo. Preserva o output
    # original em ``host_details`` para debug e auditoria.
    promoted = dict(output)
    promoted["ok"] = False
    promoted["message"] = inner.get("message") or stripped
    if inner.get("error_code"):
        promoted["error_code"] = inner["error_code"]
    if inner.get("retryable") is not None:
        promoted["retryable"] = inner["retryable"]
    if "safe_to_retry_after_snapshot_restore" in inner:
        promoted["safe_to_retry_after_snapshot_restore"] = inner[
            "safe_to_retry_after_snapshot_restore"
        ]
    if inner.get("traceback"):
        existing_host_details = (
            promoted.get("host_details") if isinstance(promoted.get("host_details"), dict) else {}
        )
        promoted["host_details"] = {
            **existing_host_details,
            "inner_traceback": inner["traceback"],
        }
    return promoted


def inner_fusion_payload(output: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extrai o payload real de um tool fusion do envelope do adapter HTTP.

    Tools fusion **bem-sucedidas** devolvem o dict do script como JSON
    *stringificado* em ``output["message"]`` (duplicado em
    ``output["result"]["message"]``); :func:`_unwrap_inner_fusion_result` só
    promove campos ao topo em FALHA. Para ler campos estruturados de um
    SUCESSO (``dimensions_mm``, ``timeline_count``, ``timeline``...) é preciso
    parsear aqui. O formato direto (mock/in_process/fakes — dict já plano)
    volta inalterado; entrada não-dict vira ``None``.

    Fonte única usada pelo verifier geométrico (item C, ``agent_loop``) e pela
    reconciliação/rollback (``chat_orchestrator``). Sem isto o read-back ficava
    mudo no Fusion real (gate 2026-05-26): o envelope mascarava as dimensões.
    """

    if not isinstance(output, dict):
        return None
    candidates = [output.get("message")]
    result = output.get("result")
    if isinstance(result, dict):
        candidates.append(result.get("message"))
    for cand in candidates:
        if not isinstance(cand, str):
            continue
        stripped = cand.strip()
        if not (stripped.startswith("{") and stripped.endswith("}")):
            continue
        try:
            inner = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(inner, dict):
            return inner
    return output


def envelope_into_output(
    envelope: ModelingErrorEnvelope, *, base: dict[str, Any]
) -> dict[str, Any]:
    """Spread a typed error envelope into a tool output dict.

    Keeps a single source of truth for error fields (``error_code``,
    ``retryable``, ``safe_to_retry_after_snapshot_restore``,
    ``host_details``) while still returning a serializable dict to fit the
    existing dict-based tool-call contract.
    """

    return {**base, **envelope.model_dump(), "message": envelope.message}


def envelope_from_output(output: dict[str, Any]) -> ModelingErrorEnvelope | None:
    """Reconstruct an envelope from a tool output dict, if one is present."""

    error_code = output.get("error_code")
    if not error_code:
        return None
    try:
        return ModelingErrorEnvelope(
            error_code=str(error_code),
            message=str(output.get("message") or output.get("error") or ""),
            retryable=bool(output.get("retryable", False)),
            safe_to_retry_after_snapshot_restore=bool(
                output.get("safe_to_retry_after_snapshot_restore", False)
            ),
            host_details=(
                output["host_details"] if isinstance(output.get("host_details"), dict) else {}
            ),
        )
    except Exception:  # pragma: no cover - defensive against malformed output
        return None


@dataclass
class _StepOutcome:
    """Outcome of executing a single plan step (see ``_execute_single_step``)."""

    step: ModelingPlanStep
    output: dict[str, Any]
    tool_call_id: str | None
    event: str
    ok: bool


class ModelingExecutorService:
    """Executes plans by dispatching steps and recording tool calls."""

    def __init__(
        self,
        store: Any,
        mcp_client: LocalMCPClient,
        snapshots: ModelingSnapshotService,
        artifacts: ModelingArtifactService,
    ) -> None:
        self.store = store
        self.mcp_client = mcp_client
        self.snapshots = snapshots
        self.artifacts = artifacts
        # Tracer compartilhado (no-op se a store não tem record_trace_events_bulk).
        self._tracer = get_tracer(store if hasattr(store, "record_trace_events_bulk") else None)
        # F8: carry-forward do ModelState (plan_id, after) p/ ser o before do
        # próximo passo — evita 2 probes/passo na proveniência.
        self._provenance_carry: tuple[str, Any] | None = None

    def execute_plan(self, plan: ModelingPlan) -> ModelingExecutionResult:
        """Execute every runnable step of ``plan`` and persist the result."""

        if plan.status == ModelingPlanStatus.draft:
            blocked_step_ids = [step.id for step in plan.steps]
            return ModelingExecutionResult(
                plan=plan,
                executed_step_ids=[],
                blocked_step_ids=blocked_step_ids,
                events=["Plano em modo planejamento; aprove antes de executar."],
                tool_call_ids=[],
            )

        executed_step_ids: list[str] = []
        blocked_step_ids: list[str] = []
        events: list[str] = []
        tool_call_ids: list[str] = []
        next_steps: list[ModelingPlanStep] = []

        for step in plan.steps:
            if step.error:
                blocked_step_ids.append(step.id)
                next_steps.append(step)
                self._tracer.record(
                    "executor.step_skipped",
                    source=ModelingTraceSource.backend,
                    level=ModelingTraceLevel.warn,
                    message=f"Step {step.seq} bloqueado por erro prévio",
                    payload={"step_id": step.id, "tool_name": step.tool_name, "error": step.error},
                    plan_id=plan.id,
                )
                continue
            if step.approval_required and step.status != ModelingStepStatus.approved:
                blocked_step_ids.append(step.id)
                next_steps.append(step)
                self._tracer.record(
                    "executor.step_blocked",
                    source=ModelingTraceSource.backend,
                    level=ModelingTraceLevel.info,
                    message=f"Step {step.seq} aguardando aprovação humana",
                    payload={
                        "step_id": step.id,
                        "tool_name": step.tool_name,
                        "risk_level": step.risk_level.value,
                    },
                    plan_id=plan.id,
                )
                continue

            outcome = self._execute_single_step(step, plan=plan)
            executed_step_ids.append(step.id)
            events.append(outcome.event)
            if outcome.tool_call_id is not None:
                tool_call_ids.append(outcome.tool_call_id)
            if not outcome.ok:
                blocked_step_ids.append(step.id)
            next_steps.append(outcome.step)

        has_failed_step = any(step.status == ModelingStepStatus.failed for step in next_steps)
        if has_failed_step:
            status = ModelingPlanStatus.failed
        elif blocked_step_ids:
            status = ModelingPlanStatus.running
        else:
            status = ModelingPlanStatus.completed
        updated = plan.model_copy(
            update={"steps": next_steps, "status": status, "updated_at": now_utc()}
        )
        self.store.upsert_modeling_plan(updated)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.plan_executed",
                metadata={
                    "plan_id": updated.id,
                    "executed_step_ids": executed_step_ids,
                    "blocked_step_ids": blocked_step_ids,
                    "tool_call_ids": tool_call_ids,
                },
                trace_id=current_trace_id(),
            ),
        )
        # Fix #7: flush imediato dos trace events do executor.
        # Bug observado via SQL: planos com <= 12 steps (< batch_size=25)
        # geravam events no buffer mas nunca chegavam ao DB porque o
        # auto-flush so dispara em multiplos de batch_size, e ninguem
        # chamava flush() externamente apos execute_plan. Resultado:
        # modal de diagnostico ficava vazio mesmo apos execucao OK.
        # O caso de 01:12 (porta-figurinhas, 16 steps + fallback)
        # funcionava por sorte — passava de 25 events e batia auto-flush.
        # PR#28 review (issue 6): passa trace_id explicito para evitar
        # iterar buffers de outros traces em execucao concorrente.
        self._tracer.flush(current_trace_id())
        return ModelingExecutionResult(
            plan=updated,
            executed_step_ids=executed_step_ids,
            blocked_step_ids=blocked_step_ids,
            events=events,
            tool_call_ids=tool_call_ids,
        )

    # ------------------------------------------------------------------
    # single-step execution (extension seam for the Fase 2 agentic loop)
    # ------------------------------------------------------------------

    def _execute_single_step(self, step: ModelingPlanStep, *, plan: ModelingPlan) -> _StepOutcome:
        """Run one runnable step end-to-end and return its outcome.

        Dispatch → unwrap inner Fusion failures → register artifacts →
        persist the tool call → emit per-step trace, then return the updated
        step (completed/failed) plus the event/tool-call/ok aggregates the
        caller collects.

        This is the **extension seam** for the Fase 2 agentic loop (replan
        v4, ADR-017+): the loop will call this per step, read back geometry
        and — on failure or geometric divergence — retry with a correction
        context (teto 5). Today it runs exactly once per step, so behavior is
        identical to the inline v1 loop.
        """

        self._tracer.record(
            "executor.step_started",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.info,
            message=f"Step {step.seq}: {step.tool_name}",
            payload={
                "step_id": step.id,
                "seq": step.seq,
                "tool_name": step.tool_name,
                "input": step.input_json,
            },
            plan_id=plan.id,
        )

        # F7 (P5): resolução de posicionamento paramétrico ANTES do dispatch
        # (atrás de flag; probe só quando o passo carrega ref/é declarativo).
        # Inline → reescreve args; tool declarativa → expande e executa cada
        # concreto. Flag OFF / passo sem ref = no-op (caminho atual intacto).
        try:
            step, expanded_steps = self._maybe_resolve_spatial(step, plan=plan)
        except SpatialRefError as exc:
            return self._spatial_failure_outcome(step, plan, exc)
        if expanded_steps is not None:
            return self._run_expanded_steps(step, expanded_steps, plan)

        # F8: estado ANTES do dispatch (carry-forward ou probe), p/ a proveniência.
        prov_before = self._provenance_before_state(step, plan)

        started_at = time.perf_counter()
        output = self._dispatch_step(step, plan=plan)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        # Fix #0: desempacota inner ``ok: false`` do fusion_adapter HTTP
        # antes da decisão de sucesso, senão falhas chegam como verdes.
        output = _unwrap_inner_fusion_result(output)
        output = self.artifacts.register_outputs(output, plan=plan, step=step)

        # F8: grava o ChangeRecord (o que o passo criou/modificou/consumiu/
        # deletou) em output["_provenance"] ANTES de persistir o tool_call.
        self._attach_provenance(step, plan, output, prov_before)

        tool_call = self._record_tool_call(
            plan=plan, step=step, output=output, duration_ms=duration_ms
        )

        event_verb = "executado" if output.get("transport") != "mock" else "preparado"
        event = f"{step.seq}. {step.tool_name} {event_verb} via {output['mcp_server']}"

        step_ok = output.get("ok") is not False
        self._tracer.record(
            "executor.step_ok" if step_ok else "executor.step_error",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.info if step_ok else ModelingTraceLevel.error,
            message=(
                f"Step {step.seq} OK"
                if step_ok
                else f"Step {step.seq} falhou: {output.get('message') or output.get('error')}"
            ),
            payload={
                "step_id": step.id,
                "tool_name": step.tool_name,
                "transport": output.get("transport"),
                "mcp_server": output.get("mcp_server"),
                "error_code": output.get("error_code"),
                "error_message": output.get("message") or output.get("error"),
                "retryable": output.get("retryable"),
            },
            duration_ms=duration_ms,
            plan_id=plan.id,
        )

        if not step_ok:
            updated_step = step.model_copy(
                update={
                    "status": ModelingStepStatus.failed,
                    "output_json": output,
                    "error": str(output.get("message") or output.get("error") or ""),
                    "completed_at": now_utc(),
                }
            )
        else:
            updated_step = step.model_copy(
                update={
                    "status": ModelingStepStatus.completed,
                    "output_json": output,
                    "completed_at": now_utc(),
                }
            )

        return _StepOutcome(
            step=updated_step,
            output=output,
            tool_call_id=tool_call.id if tool_call is not None else None,
            event=event,
            ok=step_ok,
        )

    # ------------------------------------------------------------------
    # F7: resolução de posicionamento paramétrico (pré-dispatch, flag-gated)
    # ------------------------------------------------------------------

    def _maybe_resolve_spatial(
        self, step: ModelingPlanStep, *, plan: ModelingPlan
    ) -> tuple[ModelingPlanStep, list[ModelingPlanStep] | None]:
        """Resolve refs/placement do passo antes do dispatch (Frente F7).

        Retorna ``(step, expandidos)``: no-op/inline → ``(step', None)``; tool
        declarativa F7 → ``(step, [passos concretos])``. Probe ``query_geometry``
        e resolução só rodam quando o passo realmente carrega ref ou é
        declarativo — flag OFF é no-op puro (caminho de coordenada absoluta).
        """

        from app.core.config import settings

        if not settings.modeling_spatial_resolution_enabled:
            return step, None

        from app.modeling.spatial_resolver import (
            F7_PLACEMENT_TOOLS,
            materialize_steps,
            needs_resolution,
            resolve_step,
        )
        from app.modeling.tool_registry import is_read_only

        if not needs_resolution(
            step.tool_name, step.input_json, read_only=is_read_only(step.tool_name)
        ):
            return step, None

        # Probe ao vivo: o resolver precisa da geometria REAL (tokens/bbox/pontas)
        # dos corpos já criados nos passos anteriores. capture_model_state é
        # best-effort (None se não-fusion/falha); refs sem estado caem em
        # SpatialRefError (erro tipado), não em mis-place.
        from app.modeling.model_state import capture_model_state

        state = capture_model_state(self, plan)
        concrete, actions = resolve_step(step.tool_name, dict(step.input_json or {}), state)
        self._tracer.record(
            "executor.spatial_resolved",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.info,
            message=f"F7: {step.tool_name} → {len(concrete)} passo(s) concreto(s)",
            payload={
                "step_id": step.id,
                "tool_name": step.tool_name,
                "concrete_tools": [c.tool_name for c in concrete],
                "actions": [a.detail for a in actions],
                "had_state": state is not None,
            },
            plan_id=plan.id,
        )
        # Inline (1→1, mesma tool): só reescreve os args resolvidos.
        if step.tool_name not in F7_PLACEMENT_TOOLS and len(concrete) == 1:
            return step.model_copy(update={"input_json": dict(concrete[0].input_json)}), None
        # Declarativa (1→N): materializa os passos concretos para execução.
        return step, materialize_steps(step, concrete)

    def _run_expanded_steps(
        self,
        original: ModelingPlanStep,
        concrete: list[ModelingPlanStep],
        plan: ModelingPlan,
    ) -> _StepOutcome:
        """Executa os passos concretos de uma tool declarativa F7 em sequência e
        agrega num único ``_StepOutcome`` (para o chamador, a placement é 1
        passo). Para no primeiro que falhar — os seguintes dependem dele."""

        # Constituição (inegociável): uma tool declarativa `additive` NÃO pode
        # "lavar" um concreto high_risk/destrutivo (ex.: combine_bodies da
        # combine-DENTRO) e auto-executá-lo sem aprovação humana. Pré-varre e
        # BLOQUEIA a expansão inteira ANTES de executar qualquer passo (fail-safe,
        # sem deixar corpos soltos). A UX de aprovar o sub-passo é follow-up.
        # Gate pela CATEGORIA intrínseca do concreto — NÃO pelo risk_level herdado
        # do declarativo (esse já foi consumido pelo gate de aprovação no nível do
        # plano; re-checá-lo re-bloquearia um placement já aprovado pelo humano).
        from app.modeling.tool_registry import is_blocked, is_high_risk

        blocked = [c for c in concrete if is_high_risk(c.tool_name) or is_blocked(c.tool_name)]
        if blocked:
            return self._spatial_expansion_blocked(original, blocked, plan)

        outcomes: list[_StepOutcome] = []
        for concrete_step in concrete:
            # Concretos não são F7 nem carregam ref → _maybe_resolve_spatial é
            # no-op para eles (sem recursão/probe).
            oc = self._execute_single_step(concrete_step, plan=plan)
            outcomes.append(oc)
            if not oc.ok:
                break

        ok = bool(outcomes) and all(o.ok for o in outcomes)
        n_ok = sum(1 for o in outcomes if o.ok)
        last = outcomes[-1] if outcomes else None
        agg_output: dict[str, Any] = {
            "ok": ok,
            "tool_name": original.tool_name,
            "transport": "backend",
            "mcp_server": "spatial_resolver",
            "expanded": [{"tool_name": o.step.tool_name, "ok": o.ok} for o in outcomes],
            "message": (last.output.get("message") if last else "F7: sem passos concretos"),
        }
        status = ModelingStepStatus.completed if ok else ModelingStepStatus.failed
        updated = original.model_copy(
            update={
                "status": status,
                "output_json": agg_output,
                "error": None if ok else "F7: passo concreto falhou",
                "completed_at": now_utc(),
            }
        )
        return _StepOutcome(
            step=updated,
            output=agg_output,
            tool_call_id=(last.tool_call_id if last is not None else None),
            event=f"{original.seq}. {original.tool_name} → {n_ok}/{len(concrete)} concreto(s)",
            ok=ok,
        )

    def _spatial_expansion_blocked(
        self,
        original: ModelingPlanStep,
        blocked: list[ModelingPlanStep],
        plan: ModelingPlan,
    ) -> _StepOutcome:
        """Bloqueia (fail-safe) uma expansão F7 que conteria concreto high_risk
        sem aprovação. Passo declarativo vira FALHO com erro tipado claro."""

        names = ", ".join(sorted({c.tool_name for c in blocked}))
        msg = (
            f"Placement F7 expande para operação que exige aprovação humana "
            f"({names}); não auto-executa (constituição: high_risk/destrutivo no "
            f"caminho feliz). Aprovação de sub-passo é follow-up."
        )
        output: dict[str, Any] = {
            "ok": False,
            "tool_name": original.tool_name,
            "transport": "backend",
            "mcp_server": "spatial_resolver",
            "error_code": "fusion.spatial_expansion_requires_approval",
            "message": msg,
        }
        self._tracer.record(
            "executor.step_error",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.warn,
            message=f"Step {original.seq} F7 bloqueado: expande p/ {names} (aprovação)",
            payload={"step_id": original.id, "tool_name": original.tool_name, "blocked": names},
            plan_id=plan.id,
        )
        tool_call = self._record_tool_call(plan=plan, step=original, output=output, duration_ms=0)
        updated = original.model_copy(
            update={
                "status": ModelingStepStatus.failed,
                "output_json": output,
                "error": msg,
                "completed_at": now_utc(),
            }
        )
        return _StepOutcome(
            step=updated,
            output=output,
            tool_call_id=(tool_call.id if tool_call is not None else None),
            event=f"{original.seq}. {original.tool_name} bloqueado (expansão high_risk)",
            ok=False,
        )

    def _spatial_failure_outcome(
        self, step: ModelingPlanStep, plan: ModelingPlan, exc: SpatialRefError
    ) -> _StepOutcome:
        """Converte um erro de resolução F7 num passo FALHO claro (nunca chuta)."""

        code = getattr(exc, "code", "fusion.spatial_ref_unresolved")
        output: dict[str, Any] = {
            "ok": False,
            "tool_name": step.tool_name,
            "transport": "backend",
            "mcp_server": "spatial_resolver",
            "error_code": code,
            "message": str(exc),
        }
        self._tracer.record(
            "executor.step_error",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.error,
            message=f"Step {step.seq} F7 não resolvido: {exc}",
            payload={"step_id": step.id, "tool_name": step.tool_name, "error_code": code},
            plan_id=plan.id,
        )
        # Paridade com a falha de dispatch normal: persiste o tool_call (status
        # error) p/ a falha F7 não sumir do painel de tool_calls.
        tool_call = self._record_tool_call(plan=plan, step=step, output=output, duration_ms=0)
        updated = step.model_copy(
            update={
                "status": ModelingStepStatus.failed,
                "output_json": output,
                "error": str(exc),
                "completed_at": now_utc(),
            }
        )
        return _StepOutcome(
            step=updated,
            output=output,
            tool_call_id=(tool_call.id if tool_call is not None else None),
            event=f"{step.seq}. {step.tool_name} não resolvido (F7)",
            ok=False,
        )

    # ------------------------------------------------------------------
    # F8: proveniência de operações (captura before/after, flag-gated)
    # ------------------------------------------------------------------

    def _provenance_active(self, step: ModelingPlanStep) -> bool:
        from app.core.config import settings

        if not settings.modeling_provenance_enabled:
            return False
        if not step.tool_name.startswith("fusion."):
            return False
        # Só passos MUTATIVOS — read-only (query_geometry probe) não gera
        # proveniência (e evita recursão na captura).
        from app.modeling.tool_registry import is_read_only

        return not is_read_only(step.tool_name)

    def _provenance_before_state(self, step: ModelingPlanStep, plan: ModelingPlan):
        """Estado ANTES do passo: carry-forward do after do passo anterior (mesmo
        plano) ou um probe fresco. ``None`` se a proveniência está inativa."""

        if not self._provenance_active(step):
            return None
        if self._provenance_carry is not None and self._provenance_carry[0] == plan.id:
            return self._provenance_carry[1]
        from app.modeling.model_state import capture_model_state

        return capture_model_state(self, plan)

    def _attach_provenance(
        self,
        step: ModelingPlanStep,
        plan: ModelingPlan,
        output: dict[str, Any],
        before_state: Any,
    ) -> None:
        """Captura o after, monta o ChangeRecord e o anexa em
        ``output["_provenance"]`` (zero-migration) + trace; carrega o after p/ ser
        o before do próximo passo. Best-effort — nunca quebra a execução."""

        if not self._provenance_active(step):
            return
        try:
            from app.modeling.model_state import capture_model_state
            from app.modeling.provenance import build_change_record
            from app.modeling.tool_registry import descriptor

            after = capture_model_state(self, plan)
            self._provenance_carry = (plan.id, after)
            desc = descriptor(step.tool_name)
            category = desc.category.value if desc is not None else None
            record = build_change_record(
                step.tool_name,
                before_state,
                after,
                category=category,
                seq=step.seq,
                step_id=step.id,
            )
        except Exception:  # noqa: BLE001 - proveniência é observabilidade, best-effort
            return
        if isinstance(output, dict):
            output["_provenance"] = record.model_dump(mode="json")
        self._tracer.record(
            "executor.provenance_recorded",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.info,
            message=f"Step {step.seq} proveniência: {record.summary}",
            payload={
                "step_id": step.id,
                "tool_name": step.tool_name,
                "summary": record.summary,
                "created": len(record.created),
                "modified": len(record.modified),
                "consumed": len(record.consumed),
                "deleted": len(record.deleted),
                "uncertain": len(record.uncertain),
            },
            plan_id=plan.id,
        )

    # ------------------------------------------------------------------
    # step dispatch
    # ------------------------------------------------------------------

    def _dispatch_step(self, step: ModelingPlanStep, *, plan: ModelingPlan) -> dict[str, Any]:
        """Route a step to the right local handler.

        ``project_store.*`` tools are handled inline because the project
        store lives in the same process. Everything else goes through the
        MCP client boundary, which delegates to the adapter or falls back
        to mock.
        """

        if step.tool_name == "project_store.create_snapshot":
            return self._run_project_store_snapshot(step, plan=plan)
        return self.mcp_client.execute_step(
            step,
            plan_id=plan.id,
            project_id=plan.project_id,
        )

    def _run_project_store_snapshot(
        self, step: ModelingPlanStep, *, plan: ModelingPlan
    ) -> dict[str, Any]:
        try:
            snapshot = self.snapshots.create(
                ModelingSnapshotCreate(
                    project_id=plan.project_id,
                    plan_id=plan.id,
                    step_id=step.id,
                    label=str(step.input_json.get("label") or f"Plan {plan.id} step {step.seq}"),
                    reason=str(step.input_json.get("reason") or "before_modeling"),
                )
            )
        except Exception as exc:  # pragma: no cover - safety net
            envelope = ModelingErrorEnvelope(
                error_code="project_store.snapshot_failed",
                message=f"Falha ao criar snapshot: {exc}",
                retryable=False,
                safe_to_retry_after_snapshot_restore=False,
                host_details={"plan_id": plan.id, "step_id": step.id},
            )
            return envelope_into_output(
                envelope,
                base={
                    "ok": False,
                    "mcp_server": "project_store_mcp",
                    "transport": "local",
                    "tool_name": step.tool_name,
                    "software": step.software.value,
                    "input": step.input_json,
                },
            )
        return {
            "ok": True,
            "mcp_server": "project_store_mcp",
            "transport": "local",
            "tool_name": step.tool_name,
            "software": step.software.value,
            "message": f"Snapshot {snapshot.id} criado ({len(snapshot.files)} arquivo(s)).",
            "input": step.input_json,
            "snapshot_id": snapshot.id,
            "artifact_paths": [],
        }

    # ------------------------------------------------------------------
    # tool-call persistence
    # ------------------------------------------------------------------

    def _record_tool_call(
        self,
        *,
        plan: ModelingPlan,
        step: ModelingPlanStep,
        output: dict[str, Any],
        duration_ms: int,
    ) -> ModelingToolCall | None:
        if not hasattr(self.store, "add_modeling_tool_call"):
            return None
        ok = output.get("ok") is not False
        status = ModelingToolCallStatus.ok if ok else ModelingToolCallStatus.error
        artifact_paths = [
            value for value in output.get("artifact_paths", []) if isinstance(value, str) and value
        ]
        artifact_file_ids = [
            value
            for value in output.get("platform_file_ids", [])
            if isinstance(value, str) and value
        ]
        model_version_ids = [
            value
            for value in output.get("model_version_ids", [])
            if isinstance(value, str) and value
        ]
        envelope = envelope_from_output(output) if not ok else None
        record = ModelingToolCall(
            plan_id=plan.id,
            step_id=step.id,
            seq=step.seq,
            mcp_server=str(output.get("mcp_server") or "unknown_mcp"),
            tool_name=step.tool_name,
            software=step.software,
            transport=output.get("transport") or "mock",
            status=status,
            request_json=step.input_json,
            response_json=output,
            error_code=envelope.error_code if envelope else None,
            error_message=envelope.message if envelope else None,
            retryable=envelope.retryable if envelope else False,
            safe_to_retry_after_snapshot_restore=(
                envelope.safe_to_retry_after_snapshot_restore if envelope else False
            ),
            duration_ms=duration_ms,
            artifact_paths=artifact_paths,
            artifact_file_ids=artifact_file_ids,
            model_version_ids=model_version_ids,
        )
        return self.store.add_modeling_tool_call(record)


__all__ = [
    "ModelingExecutorService",
    "envelope_from_output",
    "envelope_into_output",
]
