"""Threshold policy helpers for entity-resolution predictions."""

from __future__ import annotations

from dataclasses import dataclass

from src.entity_resolution.io import load_entity_resolution_config


@dataclass(frozen=True, slots=True)
class ThresholdPolicy:
    auto_merge: float
    manual_review_min: float
    manual_review_max: float
    no_merge: float


def load_threshold_policy() -> ThresholdPolicy:
    thresholds = load_entity_resolution_config().get("thresholds", {})
    return ThresholdPolicy(
        auto_merge=float(thresholds.get("auto_merge", 0.95)),
        manual_review_min=float(thresholds.get("manual_review_min", 0.70)),
        manual_review_max=float(thresholds.get("manual_review_max", 0.95)),
        no_merge=float(thresholds.get("no_merge", 0.70)),
    )


def decision_from_probability(probability: float, policy: ThresholdPolicy | None = None) -> str:
    policy = policy or load_threshold_policy()
    if probability >= policy.auto_merge:
        return "auto_merge"
    if policy.manual_review_min <= probability < policy.manual_review_max:
        return "manual_review"
    return "no_merge"
