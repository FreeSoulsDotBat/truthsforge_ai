from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    target = project_root / "apps" / "web" / "src" / "types" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAPI exported to {target}")


if __name__ == "__main__":
    main()
