"""Compatibility wrapper for the baseline entity-resolution pipeline."""

from __future__ import annotations

from src.entity_resolution.run_baseline_pipeline import main as baseline_main


def main(argv: list[str] | None = None) -> int:
    return baseline_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
