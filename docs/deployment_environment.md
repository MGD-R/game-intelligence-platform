# Deployment Environment

The bootstrap environment provides:

- `postgres` for relational storage and metadata tables.
- `app` for the FastAPI development server.
- `worker` for manual pipeline and ingestion commands.
- Optional profiles for `mlflow`, `minio`, `notebook`, and `pgadmin`.

This setup is intentionally local-first and avoids making Airflow mandatory for the MVP.
