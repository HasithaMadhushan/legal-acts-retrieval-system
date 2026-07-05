# PRODUCTION_ROADMAP.md — Legal Acts Retrieval System

Companion to `AUDIT_FINDINGS.md`. The audit describes **what is true today**; this roadmap describes **how to take it to a real, deployable, production-grade service**, plus honest assessments of the **libraries** and **features**.

- **Target profile:** small → medium scale (a handful of Admins/Lawyers, up to hundreds of users, hundreds→low-thousands of Acts). Correctness and legal-safety matter far more than raw throughput. Designed to grow into medium load without a rewrite.
- **Guiding principle:** ship correctness and safety first; add scale/ML features only after the core is trustworthy and measured.

---

## 1. Current state vs. production gap

**What already works (verified):** FastAPI + SQLAlchemy backend, JWT auth with RBAC, PDF parsing (PyMuPDF/Docling), metadata/section/reference extraction, reference mapping with confidence bands, Admin verification workflow, role-scoped search, saved items + CSV/Markdown export, and a real evaluation service (precision/recall/F1, false positives/negatives, per-Act and cross-Act, plus section-segmentation accuracy). The full test suite passes.

**What stands between this and production:**
- One data-integrity defect (verified data lost on reprocess — audit F-001).
- Deployment/ops maturity: secrets, migrations, background jobs, health checks, backups, CI/CD, reverse proxy/TLS, log/error monitoring.
- Search quality at scale (ILIKE → full-text).
- Auth hardening (token storage/TTL/revocation, rate limiting).

None of these require re-architecting. This is a solid foundation.

---

## 2. Recommended deployment architecture

You asked me to recommend (target was undecided). For a solo/small-team legal-retrieval app that must reach production quickly and cheaply, **avoid heavyweight AWS ECS/Kubernetes**. Two good tiers:

### Recommended: Managed PaaS (lowest ops burden)
```
[ Users ] → [ Vercel: Next.js frontend ]
                     │  HTTPS
                     ▼
        [ Render/Fly.io/Railway: FastAPI (gunicorn+uvicorn workers) ]
             │                    │                     │
             ▼                    ▼                     ▼
   [ Managed Postgres ]   [ Object storage (S3/R2) ]  [ Background worker ]
      (auto backups)          for uploaded PDFs        (same image, queue)
```
- **Why:** managed TLS, managed Postgres with automated backups, secrets UI, zero-downtime deploys, trivial rollback. You spend time on the product, not on ops. Comfortably handles the target scale.
- **Uploads:** move off local disk to S3-compatible object storage (S3 or Cloudflare R2) so files survive redeploys/scale events.

### Alternative A: Single VPS + Docker Compose + Nginx
- One droplet (Hetzner/DigitalOcean), `docker compose` for backend/frontend/Postgres, Nginx (or Caddy) for TLS.
- **Why/when:** cheapest, full control; but you own OS patching, backups, and TLS renewal. Good if institutional policy forbids managed cloud.

### Alternative B: AWS (use the existing `infra/aws/`)
- ECS Fargate or a single EC2, RDS Postgres, S3 uploads, Secrets Manager.
- **Why/when:** only if AWS is a hard requirement. More powerful, more moving parts, higher ops cost than justified at this scale.

**Recommendation:** start on **PaaS (Vercel + Render/Fly.io + managed Postgres + S3/R2)**; keep the Docker images so you can move to VPS or AWS later without code changes.

---

## 3. Production-readiness roadmap (phased)

### Phase 1 — Correctness & legal-safety (must-do before any real users) — ✅ DONE (2026-07-05)
- **F-001:** ✅ Preserve `VERIFIED` sections/references on reprocess (+ regression test). *This is the single most important fix.*
- **F-002:** ✅ Refuse to boot in production with the default `SECRET_KEY`.
- **F-003:** ✅ CSV formula-injection sanitizer on all exported cells.
- ⬜ Rotate all demo/secret values out of `docker-compose.yml` and `.env.example`. *(not yet done — demo credentials are intentionally left in place per `AGENTS.md`, but production secrets must still be overridden before deploy.)*

### Phase 2 — Reliability & operability — ✅ mostly DONE (2026-07-05)
- **F-007:** ✅ Background processing via FastAPI `BackgroundTasks`, using the existing `ProcessingJob` model for polling. (RQ/arq upgrade still recommended before multi-worker/horizontal scaling — see note below.)
- **F-011:** ✅ Real `/health` (DB `SELECT 1`, upload/storage writable, parser config).
- **F-012:** ✅ Alembic is now the single source of truth: a correct baseline migration replaces the two broken incremental ones, the app runs `alembic upgrade head` at startup, and the Docker image runs it explicitly before starting the server. `create_all()` is now test-only.
- ⬜ Add **structured logging** (`structlog`) and **error tracking** (`sentry-sdk`). *(not yet done.)*

> **Note on F-007:** `BackgroundTasks` runs the job in the same process/worker as the API. This is a correct, low-risk improvement over the previous fully-synchronous request (the HTTP call now returns immediately and the frontend polls `GET /acts/{id}/processing-jobs`), but it does **not** survive a process restart mid-job, and a very large PDF could still tie up a worker thread. Before running multiple Gunicorn/uvicorn workers in production (Phase 3), replace this with a real queue (RQ or arq + Redis) so jobs are durable and processing is decoupled from the web workers.

### Phase 3 — Deployment hardening
- Run **gunicorn + uvicorn workers** (not bare uvicorn — current `backend/Dockerfile:13`).
- HTTPS via PaaS or reverse proxy (Nginx/Caddy).
- **Secrets** via platform env/secret manager (never in compose).
- **Automated daily DB backups** (managed Postgres gives this).
- **Object storage** for uploads (S3/R2).
- **F-008:** Rate limiting on `/auth/*`.
- **F-006:** CI/CD (ruff + pytest + frontend typecheck/test/build; deploy on green).
- Split `docker-compose.yml` into local vs. production overrides.

### Phase 4 — Search quality & accuracy
- **F-004 / F-005:** Ranked Act-title mapping + per-section principal-enactment context.
- **F-009 / F-010:** Sentence-bounded reference extraction, operative-verb requirements, Ordinance metadata; back these with a **seed gold dataset** + regression tests via the existing evaluation service.
- **F-013:** Postgres full-text search (`tsvector` + GIN + `ts_rank`), ILIKE fallback for SQLite.

### Phase 5 — Advanced (only after the above is measured and stable)
- **F-018:** OCR fallback (Tesseract), output flagged `NEEDS_REVIEW`.
- **F-019:** Semantic search via pgvector + embeddings, with retrieval-accuracy evaluation.
- **F-016 / F-017:** React Hook Form + Zod; React Flow relationship graph.

---

## 4. Library assessment

### Backend (`backend/requirements.txt`) — mostly excellent choices

| Library | Verdict | Notes |
|---|---|---|
| `fastapi` 0.115 | **Keep** | Ideal for this app; modern, typed, great docs. |
| `uvicorn[standard]` | **Keep (+add gunicorn)** | Keep for dev; run `gunicorn -k uvicorn.workers.UvicornWorker` in prod. |
| `sqlalchemy` 2.0 | **Keep** | Current best-practice ORM; 2.0 style is right. |
| `pydantic` / `pydantic-settings` 2.x | **Keep** | Correct choice for schemas/config. |
| `PyJWT` | **Keep** | Fine. If you later move to cookie/refresh auth, consider `authlib` only if you need OAuth. |
| `bcrypt` | **Keep** | Solid. (`argon2-cffi` is a marginally stronger alternative, not necessary.) |
| `pymupdf` | **Keep** | Fast, high-quality text extraction — a strong pick. |
| `docling` | **Keep, but watch** | Powerful layout parsing but heavy and slow; make sure it runs in a background worker (Phase 2) and pin the version. |
| `psycopg[binary]` 3.x | **Keep** | Correct modern Postgres driver. |
| `alembic` | **Keep** | Good — just make it the *only* migration path (F-012). |
| `pytest` / `httpx` / `ruff` | **Keep** | Excellent standard toolchain. |

**Recommended additions:** `slowapi` (rate limiting), `structlog` (logging), `sentry-sdk` (errors), `gunicorn` (prod server), `python-magic-bin`/`python-magic` (content sniffing), and later `pgvector` + an embeddings library (`sentence-transformers` or an API client).

### Frontend (`frontend/package.json`) — lean; add a validation + graph layer

| Library | Verdict | Notes |
|---|---|---|
| `next` 16 / `react` 19 | **Keep** | Current, appropriate. |
| `typescript` 5.7 (strict) | **Keep** | Good. |
| `vitest` | **Keep** | Good test runner. |
| (data fetching) | **Consider adding** | `@tanstack/react-query` would standardize loading/error/caching (helps audit F-014 UX gaps). |
| (forms) | **Add** | `react-hook-form` + `zod` (F-016). |
| (graph) | **Add** | `reactflow` for the relationship graph (F-017). |

**Bottom line on libraries:** your core stack choices are genuinely good — there's nothing to *replace*, only a handful of production/UX libraries to *add*.

---

## 5. Feature assessment

### Current features, rated against the PRD purpose

| Feature | Rating | Comment |
|---|---|---|
| PDF upload + validation | **Good** | Extension/MIME/magic-byte/size/SHA-256 dedupe. Add deep sniffing later. |
| Metadata extraction | **Adequate** | Works with provenance/confidence; misses Ordinances + wide scan (F-010). |
| Section segmentation | **Good** | Structured, testable. |
| Reference extraction | **Adequate** | Rich patterns + confidence, but global regex false positives (F-009). |
| Reference mapping | **Adequate/weak** | Confidence bands are good; ranking + principal-enactment logic need work (F-004/F-005). |
| Admin verification workflow | **Good (but see F-001)** | Correct concept; undermined by reprocess wiping verified data. |
| Role-based search (Admin/Lawyer/User) | **Good** | Correct visibility rules; General Users see only verified+mapped. |
| Saved items + export (CSV/MD) | **Good** | Useful; needs CSV sanitizer (F-003). |
| Evaluation (P/R/F1, FP/FN, segmentation) | **Strong** | A standout feature and a major asset for the academic writeup. |
| Legal-safety disclaimers / no-advice | **Good** | Consistently wired. |
| Relationship visualization | **Weak** | List, not a graph (F-017). |
| Processing job tracking | **Adequate** | Model + polling exist; processing not yet async (F-007). |

### Most important features (ranked by production value)

**Tier 1 — the reason the system exists (protect these first):**
1. **Verification integrity** — Admin verification must never be silently lost (fix F-001). Without this, nothing else is trustworthy.
2. **Accurate reference extraction & mapping** — correct statutory relationships, with wrong mappings flagged rather than auto-accepted (F-004/F-005/F-009).
3. **Evaluation metrics** — the objective proof the system works; also your strongest academic evidence. Add a seed gold dataset.
4. **Role-based access + legal-safety** — General Users see only verified material; no legal advice.

**Tier 2 — makes it genuinely usable in production:**
5. Reliable search (full-text at scale).
6. Robust upload → async processing → status feedback.
7. Auth hardening (rate limiting, token handling).

**Tier 3 — valuable enhancements, not blockers:**
8. Relationship graph visualization.
9. OCR for scanned Acts.
10. Semantic/pgvector search.

---

## 6. Suggested 90-day execution order

- **Weeks 1-2:** Phase 1 (F-001 + test, F-002, F-003) → then F-006 CI to lock it in.
- **Weeks 3-5:** Phase 2 (async processing, health check, Alembic, logging/errors).
- **Weeks 6-8:** Phase 3 (deploy to PaaS: gunicorn, TLS, secrets, backups, S3/R2, rate limiting).
- **Weeks 9-11:** Phase 4 (mapping ranking, principal enactment, extraction tightening + gold dataset, full-text search).
- **Week 12+:** Phase 5 as capacity allows (graph, OCR, semantic search).

**If you only do three things:** F-001 (verified-data preservation), F-002 (secret guard), and F-006 (CI). Those move you from "working demo" to "safe to run for real users" faster than anything else.
