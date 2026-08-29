# Semantic search performance verification

No benchmark number is claimed until a run artifact is committed or attached to release evidence.

Run against an isolated PostgreSQL 16 database with pgvector:

```bash
cd backend
PGVECTOR_BENCHMARK_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB \
python -m scripts.benchmark_semantic_search \
  --sizes 1000 10000 \
  --runs 20 \
  --output ../data/retrieval-evaluation/results/<timestamp>-performance
```

The script streams synthetic normalized vectors in bounded batches, measures filtered and unfiltered cold/warm queries, records index-build time and database size, and preserves query plans. Add `100000` only when the test database has sufficient capacity.

Initial gates are p95 below 300 ms for the project corpus and below 750 ms at 10,000 sections on the documented development machine, with HNSW visible in representative plans. Adjust a gate only alongside recorded evidence and machine details.
