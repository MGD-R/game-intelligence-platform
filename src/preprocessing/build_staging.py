"""Placeholder CLI for staging build steps."""

from __future__ import annotations

import argparse


def build_staging(demo: bool = False) -> str:
    if demo:
        return "TODO: generate demo staging data after ingestion is available."
    return "TODO: build staging tables after ingestion is available."


def main() -> int:
    parser = argparse.ArgumentParser(description="Staging placeholder runner")
    parser.add_argument("--demo", action="store_true", help="Print the demo-data placeholder path.")
    args = parser.parse_args()
    print(build_staging(demo=args.demo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
