# Architecture

The MVP architecture follows a simple local-development path:

1. External APIs feed raw acquisition jobs.
2. PostgreSQL stores raw, staging, ML, data mart, and metadata schemas.
3. FastAPI exposes health checks first, then catalog and recommendation APIs.
4. Worker commands orchestrate ingestion, preprocessing, ER, recommendation, and RAG steps through the Makefile.

Future branches should deepen each stage without changing the bootstrap contract.
