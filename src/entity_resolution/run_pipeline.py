"""Placeholder CLI for entity resolution pipeline."""

from __future__ import annotations

from src.entity_resolution.blocking import default_blocking_strategy
from src.entity_resolution.features import feature_catalog


def main() -> int:
    print("Blocking strategy:", default_blocking_strategy())
    print("Planned features:", ", ".join(feature_catalog()))
    print("TODO: implement baseline ER rules and logistic regression in a later branch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
