# pgvector semantic retrieval and LLM extraction

Last updated: 2026-08-29.

These are independent, feature-gated capabilities. LLM extraction affects ingest-time statutory references. pgvector affects query-time section discovery. Neither replaces Admin verification or provides legal advice.

## Semantic architecture

```text
PDF + SHA-256
  -> structured extraction and exact section text
  -> section embedding text (Act identity + path + heading + text)
  -> MiniLM 384-dimensional normalized vector
  -> PostgreSQL vector(384) + HNSW

query
  -> exact legal-identifier intent
  -> keyword/FTS candidates
  -> pgvector cosine candidates
  -> weighted reciprocal-rank fusion
  -> role and verification filters
```

The pinned provider is `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, dimension 384. Production does not use deterministic hash embeddings; `hash-test` exists only in the test environment.

## Operations

Keep serving disabled while migrating and backfilling:

```bash
SEMANTIC_SEARCH_ENABLED=false
ENABLE_PGVECTOR=true
EMBEDDING_PROVIDER=sentence-transformers
```

Run the resumable backfill:

```bash
cd backend
python -m app.db.backfill_embeddings --resume --retry-failed
```

Readiness is available through `/health`; Admins also receive model identity, status counts, HNSW state, and privacy-safe failure samples from `GET /api/v1/embeddings/status`.

Search semantics:

- `keyword`: metadata and PostgreSQL full-text only.
- `semantic`: pgvector section retrieval; returns a stable 400 when disabled and 503 when enabled but unready.
- `all`: Hybrid RRF only when semantic readiness is healthy; otherwise accurately reports Keyword as the effective mode.

Rollback is `SEMANTIC_SEARCH_ENABLED=false`. Do not drop vectors during operational rollback. Rebuild them whenever provider, model, revision, source composition, or dimension changes.

## Release gates

Do not change the default until:

- every embedding is current for provider/model/dimension;
- exact Act and section identifiers do not regress;
- all semantic results obey role and verification visibility;
- Hybrid MRR is at least Keyword MRR on the frozen gold set;
- Hybrid Recall@10 improves on paraphrase queries;
- representative plans use HNSW and recorded p95 meets the project target;
- PostgreSQL integration CI and a fresh-stack acceptance run pass.

The candidate retrieval dataset is under `data/retrieval-evaluation`. It requires independent human review before it may be frozen as v1.0. Evaluator runs are one-off processes with `SEMANTIC_SEARCH_ENABLED=true`; this does not authorize enabling deployed API serving.

## Model redistribution

See `THIRD_PARTY_NOTICES.md`. The pinned MiniLM metadata declares Apache-2.0. Release images must carry the license/notices, record model ID and revision, and repeat the review for any model change.
