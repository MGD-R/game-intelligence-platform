# ML Defense Remaining Steps

This document tracks the remaining work after the current ML research readiness gate.

## Current Status

- The ER-first research package is ready for defense rehearsal.
- `make ml-defense-readiness` verifies required research artifacts and key metrics.
- `make ml-defense-presentation` builds a slide outline, speaker notes and remaining-step
  checklist from the readiness artifacts.
- `make ml-defense-all` rebuilds all research artifacts and then generates the presentation
  package.
- The first editable PPTX deck is available at
  `docs/presentations/game-intelligence-ml-defense.pptx`.

## Next Practical Step

Run a timed defense rehearsal using:

- `docs/presentations/game-intelligence-ml-defense.pptx`
- `data/artifacts/reports/ml_defense_presentation/ml_defense_presentation_outline.md`
- `data/artifacts/reports/ml_defense_presentation/ml_defense_slide_outline.csv`
- `data/artifacts/reports/ml_defense_presentation/ml_defense_speaker_notes.md`

Recommended deck structure:

1. Problem and research goal.
2. Data pipeline and corpus scale.
3. Manual review as supervision.
4. Explainable ER baseline.
5. Merge governance.
6. Graph risk analysis.
7. Lightweight title embeddings.
8. IGDB search lane.
9. Content-based recommendations.
10. Bayesian rating.
11. Grounded RAG explanations.
12. Conclusions and next research steps.

## Optional Research Extensions

- Neural multilingual embeddings for title/description matching.
- LLM rendering over grounded fact cards without giving the LLM decision authority.
- Additional IGDB search candidate calibration by query strategy and rank.
- Timed defense rehearsal and slide pruning for the target presentation duration.

## Release Workflow

After the final presentation materials are accepted:

1. Run `make ml-defense-all`.
2. Run code quality checks.
3. Merge `feature/igdb-search-lane` into `develop`.
4. Merge `develop` into `main` only after explicit confirmation.
