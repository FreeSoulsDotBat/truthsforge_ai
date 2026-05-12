"""Pure printability report builder for Fusion 360 body summaries.

This module deliberately has zero Fusion API dependencies so the Truth's Forge
backend can import and test it from outside the Fusion runtime. The add-in
collects raw measurements from each ``BRepBody`` and feeds a list of dicts
into :func:`compute_printability_report`.

Each body summary is expected to look like::

    {
        "name": "Body1",
        "volume_mm3": 8000.0,
        "surface_area_mm2": 2400.0,
        "is_solid": True,
        "bbox_min_mm": [0.0, 0.0, 0.0],
        "bbox_max_mm": [20.0, 20.0, 20.0],
        "downward_face_area_mm2": 400.0,   # area of faces with normal ≈ -Z
        "total_face_area_mm2": 2400.0,     # sum of all face areas
        "thin_face_area_mm2": 0.0,         # area of suspiciously tiny faces
    }

Missing keys are treated as zeros / absent. The heuristics intentionally err
on the side of *info*/*warning* rather than *error* so the report is advisory
and never blocks an export by itself; the user remains in the loop.
"""

from __future__ import annotations

from typing import Any, Iterable

# Severities — kept as plain strings to match the rest of the modeling envelopes.
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

# Weights when aggregating into the 0..1 risk_score.
SEVERITY_WEIGHTS = {SEVERITY_ERROR: 0.5, SEVERITY_WARNING: 0.2, SEVERITY_INFO: 0.05}

# Built-in checks the report can run; defaults to the full set when caller
# does not narrow it.
DEFAULT_CHECKS: tuple[str, ...] = (
    "volume",
    "is_solid",
    "bounding_box",
    "wall_thickness_approx",
    "overhang_approx",
    "thin_features",
)

# Per-printer profile thresholds. The "default" profile is a generic FDM
# slicer (Bambu X1C/PLA-ish); add profiles when needed without breaking the
# backend interface. Thresholds are deliberately conservative — we *warn*,
# we do not block.
PRINTER_PROFILES: dict[str, dict[str, float]] = {
    "default": {
        # mm: prints with the smallest dimension below this are flagged.
        "min_dimension_mm": 1.0,
        # mm: warns when implied wall thickness (volume/surface) drops below this.
        "min_wall_thickness_mm": 1.5,
        # 0..1: warns when downward-face area / total-face area exceeds this.
        "max_overhang_ratio": 0.25,
        # 0..1: warns when "thin face" area / total exceeds this.
        "max_thin_face_ratio": 0.05,
    },
    "bambu_x1c_pla": {
        "min_dimension_mm": 0.8,
        "min_wall_thickness_mm": 1.2,
        "max_overhang_ratio": 0.30,
        "max_thin_face_ratio": 0.05,
    },
}


def _profile(name: str | None) -> dict[str, float]:
    if name and name in PRINTER_PROFILES:
        return PRINTER_PROFILES[name]
    return PRINTER_PROFILES["default"]


def _checks_to_run(requested: Iterable[str] | None) -> set[str]:
    if not requested:
        return set(DEFAULT_CHECKS)
    return {check for check in requested if check in DEFAULT_CHECKS} or set(DEFAULT_CHECKS)


def _dimensions_mm(body: dict[str, Any]) -> tuple[float, float, float]:
    min_pt = body.get("bbox_min_mm") or [0.0, 0.0, 0.0]
    max_pt = body.get("bbox_max_mm") or [0.0, 0.0, 0.0]
    if not isinstance(min_pt, (list, tuple)) or not isinstance(max_pt, (list, tuple)):
        return (0.0, 0.0, 0.0)
    if len(min_pt) < 3 or len(max_pt) < 3:
        return (0.0, 0.0, 0.0)
    return (
        max(0.0, float(max_pt[0]) - float(min_pt[0])),
        max(0.0, float(max_pt[1]) - float(min_pt[1])),
        max(0.0, float(max_pt[2]) - float(min_pt[2])),
    )


def _issue(check: str, severity: str, message: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {"check": check, "severity": severity, "message": message, "detail": detail}


def _check_volume(body: dict[str, Any]) -> list[dict[str, Any]]:
    volume = float(body.get("volume_mm3") or 0.0)
    if volume <= 0.0:
        return [
            _issue(
                "volume",
                SEVERITY_ERROR,
                f"Volume não positivo em '{body.get('name')}'; corpo provavelmente aberto.",
                {"object": body.get("name"), "volume_mm3": volume},
            )
        ]
    return []


def _check_is_solid(body: dict[str, Any]) -> list[dict[str, Any]]:
    if body.get("is_solid") is False:
        return [
            _issue(
                "is_solid",
                SEVERITY_ERROR,
                f"'{body.get('name')}' não é um sólido fechado — não é printável diretamente.",
                {"object": body.get("name")},
            )
        ]
    return []


def _check_bounding_box(body: dict[str, Any], profile: dict[str, float]) -> list[dict[str, Any]]:
    dx, dy, dz = _dimensions_mm(body)
    issues: list[dict[str, Any]] = []
    smallest = min((d for d in (dx, dy, dz) if d > 0.0), default=0.0)
    if smallest and smallest < profile["min_dimension_mm"]:
        issues.append(
            _issue(
                "bounding_box",
                SEVERITY_WARNING,
                (
                    f"Menor dimensão de '{body.get('name')}' é {smallest:.2f} mm; "
                    f"abaixo de {profile['min_dimension_mm']} mm pode falhar na impressão."
                ),
                {"object": body.get("name"), "smallest_dim_mm": smallest},
            )
        )
    return issues


def _check_wall_thickness(
    body: dict[str, Any], profile: dict[str, float]
) -> list[dict[str, Any]]:
    volume = float(body.get("volume_mm3") or 0.0)
    surface = float(body.get("surface_area_mm2") or 0.0)
    if volume <= 0.0 or surface <= 0.0:
        return []
    # Implied wall thickness ≈ 2 * volume / surface (twice the volume-over-surface ratio).
    implied = (2.0 * volume) / surface
    if implied < profile["min_wall_thickness_mm"]:
        return [
            _issue(
                "wall_thickness_approx",
                SEVERITY_WARNING,
                (
                    f"Espessura implícita de '{body.get('name')}' ≈ {implied:.2f} mm; "
                    f"abaixo de {profile['min_wall_thickness_mm']} mm pode fraquear."
                ),
                {
                    "object": body.get("name"),
                    "implied_wall_thickness_mm": implied,
                    "volume_mm3": volume,
                    "surface_area_mm2": surface,
                },
            )
        ]
    return []


def _check_overhang(body: dict[str, Any], profile: dict[str, float]) -> list[dict[str, Any]]:
    downward = float(body.get("downward_face_area_mm2") or 0.0)
    total = float(body.get("total_face_area_mm2") or body.get("surface_area_mm2") or 0.0)
    if total <= 0.0:
        return []
    ratio = downward / total
    if ratio > profile["max_overhang_ratio"]:
        return [
            _issue(
                "overhang_approx",
                SEVERITY_INFO,
                (
                    f"'{body.get('name')}' tem {ratio * 100:.0f}% de área voltada pra baixo; "
                    "pode precisar de suporte."
                ),
                {
                    "object": body.get("name"),
                    "downward_ratio": ratio,
                    "downward_area_mm2": downward,
                    "total_face_area_mm2": total,
                },
            )
        ]
    return []


def _check_thin_features(
    body: dict[str, Any], profile: dict[str, float]
) -> list[dict[str, Any]]:
    thin = float(body.get("thin_face_area_mm2") or 0.0)
    total = float(body.get("total_face_area_mm2") or body.get("surface_area_mm2") or 0.0)
    if total <= 0.0 or thin <= 0.0:
        return []
    ratio = thin / total
    if ratio > profile["max_thin_face_ratio"]:
        return [
            _issue(
                "thin_features",
                SEVERITY_INFO,
                (
                    f"'{body.get('name')}' tem {ratio * 100:.0f}% de área em faces muito "
                    "pequenas; possível parede ou aresta fina."
                ),
                {
                    "object": body.get("name"),
                    "thin_ratio": ratio,
                    "thin_face_area_mm2": thin,
                    "total_face_area_mm2": total,
                },
            )
        ]
    return []


_CHECK_RUNNERS = {
    "volume": _check_volume,
    "is_solid": _check_is_solid,
    "bounding_box": _check_bounding_box,
    "wall_thickness_approx": _check_wall_thickness,
    "overhang_approx": _check_overhang,
    "thin_features": _check_thin_features,
}


def compute_printability_report(
    bodies: list[dict[str, Any]],
    *,
    checks: Iterable[str] | None = None,
    printer_profile: str | None = None,
) -> dict[str, Any]:
    """Return a report compatible with the ``ModelingPrintabilityReport`` shape."""
    selected_checks = _checks_to_run(checks)
    profile = _profile(printer_profile)
    issues: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, Any]] = {}

    for body in bodies:
        name = str(body.get("name") or "Body")
        dims = _dimensions_mm(body)
        metrics[name] = {
            "volume_mm3": float(body.get("volume_mm3") or 0.0),
            "surface_area_mm2": float(body.get("surface_area_mm2") or 0.0),
            "dimensions_mm": list(dims),
            "is_solid": bool(body.get("is_solid", True)),
        }
        for check in selected_checks:
            runner = _CHECK_RUNNERS[check]
            if check in {"volume", "is_solid"}:
                produced = runner(body)
            else:
                produced = runner(body, profile)  # type: ignore[arg-type]
            issues.extend(produced)

    risk_score = min(
        1.0, sum(SEVERITY_WEIGHTS.get(issue["severity"], 0.05) for issue in issues)
    )
    return {
        "message": (
            f"Printability validada em {len(bodies)} corpo(s); "
            f"{len(issues)} aviso(s) registrado(s)."
        ),
        "objects_inspected": len(bodies),
        "checks_executed": sorted(selected_checks),
        "issues": issues,
        "metrics": metrics,
        "risk_score": round(risk_score, 3),
        "printer_profile": printer_profile,
    }
