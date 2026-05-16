"""Run the baseline entity-resolution pipeline end to end."""

from __future__ import annotations

import argparse

from src.entity_resolution.build_manual_review_queue import main as review_queue_main
from src.entity_resolution.build_training_dataset import main as dataset_main
from src.entity_resolution.evaluate_model import main as evaluate_main
from src.entity_resolution.predict_matches import main as predict_main
from src.entity_resolution.rule_baseline import main as rule_main
from src.entity_resolution.train_baseline_model import main as train_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run baseline entity-resolution pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Preview orchestrated steps only.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty state.")
    parser.add_argument("--limit", type=int, help="Optional row limit.")
    parser.add_argument("--log-mlflow", action="store_true", help="Log training metrics to MLflow.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "allow_empty": args.allow_empty,
                "limit": args.limit,
                "log_mlflow": args.log_mlflow,
                "steps": [
                    "build training dataset",
                    "run rule baseline",
                    "train logistic regression baseline",
                    "predict matches",
                    "evaluate model",
                    "build manual review queue",
                ],
            }
        )
        return 0

    shared = (["--allow-empty"] if args.allow_empty else []) + (
        ["--limit", str(args.limit)] if args.limit is not None else []
    )
    dataset_main(shared)
    rule_main(shared)
    train_main(shared + (["--log-mlflow"] if args.log_mlflow else []))
    predict_main(shared)
    evaluate_main(["--allow-empty"] if args.allow_empty else [])
    review_queue_main(["--allow-empty"] if args.allow_empty else [])
    print({"pipeline": "entity_resolution_baseline", "status": "ok"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
