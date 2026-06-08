"""Validate that defense notebooks are present and parseable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.utils.config import project_root

NOTEBOOKS = (
    "notebooks/03_ml_research_defense_report.ipynb",
    "notebooks/04_live_demo_cases.ipynb",
    "notebooks/entity_resolution_training_report.ipynb",
)


def check_notebooks(root: Path | None = None) -> dict[str, Any]:
    resolved_root = root or project_root()
    items = []
    for relative_path in NOTEBOOKS:
        path = resolved_root / relative_path
        exists = path.exists()
        parseable = False
        cell_count = 0
        error = None
        if exists:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                cells = payload.get("cells") or []
                parseable = isinstance(cells, list)
                cell_count = len(cells) if parseable else 0
            except Exception as exc:
                error = str(exc)
        items.append(
            {
                "path": str(path),
                "exists": exists,
                "parseable": parseable,
                "cell_count": cell_count,
                "error": error,
            }
        )
    status = "ok" if all(item["exists"] and item["parseable"] for item in items) else "error"
    return {"status": status, "items": items}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check defense notebooks.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = check_notebooks()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Notebook check status: {result['status']}")
        for item in result["items"]:
            print(
                f"- {item['path']}: exists={item['exists']} "
                f"parseable={item['parseable']} cells={item['cell_count']}"
            )
            if item["error"]:
                print(f"  error: {item['error']}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
