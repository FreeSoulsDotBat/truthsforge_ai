"""Tests for the Fusion printability calculator.

The pure-Python module lives under ``apps/fusion-addin/printability_logic.py``
so the add-in (running inside Fusion's embedded Python) can use it without
depending on the backend. The test injects the add-in directory into
``sys.path`` so we can import and verify the heuristics from CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ADDIN_DIR = Path(__file__).resolve().parents[2] / "apps" / "fusion-addin"
sys.path.insert(0, str(ADDIN_DIR))

import printability_logic  # noqa: E402

# Re-export for clarity in assertions.
SEVERITY_INFO = printability_logic.SEVERITY_INFO
SEVERITY_WARNING = printability_logic.SEVERITY_WARNING
SEVERITY_ERROR = printability_logic.SEVERITY_ERROR


def _healthy_cube() -> dict[str, float]:
    return {
        "name": "Cube",
        "is_solid": True,
        "volume_mm3": 8000.0,
        "surface_area_mm2": 2400.0,
        "bbox_min_mm": [0.0, 0.0, 0.0],
        "bbox_max_mm": [20.0, 20.0, 20.0],
        "downward_face_area_mm2": 400.0,
        "total_face_area_mm2": 2400.0,
        "thin_face_area_mm2": 0.0,
    }


def test_healthy_cube_produces_no_issues() -> None:
    report = printability_logic.compute_printability_report([_healthy_cube()])
    assert report["objects_inspected"] == 1
    assert report["issues"] == []
    assert report["risk_score"] == 0.0
    assert report["printer_profile"] is None
    assert "Cube" in report["metrics"]


def test_open_body_is_flagged_as_error() -> None:
    body = _healthy_cube() | {"name": "Open", "is_solid": False}
    report = printability_logic.compute_printability_report([body])
    error_codes = {
        issue["check"] for issue in report["issues"] if issue["severity"] == SEVERITY_ERROR
    }
    assert "is_solid" in error_codes
    assert report["risk_score"] >= printability_logic.SEVERITY_WEIGHTS[SEVERITY_ERROR]


def test_non_positive_volume_is_error() -> None:
    body = _healthy_cube() | {"name": "Hollow", "volume_mm3": 0.0}
    report = printability_logic.compute_printability_report([body])
    assert any(
        issue["check"] == "volume" and issue["severity"] == SEVERITY_ERROR
        for issue in report["issues"]
    )


def test_tiny_dimensions_flagged_as_warning() -> None:
    body = _healthy_cube() | {
        "name": "Tiny",
        "bbox_min_mm": [0.0, 0.0, 0.0],
        "bbox_max_mm": [10.0, 10.0, 0.5],  # smallest dim = 0.5 mm
    }
    report = printability_logic.compute_printability_report([body])
    bbox_issues = [issue for issue in report["issues"] if issue["check"] == "bounding_box"]
    assert bbox_issues, "expected bounding_box warning for sub-mm dimension"
    assert bbox_issues[0]["severity"] == SEVERITY_WARNING


def test_thin_walls_flagged_as_warning() -> None:
    # A spherical shell: large surface, tiny volume → implied thickness very small.
    body = _healthy_cube() | {
        "name": "Shell",
        "volume_mm3": 500.0,
        "surface_area_mm2": 5000.0,  # implied wall ≈ 2*500/5000 = 0.2 mm
    }
    report = printability_logic.compute_printability_report([body])
    thin_issues = [issue for issue in report["issues"] if issue["check"] == "wall_thickness_approx"]
    assert thin_issues
    assert thin_issues[0]["severity"] == SEVERITY_WARNING
    detail = thin_issues[0]["detail"]
    assert pytest.approx(detail["implied_wall_thickness_mm"], rel=1e-3) == 0.2


def test_high_overhang_ratio_flagged_as_info() -> None:
    body = _healthy_cube() | {
        "name": "Overhang",
        "downward_face_area_mm2": 1500.0,  # 62% of total — well above default 25%
    }
    report = printability_logic.compute_printability_report([body])
    overhang_issues = [issue for issue in report["issues"] if issue["check"] == "overhang_approx"]
    assert overhang_issues
    assert overhang_issues[0]["severity"] == SEVERITY_INFO


def test_thin_features_flagged_as_info() -> None:
    body = _healthy_cube() | {
        "name": "Detail",
        "thin_face_area_mm2": 300.0,  # 12.5% of total — above default 5%
    }
    report = printability_logic.compute_printability_report([body])
    thin_issues = [issue for issue in report["issues"] if issue["check"] == "thin_features"]
    assert thin_issues
    assert thin_issues[0]["severity"] == SEVERITY_INFO


def test_only_requested_checks_run() -> None:
    body = _healthy_cube() | {
        "name": "Multi",
        "is_solid": False,
        "volume_mm3": 0.0,
        "downward_face_area_mm2": 2000.0,
    }
    report = printability_logic.compute_printability_report([body], checks=["is_solid"])
    checks_seen = {issue["check"] for issue in report["issues"]}
    assert checks_seen == {"is_solid"}
    assert report["checks_executed"] == ["is_solid"]


def test_unknown_checks_fall_back_to_default_set() -> None:
    report = printability_logic.compute_printability_report(
        [_healthy_cube()], checks=["does_not_exist", "also_invalid"]
    )
    assert set(report["checks_executed"]) == set(printability_logic.DEFAULT_CHECKS)


def test_printer_profile_changes_threshold() -> None:
    # Implied wall = 1.4 mm: triggers warning under "default" (min 1.5),
    # but is fine under "bambu_x1c_pla" (min 1.2).
    body = _healthy_cube() | {
        "name": "Borderline",
        "volume_mm3": 700.0,
        "surface_area_mm2": 1000.0,
    }
    default_report = printability_logic.compute_printability_report([body])
    bambu_report = printability_logic.compute_printability_report(
        [body], printer_profile="bambu_x1c_pla"
    )
    default_wall = [
        issue for issue in default_report["issues"] if issue["check"] == "wall_thickness_approx"
    ]
    bambu_wall = [
        issue for issue in bambu_report["issues"] if issue["check"] == "wall_thickness_approx"
    ]
    assert default_wall, "default profile should warn on 1.4 mm wall"
    assert not bambu_wall, "bambu profile (min 1.2 mm) should accept 1.4 mm"
    assert bambu_report["printer_profile"] == "bambu_x1c_pla"


def test_risk_score_saturates_at_one() -> None:
    body = _healthy_cube() | {
        "name": "Terrible",
        "is_solid": False,
        "volume_mm3": 0.0,
        "downward_face_area_mm2": 2000.0,
        "thin_face_area_mm2": 800.0,
        "bbox_min_mm": [0.0, 0.0, 0.0],
        "bbox_max_mm": [10.0, 10.0, 0.2],
    }
    # Two bodies to push the score up further.
    report = printability_logic.compute_printability_report([body, body])
    assert report["risk_score"] == 1.0


def test_metrics_include_dimensions_and_volume() -> None:
    report = printability_logic.compute_printability_report([_healthy_cube()])
    cube_metrics = report["metrics"]["Cube"]
    assert cube_metrics["volume_mm3"] == 8000.0
    assert cube_metrics["surface_area_mm2"] == 2400.0
    assert cube_metrics["dimensions_mm"] == [20.0, 20.0, 20.0]
    assert cube_metrics["is_solid"] is True


def test_empty_bodies_produces_empty_report() -> None:
    report = printability_logic.compute_printability_report([])
    assert report["objects_inspected"] == 0
    assert report["issues"] == []
    assert report["risk_score"] == 0.0
