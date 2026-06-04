# Presentations

## ML Defense Deck

- File: `game-intelligence-ml-defense.pptx`
- Purpose: editable 12-slide deck for the current ER-first ML research defense.
- Source narrative: `data/artifacts/reports/ml_defense_presentation/`.
- Rebuild command for source outline and speaker notes: `make ml-defense-presentation`.
- Full research rebuild command: `make ml-defense-all`.

The deck is generated from current project metrics and should be reviewed after every
major retraining or data expansion cycle.

The current source narrative is aligned with the read-only FastAPI demo endpoints:
`/stats/catalog`, `/stats/ml`, `/games/{game_id}/similar`, `/recommend`,
`/matches/review`, `/explain/recommendation`, and `/explain/match`.
