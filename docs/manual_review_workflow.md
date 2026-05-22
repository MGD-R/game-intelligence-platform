# Entity Resolution Manual Review Workflow

Manual review labels are stored in PostgreSQL, not in generated parquet or CSV artifacts.

## Database Objects

- `ml.entity_resolution_manual_reviews`: editable manual labels.
- `ml.v_entity_resolution_review_candidates`: joined review context for all candidate pairs.
- `ml.v_igdb_manual_review_queue`: IGDB-focused queue ordered by review priority.

The manual column to fill is `review_label`:

- `TRUE`: both source records describe the same game and can be merged.
- `FALSE`: records describe different games and must not be merged.
- `NULL`: not reviewed yet or uncertain.

When a row is reviewed, also set `review_status = 'reviewed'` and `reviewed_at = NOW()`.
Use `review_status = 'unsure'` when the pair needs later investigation and leave
`review_label` as `NULL`.

## Setup

```bash
make manual-review-db
make manual-review-db-seed
```

The default seed command inserts up to 50 rows for each strategy. It does not overwrite
already reviewed labels.

Strategy-specific examples:

```bash
docker compose --profile dev run --rm --no-deps --build worker-dev \
  python -m src.entity_resolution.seed_manual_review_queue \
  --strategy igdb_suspicious_auto_merge \
  --limit-per-strategy 100

docker compose --profile dev run --rm --no-deps --build worker-dev \
  python -m src.entity_resolution.seed_manual_review_queue \
  --strategy igdb_likely_positive \
  --limit-per-strategy 50
```

When running through Codex, prepend shell commands with `rtk`.

## Review Query

Use this query in DBeaver, DataGrip, pgAdmin, or `psql`:

```sql
SELECT
    pair_id,
    name_a AS rawg_name,
    release_year_a AS rawg_year,
    rawg_url,
    name_b AS igdb_name,
    release_year_b AS igdb_year,
    igdb_url,
    igdb_search_rank,
    igdb_search_confidence,
    name_similarity,
    alias_similarity,
    release_year_diff,
    same_game_probability,
    model_decision,
    selection_strategy,
    priority_score,
    review_label,
    review_status,
    review_notes
FROM ml.v_igdb_manual_review_queue
WHERE review_status = 'pending'
ORDER BY priority_score DESC, name_similarity ASC NULLS LAST
LIMIT 200;
```

## Mark a Pair

Positive match:

```sql
UPDATE ml.entity_resolution_manual_reviews
SET review_label = TRUE,
    review_status = 'reviewed',
    reviewer = 'mgdr',
    review_notes = 'Same game',
    reviewed_at = NOW(),
    updated_at = NOW()
WHERE pair_id = '<pair_id>';
```

Negative match:

```sql
UPDATE ml.entity_resolution_manual_reviews
SET review_label = FALSE,
    review_status = 'reviewed',
    reviewer = 'mgdr',
    review_notes = 'Different game',
    reviewed_at = NOW(),
    updated_at = NOW()
WHERE pair_id = '<pair_id>';
```

Unsure:

```sql
UPDATE ml.entity_resolution_manual_reviews
SET review_label = NULL,
    review_status = 'unsure',
    reviewer = 'mgdr',
    review_notes = 'Needs additional source check',
    updated_at = NOW()
WHERE pair_id = '<pair_id>';
```

## Notebook Status

The project already has a Jupyter container profile (`make up-notebook`), but no committed
analysis notebook template yet. The recommended flow is to keep labels in PostgreSQL and use
notebooks only for exploratory analysis, charts, and model diagnostics over these DB tables.
