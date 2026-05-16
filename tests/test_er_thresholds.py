from src.entity_resolution.thresholds import ThresholdPolicy, decision_from_probability


def test_threshold_policy_maps_probabilities_to_decisions() -> None:
    policy = ThresholdPolicy(
        auto_merge=0.95,
        manual_review_min=0.70,
        manual_review_max=0.95,
        no_merge=0.70,
    )

    assert decision_from_probability(0.97, policy) == "auto_merge"
    assert decision_from_probability(0.72, policy) == "manual_review"
    assert decision_from_probability(0.20, policy) == "no_merge"
