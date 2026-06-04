# Demo Scenarios

Current defense demo:

1. Start the local stack with `make up-dev` and inspect `/health`, `/health/db`, and
   `/version`.
2. Show platform scale through `/stats/catalog` and `/stats/ml`.
3. Search the canonical catalog with `/games?search=doom` and open the DOOM card through
   `/games/{game_id}`.
4. Show read-only recommendations through `/games/{game_id}/similar` and `POST /recommend`.
5. Demonstrate reviewed ER/manual-review pairs through `/matches/review?review_status=reviewed`.
6. Show grounded Russian explanations through `/explain/recommendation` and `/explain/match`.
7. Use [final demo cases](final_demo_cases_ru.md), [timed rehearsal](timed_defense_rehearsal_ru.md),
   and [final smoke checklist](final_defense_smoke_checklist_ru.md) as the canonical defense
   scenario.
