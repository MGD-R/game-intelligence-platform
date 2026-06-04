# Demo Scenarios

Current defense demo:

1. Start the local stack with `make up-dev` and inspect `/health`, `/health/db`, and
   `/version`.
2. Run `make demo-readiness` or open `/stats/readiness` to show that demo data and defense
   artifacts are available.
3. Show platform scale through `/stats/catalog`, `/stats/ml`, and `/stats/graph`.
4. Search the canonical catalog with `/games?search=doom` and open the DOOM card through
   `/games/{game_id}`.
5. Show recommendations through `/games/{game_id}/similar` and `POST /recommend`, switching
   between `content_jaccard_v1` and `hybrid_content_rating_v1` when hybrid rows are available.
6. Demonstrate reviewed ER/manual-review pairs through `/matches/review?review_status=reviewed`.
7. Demonstrate the write review endpoint with `PATCH /matches/review/{pair_id}` on a safe
   test pair when PostgreSQL manual review data is available.
8. Show grounded Russian explanations through `/explain/recommendation` and `/explain/match`;
   `mode=llm` is optional and falls back to template text unless an LLM provider is configured.
9. Optionally start `make up-ui` and use the Streamlit UI on `http://localhost:8501`.
10. Use [final demo cases](final_demo_cases_ru.md), [timed rehearsal](timed_defense_rehearsal_ru.md),
   and [final smoke checklist](final_defense_smoke_checklist_ru.md) as the canonical defense
   scenario.
