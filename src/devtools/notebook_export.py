"""Export defense notebooks to HTML for offline presentation backup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.devtools.notebook_check import NOTEBOOKS
from src.utils.config import project_root

DEFAULT_OUTPUT_DIR = project_root() / "data" / "artifacts" / "reports" / "notebooks_html"


def export_notebooks(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    try:
        from nbconvert import HTMLExporter
    except Exception as exc:
        return {
            "status": "error",
            "error": f"nbconvert is not available: {exc}",
            "recommendation": "Run through the notebook profile or install `nbconvert`.",
            "items": [],
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    exporter = HTMLExporter()
    items = []
    root = project_root()
    for relative_path in NOTEBOOKS:
        notebook_path = root / relative_path
        if not notebook_path.exists():
            items.append({"notebook": relative_path, "exported": False, "error": "missing"})
            continue
        try:
            html, _resources = exporter.from_filename(str(notebook_path))
            output_path = output_dir / f"{notebook_path.stem}.html"
            output_path.write_text(html, encoding="utf-8")
            items.append(
                {
                    "notebook": relative_path,
                    "exported": True,
                    "output_path": str(output_path),
                }
            )
        except Exception as exc:
            items.append({"notebook": relative_path, "exported": False, "error": str(exc)})
    status = "ok" if all(item["exported"] for item in items) else "warning"
    return {"status": status, "output_dir": str(output_dir), "items": items}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export defense notebooks to HTML.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = export_notebooks(args.output_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Notebook export status: {result['status']}")
        if result.get("error"):
            print(result["error"])
            print(result.get("recommendation", ""))
        for item in result.get("items", []):
            print(f"- {item['notebook']}: exported={item['exported']}")
    return 0 if result["status"] in {"ok", "warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
