# Docker and PostgreSQL Bootstrap

This stage verifies the local MVP environment only. It does not run ingestion jobs and does not call external APIs.

## Commands

```bash
cp .env.example .env
# optionally create .env.secrets locally, never commit it
make build
make up
make ps
make db-check
curl http://localhost:8000/health
curl http://localhost:8000/health/db
make test
make lint
```

## Scope

- `postgres`, `app`, and `worker` are the default MVP services.
- PostgreSQL bootstrap is driven by idempotent init SQL scripts.
- The worker is intentionally idle and reserved for future ingestion commands.
- Optional services remain behind profiles and are not started by default.
