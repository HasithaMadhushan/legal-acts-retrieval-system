# Evaluation guide

LexAtlas has two distinct source-gold evaluations. Neither workflow treats extractor or retrieval output as truth.

## Statutory-reference extraction

Admin-entered gold references measure precision, recall, F1, false positives, false negatives, and optional section-segmentation accuracy. Source text must be checked against the checksum-pinned PDF before a row is accepted.

## Retrieval relevance

`data/retrieval-evaluation/queries.csv` maps stable PDF filenames and section paths to graded relevance judgments. Runtime UUIDs are resolved only when an evaluation starts.

The evaluator reports P@5, R@5, R@10, MRR, nDCG@10, zero-result rate, verified-content rate, median latency, and p95 latency for Keyword, Semantic, and Hybrid modes. It saves commit SHA, model revision, configuration, per-query rankings, scores, and latency without overwriting earlier runs.

```bash
cd backend
SEMANTIC_SEARCH_ENABLED=true python -m scripts.evaluate_retrieval \
  --dataset ../data/retrieval-evaluation/queries.csv \
  --output ../data/retrieval-evaluation/results/<timestamp>-<sha>
```

`SEMANTIC_SEARCH_ENABLED=true` above is scoped to the evaluator process. Deployed serving stays disabled until the documented quality and performance gates pass.

The current candidate contains 40 queries over 12 Acts and covers exact identifiers, sections, terminology, paraphrases, amendment intent, ambiguity, spelling/format variants, and hard negatives. Two source-inspection passes are recorded, but these do not constitute two independent human legal annotations. Human reviewers must double-annotate at least 20%, adjudicate disagreements, and freeze v1.0 before release metrics are used.

## Performance evidence

Use `scripts/benchmark_semantic_search.py` against an isolated pgvector database. Preserve its JSON, Markdown, and full `EXPLAIN (ANALYZE, BUFFERS)` output. Database-query latency is not an API-latency claim; Task 21 separately records end-to-end API latency on the release-candidate stack.
