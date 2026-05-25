"""Loop agêntico de execução com auto-correção (Fase 2 — RF-008/010/011).

Após a aprovação, o motor executa o plano **do início ao fim, sem pausar**; para
cada passo roda um loop ``executa → inspeciona → corrige`` com **teto de 5
iterações**. Em falha recuperável (erro de tool ou — quando há read-back —
divergência geométrica), pede uma correção ao ``corrector`` e re-executa o MESMO
passo. Ao **esgotar** as iterações, PARA, reverte ao último estado seguro
(rollback) e reporta a falha (RF-011).

Pluga na costura ``ModelingExecutorService._execute_single_step``. Injeções:
- ``corrector(step, output, attempt) -> ModelingPlanStep | None`` — produz o
  passo corrigido (em produção: planner LLM via ``build_correction_context``).
- ``verifier(step, output) -> dict | None`` — verificação geométrica (read-back
  esperado × medido). Só roda com o Fusion real (gate do dono); sem ela, a
  correção dispara apenas em falha de tool.
- ``rollback(plan) -> None`` — reversão ao estado seguro (DT-005: nativo do
  Fusion, pendente do gate; aqui é best-effort/injetável).

DT-010: o delta corretivo high-risk **não** bloqueia — a aprovação do plano já
cobre a correção; o loop não pausa para aprovar a correção.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.core.config import settings
from app.core.contracts import (
    AuditEvent,
    ModelingExecutionResult,
    ModelingPlan,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingStepStatus,
    ModelingTraceLevel,
    ModelingTraceSource,
    now_utc,
)
from app.modeling.executor import ModelingExecutorService
from app.modeling.observability import current_trace_id

logger = logging.getLogger(__name__)

MAX_CORRECTION_ITERATIONS = 5

StepCorrector = Callable[[ModelingPlanStep, dict[str, Any], int], ModelingPlanStep | None]
GeometryVerifier = Callable[[ModelingPlanStep, dict[str, Any]], dict[str, Any] | None]
PlanRollback = Callable[[ModelingPlan], None]


class ModelingAgentLoop:
    """Execução autônoma fim-a-fim com loop de auto-correção por passo."""

    def __init__(
        self,
        executor: ModelingExecutorService,
        *,
        corrector: StepCorrector | None = None,
        verifier: GeometryVerifier | None = None,
        rollback: PlanRollback | None = None,
        max_iterations: int = MAX_CORRECTION_ITERATIONS,
    ) -> None:
        self.executor = executor
        self.corrector = corrector
        self.verifier = verifier
        self.rollback = rollback
        self.max_iterations = max(1, max_iterations)
        # Reusa o tracer do executor (mesma sink/trace ativo).
        self._tracer = executor._tracer

    def run(self, plan: ModelingPlan) -> ModelingExecutionResult:
        if plan.status == ModelingPlanStatus.draft:
            return ModelingExecutionResult(
                plan=plan,
                executed_step_ids=[],
                blocked_step_ids=[step.id for step in plan.steps],
                events=["Plano em modo planejamento; aprove antes de executar."],
                tool_call_ids=[],
            )

        executed_step_ids: list[str] = []
        blocked_step_ids: list[str] = []
        events: list[str] = []
        tool_call_ids: list[str] = []
        next_steps: list[ModelingPlanStep] = []
        aborted = False

        for step in plan.steps:
            if aborted:
                # RF-011: após esgotar a correção de um passo, o motor PARA;
                # os passos seguintes ficam bloqueados (estado consistente).
                blocked_step_ids.append(step.id)
                next_steps.append(step)
                continue
            if step.error:
                blocked_step_ids.append(step.id)
                next_steps.append(step)
                continue
            if step.approval_required and step.status != ModelingStepStatus.approved:
                blocked_step_ids.append(step.id)
                next_steps.append(step)
                continue

            current = step
            outcome = self.executor._execute_single_step(current, plan=plan)
            attempt = 0
            while self._needs_correction(current, outcome) and attempt < self.max_iterations:
                attempt += 1
                # Tool OK mas geometria divergente (verifier): injeta a
                # divergência no output p/ o corretor enxergar (o
                # build_correction_context formata "esperado × medido").
                divergence = None
                if outcome.ok and self.verifier is not None:
                    divergence = self.verifier(current, outcome.output)
                self._tracer.record(
                    "agent_loop.correction_attempt",
                    source=ModelingTraceSource.backend,
                    level=ModelingTraceLevel.warn,
                    message=f"Step {current.seq}: auto-correção {attempt}/{self.max_iterations}",
                    payload={
                        "step_id": step.id,
                        "tool_name": current.tool_name,
                        "error_code": outcome.output.get("error_code"),
                        "divergence": divergence,
                    },
                    plan_id=plan.id,
                )
                corrector_output = outcome.output
                if divergence is not None:
                    corrector_output = {**outcome.output, "verification_divergence": divergence}
                corrected = (
                    self.corrector(current, corrector_output, attempt) if self.corrector else None
                )
                if corrected is None:
                    break
                current = corrected
                outcome = self.executor._execute_single_step(current, plan=plan)

            executed_step_ids.append(step.id)
            suffix = f" (após {attempt} correção(ões))" if attempt else ""
            events.append(outcome.event + suffix)
            if outcome.tool_call_id is not None:
                tool_call_ids.append(outcome.tool_call_id)
            next_steps.append(outcome.step)

            if self._needs_correction(current, outcome):
                # Esgotou as iterações sem sucesso → PARA + rollback (RF-011).
                blocked_step_ids.append(step.id)
                aborted = True
                self._tracer.record(
                    "agent_loop.exhausted",
                    source=ModelingTraceSource.backend,
                    level=ModelingTraceLevel.error,
                    message=(
                        f"Step {step.seq} esgotou {self.max_iterations} correções; "
                        "revertendo e parando."
                    ),
                    payload={"step_id": step.id, "tool_name": current.tool_name},
                    plan_id=plan.id,
                )
                self._do_rollback(plan)

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
        self.executor.store.upsert_modeling_plan(updated)
        self.executor.store.add_audit_event(
            AuditEvent(
                event_type="modeling.agent_loop_executed",
                metadata={
                    "plan_id": updated.id,
                    "executed_step_ids": executed_step_ids,
                    "blocked_step_ids": blocked_step_ids,
                    "tool_call_ids": tool_call_ids,
                    "aborted": aborted,
                },
                trace_id=current_trace_id(),
            ),
        )
        self._tracer.flush(current_trace_id())
        return ModelingExecutionResult(
            plan=updated,
            executed_step_ids=executed_step_ids,
            blocked_step_ids=blocked_step_ids,
            events=events,
            tool_call_ids=tool_call_ids,
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _needs_correction(self, step: ModelingPlanStep, outcome: Any) -> bool:
        if not outcome.ok:
            return True
        # Verificação geométrica (read-back esperado × medido). Só quando
        # injetada — depende do Fusion real (gate do dono).
        if self.verifier is not None:
            divergence = self.verifier(step, outcome.output)
            if divergence:
                return True
        return False

    def _do_rollback(self, plan: ModelingPlan) -> None:
        if self.rollback is None:
            # Rollback nativo do Fusion ainda não disponível (DT-005, pendente
            # do gate). Registra a intenção para auditoria/observabilidade.
            self._tracer.record(
                "agent_loop.rollback_skipped",
                source=ModelingTraceSource.backend,
                level=ModelingTraceLevel.warn,
                message="Rollback solicitado mas nenhum mecanismo de reversão injetado.",
                payload={"plan_id": plan.id},
                plan_id=plan.id,
            )
            return
        try:
            self.rollback(plan)
        except Exception as exc:  # noqa: BLE001 - rollback é best-effort
            logger.error("Rollback do plano %s falhou: %s", plan.id, exc, exc_info=True)


def build_dimension_verifier(
    *,
    expected_key: str = "expected_dimensions_mm",
    measured_key: str = "dimensions_mm",
    tolerance_mm: float = 0.5,
) -> GeometryVerifier:
    """Builder de ``GeometryVerifier`` por comparação de dimensões (RF-012/013).

    Compara as dimensões **esperadas** (declaradas no passo em
    ``input_json[expected_key]``) com as **medidas** retornadas no output do
    read-back (``output[measured_key]``), por chave, com tolerância em mm.
    Retorna o dicionário de divergências (``{chave: {expected, measured, delta}}``)
    ou ``None`` quando conforme — ou quando não há dados de verificação.

    A lógica de comparação é independente do Fusion; os **valores medidos** só
    aparecem quando uma tool de read-back roda no Fusion real (gate do dono).
    """

    def verifier(step: ModelingPlanStep, output: dict[str, Any]) -> dict[str, Any] | None:
        expected = (step.input_json or {}).get(expected_key)
        measured = (output or {}).get(measured_key)

        def _diverged(exp: Any, meas: Any) -> bool:
            return (
                isinstance(exp, int | float)
                and isinstance(meas, int | float)
                and abs(float(exp) - float(meas)) > tolerance_mm
            )

        divergences: dict[str, Any] = {}
        # Formato lista [x, y, z] (o usado pelas tools de geometria): índice→eixo.
        if isinstance(expected, list | tuple) and isinstance(measured, list | tuple):
            for i in range(min(len(expected), len(measured), 3)):
                if _diverged(expected[i], measured[i]):
                    divergences[("x", "y", "z")[i]] = {
                        "expected": expected[i],
                        "measured": measured[i],
                        "delta": round(float(measured[i]) - float(expected[i]), 3),
                    }
            return divergences or None
        # Formato dict {chave: valor}.
        if not isinstance(expected, dict) or not isinstance(measured, dict):
            return None
        for key, exp in expected.items():
            if _diverged(exp, measured.get(key)):
                divergences[key] = {
                    "expected": exp,
                    "measured": measured.get(key),
                    "delta": round(float(measured.get(key)) - float(exp), 3),
                }
        return divergences or None

    return verifier


def run_plan_with_optional_loop(
    executor: ModelingExecutorService,
    planner: Any,
    plan: ModelingPlan,
) -> ModelingExecutionResult:
    """Executa um plano aprovado pelo loop agêntico OU pelo executor linear.

    Quando ``settings.modeling_agentic_loop_enabled`` está ligado (Fase 2), usa o
    ``ModelingAgentLoop`` (executa→inspeciona→corrige, teto 5, rollback ao esgotar)
    com o corretor LLM do planner; senão, o executor linear de sempre.

    Fonte ÚNICA da decisão loop×linear, compartilhada pelo
    ``ModelingChatOrchestrator`` (fluxo de chat) e pelo ``ModelingService``
    (card → ``POST /plans/{id}/execute``). Sem isto a flag só valia no fluxo de
    chat e o caminho do card executava SEMPRE linear — o loop não corrigia nada
    apesar de "ligado".
    """

    if settings.modeling_agentic_loop_enabled:
        loop = ModelingAgentLoop(
            executor,
            corrector=planner.build_corrector(),
            verifier=build_dimension_verifier(),
        )
        return loop.run(plan)
    return executor.execute_plan(plan)


__all__ = [
    "ModelingAgentLoop",
    "MAX_CORRECTION_ITERATIONS",
    "StepCorrector",
    "GeometryVerifier",
    "PlanRollback",
    "build_dimension_verifier",
    "run_plan_with_optional_loop",
]
