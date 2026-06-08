"""Build grounded RAG explanation artifacts."""

from __future__ import annotations

from src.rag.build_explanations import main as build_explanations_main


def main(argv: list[str] | None = None) -> int:
    return build_explanations_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
