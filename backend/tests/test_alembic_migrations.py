"""Smoke tests for the Alembic configuration introduced in Onda 1.4.

We don't run the migrations against a live Postgres here (the test suite
runs against the JSON dev store), but we do guarantee that the Alembic
config is loadable and that the revision graph is well-formed.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    return cfg


def test_alembic_ini_is_loadable() -> None:
    cfg = _alembic_config()
    assert cfg.get_main_option("script_location") is not None


def test_revision_graph_is_linear_001_to_004() -> None:
    cfg = _alembic_config()
    scripts = ScriptDirectory.from_config(cfg)
    revisions = {rev.revision: rev for rev in scripts.walk_revisions()}
    assert "001_initial_baseline" in revisions
    assert "002_chats_title_not_null" in revisions
    assert "003_chats_modeling_fields" in revisions
    assert "004_modeling_plans_kind" in revisions
    head = scripts.get_current_head()
    assert head == "004_modeling_plans_kind"
    assert revisions["002_chats_title_not_null"].down_revision == "001_initial_baseline"
    assert revisions["003_chats_modeling_fields"].down_revision == "002_chats_title_not_null"
    assert revisions["004_modeling_plans_kind"].down_revision == "003_chats_modeling_fields"


def test_initial_baseline_includes_modeling_plans_table() -> None:
    backend_root = Path(__file__).resolve().parent.parent
    script_path = backend_root / "migrations" / "versions" / "001_initial_baseline.py"
    body = script_path.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS modeling_plans" in body
    assert "CREATE TABLE IF NOT EXISTS modeling_snapshots" in body
    assert "idx_modeling_tool_calls_plan" in body


def test_chats_title_backfill_targets_blank_or_missing_titles() -> None:
    backend_root = Path(__file__).resolve().parent.parent
    script_path = backend_root / "migrations" / "versions" / "002_chats_title_not_null.py"
    body = script_path.read_text(encoding="utf-8")
    # The backfill must hit BOTH the rows that are missing the title key
    # entirely and the rows where the title is blank/whitespace.
    assert "payload->'title' IS NULL" in body
    assert "btrim(coalesce(payload->>'title', '')) = ''" in body
    assert "Sem título" in body


def test_chats_modeling_fields_creates_three_indexes() -> None:
    backend_root = Path(__file__).resolve().parent.parent
    script_path = backend_root / "migrations" / "versions" / "003_chats_modeling_fields.py"
    body = script_path.read_text(encoding="utf-8")
    assert "idx_chat_sessions_modeling_3d" in body
    assert "idx_chat_sessions_modeling_stage" in body
    assert "idx_chat_sessions_modeling_plan" in body


def test_modeling_plans_kind_creates_two_indexes() -> None:
    backend_root = Path(__file__).resolve().parent.parent
    script_path = backend_root / "migrations" / "versions" / "004_modeling_plans_kind.py"
    body = script_path.read_text(encoding="utf-8")
    assert "idx_modeling_plans_kind" in body
    assert "idx_modeling_plans_parent" in body
