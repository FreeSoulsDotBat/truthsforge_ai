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

import asyncio
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
from app.modeling.executor import ModelingExecutorService, inner_fusion_payload
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
            # Computa a divergência geométrica UMA vez por iteração e reaproveita
            # tanto na condição de correção quanto no payload do corretor (o
            # verifier desempacota o envelope + json.loads; rodá-lo 2x por passo
            # é desperdício no caminho quente do loop).
            divergence = self._compute_divergence(current, outcome)
            while (not outcome.ok or bool(divergence)) and attempt < self.max_iterations:
                attempt += 1
                # Tool OK mas geometria divergente (verifier): injeta a
                # divergência no output p/ o corretor enxergar (o
                # build_correction_context formata "esperado × medido").
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
                divergence = self._compute_divergence(current, outcome)

            executed_step_ids.append(step.id)
            suffix = f" (após {attempt} correção(ões))" if attempt else ""
            events.append(outcome.event + suffix)
            if outcome.tool_call_id is not None:
                tool_call_ids.append(outcome.tool_call_id)
            next_steps.append(outcome.step)

            if not outcome.ok or bool(divergence):
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

    def _compute_divergence(
        self, step: ModelingPlanStep, outcome: Any
    ) -> dict[str, Any] | None:
        """Divergência geométrica (read-back esperado × medido) ou ``None``.

        Só roda o verifier quando a tool teve sucesso (em falha de tool a
        correção já dispara por ``outcome.ok``) e quando há verifier injetado —
        depende do Fusion real (gate do dono). O resultado é reaproveitado na
        condição do loop e no payload do corretor (evita rodar o verifier 2x)."""

        if not outcome.ok or self.verifier is None:
            return None
        return self.verifier(step, outcome.output)

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
        # As tools fusion devolvem o read-back dentro do envelope HTTP (JSON
        # stringificado); sem desempacotar, ``dimensions_mm`` nunca aparecia e o
        # verifier ficava mudo no Fusion real. ``inner_fusion_payload`` cai no
        # formato direto p/ mock/in_process/testes.
        measured = (inner_fusion_payload(output) or {}).get(measured_key)

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


def build_surface_verifier(
    *,
    area_tolerance_mm2: float = 5.0,
) -> GeometryVerifier:
    """Builder de ``GeometryVerifier`` para superfícies (Fase 5 T5.3b).

    Compara o que o passo **declarou esperar** com o read-back:
    - ``expected_surface_area_mm2`` (escalar) × ``surface_area_mm2`` (medido).
    - ``expected_is_closed`` (bool) × ``is_closed`` (medido) — útil antes do
      ``thicken_surface``: se o stitch deixou aresta livre, o thicken
      simétrico falha. O verifier reage e o corretor pode aumentar a
      tolerância do stitch ou inserir um patch.

    No-op quando o passo não declara nenhum dos dois campos (backward-compat
    com planos antigos que só usam ``expected_dimensions_mm``).
    """

    def verifier(step: ModelingPlanStep, output: dict[str, Any]) -> dict[str, Any] | None:
        input_json = step.input_json or {}
        payload = inner_fusion_payload(output) or {}
        divergences: dict[str, Any] = {}

        expected_area = input_json.get("expected_surface_area_mm2")
        measured_area = payload.get("surface_area_mm2")
        if (
            isinstance(expected_area, int | float)
            and isinstance(measured_area, int | float)
            and abs(float(measured_area) - float(expected_area)) > area_tolerance_mm2
        ):
            divergences["surface_area_mm2"] = {
                "expected": expected_area,
                "measured": measured_area,
                "delta": round(float(measured_area) - float(expected_area), 3),
            }

        expected_closed = input_json.get("expected_is_closed")
        measured_closed = payload.get("is_closed")
        if (
            isinstance(expected_closed, bool)
            and isinstance(measured_closed, bool)
            and expected_closed != measured_closed
        ):
            divergences["is_closed"] = {
                "expected": expected_closed,
                "measured": measured_closed,
                # mensagem semantica pro corretor: dificil reagir só com bool.
                "hint": (
                    "Body ficou aberto (provavel gap na costura). "
                    "Aumente tolerance_mm do stitch, adicione patch nas "
                    "arestas livres (query_geometry → free_edges) ou refaca "
                    "a casca."
                    if expected_closed
                    else "Body ficou fechado quando esperado aberto."
                ),
            }
        return divergences or None

    return verifier


def combine_verifiers(*verifiers: GeometryVerifier) -> GeometryVerifier:
    """Combina múltiplos verifiers em um só, agregando divergências (Fase 5).

    Cada verifier roda independente; divergências de todos são mescladas no
    payload final passado ao corretor. Verifiers None são ignorados.
    """

    actives: list[GeometryVerifier] = [v for v in verifiers if v is not None]

    def verifier(step: ModelingPlanStep, output: dict[str, Any]) -> dict[str, Any] | None:
        merged: dict[str, Any] = {}
        for v in actives:
            div = v(step, output)
            if div:
                merged.update(div)
        return merged or None

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

    Caminho SÍNCRONO por contrato: o corretor LLM despacha via ``asyncio.run``
    (``planner.correct_step``), que estoura ``RuntimeError`` se houver event loop
    ativo na thread. Os call sites atuais rodam fora do loop (rotas ``def`` em
    threadpool; chat via ``asyncio.to_thread``). Falhamos cedo e com mensagem
    clara caso um chamador async invoque isto direto — em vez de o corretor
    engolir o erro e abortar o plano sem motivo aparente (mdl-exec-7).
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass  # sem loop ativo: caminho síncrono esperado.
    else:
        raise RuntimeError(
            "run_plan_with_optional_loop deve ser chamado fora de um event loop "
            "ativo (o corretor usa asyncio.run); despache via asyncio.to_thread."
        )

    if settings.modeling_agentic_loop_enabled:
        loop = ModelingAgentLoop(
            executor,
            corrector=planner.build_corrector(),
            # T5.3b (Fase 5): verifier combinado (dimensoes + superficie).
            # Step que declarar apenas expected_dimensions_mm continua tendo
            # comportamento legado; quem declarar expected_surface_area_mm2
            # ou expected_is_closed ganha o check adicional sem precisar
            # mudar o caminho do loop.
            verifier=combine_verifiers(
                build_dimension_verifier(),
                build_surface_verifier(),
            ),
        )
        result = loop.run(plan)
    else:
        result = executor.execute_plan(plan)
    executed_plan = getattr(result, "plan", None) or plan
    # A correção visual (quando ligada) pode rodar replan + re-execução e mudar
    # a geometria/persistir novos planos. Roda ANTES da captura do model_state
    # para o read-back refletir o estado pós-correção, não o anterior.
    _maybe_visual_correction(executor, planner, executed_plan)
    _maybe_capture_model_state(executor, executed_plan)
    # F8 (Sub3.2): auto-crítica GEOMÉTRICA após a captura do estado. Roda DEPOIS
    # do model_state (precisa do read-back fresco) e é o feedback primário. Quando
    # o visual está ON, a visão entra aqui como achado semântico (não atua).
    # Best-effort, flag OFF, **só reporta**.
    _maybe_evaluate_verdict(executor, planner, executed_plan)
    # F8: SURFAÇA o veredito ao usuário. O sistema não deve reportar "finalizado"
    # limpo quando a auto-crítica detecta divergência (corpos a mais/órfãos/
    # interferência) — era a queixa "diz que finalizou mas montou errado". Só
    # REPORTA (não replaneja); o aviso entra nos events que o chat mostra.
    result = _attach_verdict_notice(result, executed_plan)
    # Recarrega o plano da store para que o result devolvido ao chamador
    # (trace/audit/frontend) reflita o estado final real após correção visual e
    # captura de model_state, em vez do snapshot stale de antes dessas etapas.
    refreshed = _reload_plan(executor, executed_plan)
    if refreshed is not None and refreshed is not result.plan:
        result = result.model_copy(update={"plan": refreshed})
    return result


_VERDICT_HEAD = {
    "incomplete": "⚠️ Faltou algo no modelo",
    "diverged": "⚠️ O modelo divergiu do pedido",
    "broken": "⛔ Modelo inconsistente",
}


def _attach_verdict_notice(
    result: ModelingExecutionResult, plan: ModelingPlan
) -> ModelingExecutionResult:
    """Anexa um aviso aos ``events`` quando a auto-crítica geométrica reprovou.

    Honestidade: se o veredito (F8) viu corpos a mais/órfãos/interferência, o
    usuário precisa SABER — não basta o chat dizer "finalizado". Report-only; não
    altera status nem dispara replan. No-op quando não há veredito ou ele é ``ok``
    (flag de auto-crítica OFF = sem veredito = comportamento idêntico ao anterior)."""

    verdict = getattr(plan, "model_verdict", None)
    if verdict is None or verdict.overall == "ok":
        return result
    issues = [f.detail for f in verdict.findings if f.kind in ("missing", "excess", "wrong")]
    if not issues:
        return result
    head = _VERDICT_HEAD.get(verdict.overall, "⚠️ Atenção")
    notice = f"{head}: " + "; ".join(issues[:5])
    events = list(getattr(result, "events", []) or [])
    events.append(notice)
    return result.model_copy(update={"events": events})


def _reload_plan(
    executor: ModelingExecutorService, plan: ModelingPlan
) -> ModelingPlan | None:
    """Recarrega o plano da store (best-effort); ``None`` se indisponível."""

    store = getattr(executor, "store", None)
    if store is None or not hasattr(store, "get_modeling_plan"):
        return None
    try:
        return store.get_modeling_plan(plan.id)
    except Exception as exc:  # noqa: BLE001 - recarga é best-effort
        logger.debug("recarga do plano %s pós-execução falhou: %s", plan.id, exc)
        return None


def _maybe_visual_correction(
    executor: ModelingExecutorService, planner: Any, plan: ModelingPlan
) -> None:
    """Passo 3 do motor genérico: render → crítica visual → replan corretivo.

    Best-effort, atrás de ``modeling_visual_verification_enabled`` (default OFF).
    Render só existe no Fusion real; nunca propaga erro.

    F8: quando a auto-crítica GEOMÉTRICA está ligada, só o REPLAN destrutivo do
    visual se aposenta (ADR-023). A PERCEPÇÃO visual continua — mas via
    ``_maybe_evaluate_verdict`` → ``assess_visual_findings``, entrando no veredito
    como achado ``source='semantic'`` (um veredito, duas percepções), sem recriar
    corpos. Evita a duplicação (``BoxOuter (1)``/``Lid (2)``) mantendo o olho da
    visão no jogo."""

    if not settings.modeling_visual_verification_enabled:
        return
    if not settings.modeling_visual_autocorrect_enabled:
        # Default SEGURO: o replan visual que RECRIA corpos (BoxOuter_fixed/
        # Lid (1) — a duplicação quando a visão alucina) é opt-in explícito. Sem
        # ele, a verificação fica com a auto-crítica geométrica (F8) + a visão
        # como achado semântico do veredito. Mata o footgun de reaproveitar a env
        # do gate F7 (visual ON) e ver corpos duplicados.
        logger.info(
            "replan visual destrutivo desligado (default seguro; opt-in via "
            "modeling_visual_autocorrect_enabled). Use a auto-crítica geométrica (F8)."
        )
        return
    if settings.modeling_self_critique_enabled:
        logger.info(
            "replan visual ignorado: auto-crítica geométrica (F8) é primária; a "
            "visão entra como achado semântico no veredito, sem replan destrutivo."
        )
        return
    try:
        from app.modeling.visual_critique import run_visual_correction

        run_visual_correction(executor, planner, plan)
    except Exception:  # noqa: BLE001 - verificação visual nunca derruba o plano
        logger.warning("verificação visual falhou", exc_info=True)


def _maybe_visual_findings(
    executor: ModelingExecutorService, planner: Any, plan: ModelingPlan
) -> list[Any]:
    """F8: percepção visual como ENTRADA do veredito (``source='semantic'``), não
    como atuador. ``[]`` quando o visual está OFF ou a visão aprova. Best-effort —
    nunca derruba a avaliação."""

    if not settings.modeling_visual_verification_enabled:
        return []
    try:
        from app.modeling.visual_critique import assess_visual_findings

        return assess_visual_findings(executor, planner, plan)
    except Exception:  # noqa: BLE001 - visão é observabilidade, best-effort
        logger.debug("percepção visual (verdict input) falhou", exc_info=True)
        return []


def _maybe_evaluate_verdict(
    executor: ModelingExecutorService, planner: Any, plan: ModelingPlan
) -> None:
    """F8 Sub3.2: deriva o ``IntentSpec`` do plano + agrega o histórico de
    proveniência (Sub2) + o ``model_state`` read-back e produz um ``ModelVerdict``
    determinístico (faltou/demais/errado/certo). Persiste em ``plan.model_verdict``
    + trace; entra no contexto do próximo bloco via ``render_verdict_block``.

    Quando o visual está ligado, a crítica VISUAL entra AQUI como achado
    ``source='semantic'`` (um veredito, duas percepções) — sem replan destrutivo.

    **INVARIANTE: só REPORTA** — não dispara replan nem correção. Best-effort,
    atrás de ``modeling_self_critique_enabled`` (default OFF) — com OFF é no-op
    total (zero regressão)."""

    if not settings.modeling_self_critique_enabled:
        return
    try:
        from app.modeling.intent_spec import intent_from_plan
        from app.modeling.model_critique import build_model_verdict
        from app.modeling.provenance import history_from_plan

        intent = intent_from_plan(plan)
        history = history_from_plan(plan)
        semantic = _maybe_visual_findings(executor, planner, plan)
        verdict = build_model_verdict(
            intent, history, plan.model_state, semantic_findings=semantic
        )
        plan.model_verdict = verdict
        store = getattr(executor, "store", None)
        if store is not None and hasattr(store, "upsert_modeling_plan"):
            store.upsert_modeling_plan(plan)
        executor._tracer.record(
            "agent_loop.verdict",
            source=ModelingTraceSource.backend,
            level=(ModelingTraceLevel.warn if verdict.overall != "ok" else ModelingTraceLevel.info),
            message=f"Auto-crítica: {verdict.summary}",
            payload={
                "plan_id": plan.id,
                "overall": verdict.overall,
                "findings": len(verdict.findings),
                "semantic_findings": len(semantic),
                "expected_body_count": intent.expected_body_count,
                "deterministic_complete": verdict.deterministic_complete,
            },
            plan_id=plan.id,
        )
    except Exception as exc:  # noqa: BLE001 - auto-crítica é observabilidade
        logger.debug("auto-crítica (model_verdict) falhou: %s", exc)


def _maybe_capture_model_state(executor: ModelingExecutorService, plan: ModelingPlan) -> None:
    """F1 (T1.6): captura o ModelState pós-execução (read-back) e persiste em
    ``plan.model_state``, para o planner ter o estado geométrico real no próximo
    bloco/edição. Best-effort — nunca propaga (1 probe read-only extra por
    plano, só para fusion com geometria)."""

    try:
        from app.modeling.model_state import capture_model_state

        state = capture_model_state(executor, plan)
        if state is None:
            return
        plan.model_state = state
        store = getattr(executor, "store", None)
        if store is not None and hasattr(store, "upsert_modeling_plan"):
            store.upsert_modeling_plan(plan)
    except Exception as exc:  # noqa: BLE001 - captura é best-effort
        logger.debug("model_state capture pós-execução falhou: %s", exc)


__all__ = [
    "ModelingAgentLoop",
    "MAX_CORRECTION_ITERATIONS",
    "StepCorrector",
    "GeometryVerifier",
    "PlanRollback",
    "build_dimension_verifier",
    "build_surface_verifier",
    "combine_verifiers",
    "run_plan_with_optional_loop",
]
