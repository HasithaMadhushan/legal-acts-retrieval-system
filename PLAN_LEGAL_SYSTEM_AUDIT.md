# PLAN.md — Legal Acts Retrieval System Audit Plan

## Purpose

Use this plan to audit the current `legal-acts-retrieval-system` codebase and determine whether the recommended issues actually exist in the system.

This is an **audit-first** plan. Do not implement fixes during the first pass unless explicitly asked. The expected output is a clear evidence-based report showing which issues are confirmed, partially present, not present, or unknown.

---

## Audit Rules for the Agent

1. **Do not modify code in the first pass.**
2. **Do not commit anything.**
3. **Do not delete files, database data, uploads, or migrations.**
4. **Do not expose secrets.**
5. **Use evidence from actual files, tests, and runtime behavior.**
6. For each finding, include:
   - status: `CONFIRMED`, `PARTIAL`, `NOT_FOUND`, or `UNKNOWN`
   - severity: `P0`, `P1`, `P2`
   - exact file path
   - exact line/function/class if possible
   - why it matters
   - how to reproduce or verify
   - recommended fix
7. If a finding cannot be confirmed statically, mark it `UNKNOWN` and explain what runtime test/data is required.

---

## Repository Context

Project: **Automated Legal Acts Retrieval System**

Main purpose:
- Upload English-language Sri Lankan Legal Act PDFs.
- Extract metadata, sections, and statutory references.
- Map references between Acts/sections.
- Allow Admin verification.
- Provide role-based search for Admin, Lawyer, and General User.
- Provide evaluation metrics such as precision, recall, and F1.

Expected stack:
- Backend: FastAPI, SQLAlchemy, Pydantic, JWT, bcrypt, PyMuPDF/Docling.
- Frontend: Next.js App Router, React, TypeScript.
- Database: SQLite local default, PostgreSQL for Docker/deployment.

---

# Phase 0 — Baseline Repo Inspection

## 0.1 Check branch and working tree

Run:

```bash
git status
git branch --show-current
git log --oneline -5
```

Record:
- current branch
- whether working tree is clean
- latest commit hash
- any uncommitted files

## 0.2 Inspect project structure

Run:

```bash
find . -maxdepth 3 -type f | sort
```

On Windows PowerShell:

```powershell
Get-ChildItem -Recurse -File | Select-Object -ExpandProperty FullName
```

Record main directories:
- `backend/`
- `frontend/`
- `backend/app/services/`
- `backend/app/api/routes/`
- `backend/app/models/`
- `backend/tests/`
- `.github/workflows/`
- `backend/alembic/versions/`

---

# Phase 1 — P0 Accuracy and Data Integrity Audit

## 1.1 Check whether verified data is wiped during reprocessing

### Why this matters

If an Admin verifies sections or references, reprocessing the same Act must not delete or overwrite that verified data. Otherwise the legal verification workflow cannot be trusted.

### Files to inspect

```text
backend/app/services/document_processor.py
backend/app/models/act_section.py
backend/app/models/legal_reference.py
backend/app/api/routes/acts.py
```

### What to look for

Search:

```bash
grep -R "delete(ActSection\|delete(LegalReference\|verification_status\|VERIFIED" backend/app/services backend/app/models backend/app/api -n
```

On PowerShell:

```powershell
Select-String -Path backend/app/services/*.py,backend/app/models/*.py,backend/app/api/routes/*.py -Pattern "delete\(ActSection|delete\(LegalReference|verification_status|VERIFIED"
```

### Confirm issue if

- `process_act()` deletes all `ActSection` rows for an Act before recreating them.
- `process_act()` deletes all `LegalReference` rows for an Act before recreating them.
- There is no preservation logic for `VERIFIED` records.
- The system only logs a warning but still deletes verified records.

### Expected audit result format

```markdown
### Finding: Verified sections/references are deleted on reprocess
Status: CONFIRMED / PARTIAL / NOT_FOUND / UNKNOWN
Severity: P0
Evidence:
- `backend/app/services/document_processor.py`, function `process_act`, lines ...
Impact:
- Admin-verified legal records can be lost after reprocessing.
Recommended fix:
- Preserve `VERIFIED` records or introduce extraction run/version tracking.
```

---

## 1.2 Check reference extraction false-positive risk

### Why this matters

Legal extraction must avoid treating every casual mention of “section”, “Act”, “paragraph”, “schedule”, or “chapter” as a meaningful statutory relationship.

### Files to inspect

```text
backend/app/services/reference_extractor.py
backend/app/services/reference_patterns.py
backend/app/core/roles.py
backend/tests/
```

### What to look for

Search:

```bash
grep -R "SECTION_RE\|SUBSECTION_RE\|PARAGRAPH_RE\|ITEM_RE\|SCHEDULE_RE\|CHAPTER_RE\|ACT_CITATION_RE\|classify_relationship\|score_reference" backend/app/services backend/tests -n
```

### Confirm issue if

- Broad regex patterns are applied globally to all text.
- Bare `section`, `subsection`, `paragraph`, `item`, `schedule`, or `chapter` mentions create references.
- Relationship classification uses a wide context window instead of sentence-bounded logic.
- Strong relationship types like `AMENDS`, `REPEALS`, `INSERTS`, `SUBSTITUTES`, or `ADDS` can be inferred without a clear operative verb close to the reference.
- Low-confidence references are still mixed into default Lawyer/General search results without clear filtering.
- No tests exist for dense amending sections or false-positive examples.

### Recommended fix direction

- Use sentence-bounded windows.
- Require operative legal verbs for strong relationship types.
- Classify weak references as `CROSS_REFERENCE` or `UNKNOWN`.
- Exclude `UNKNOWN` and low-confidence references from default General User views.
- Add regression tests for false-positive patterns.

---

## 1.3 Check fuzzy Act-title mapping weakness

### Why this matters

Wrongly mapping a reference to the wrong Act is worse than leaving it unresolved.

### Files to inspect

```text
backend/app/services/reference_mapper.py
backend/tests/
```

### What to look for

Search:

```bash
grep -R "ilike\|\.first()\|normalized_title\|_find_target_act\|match_kind" backend/app/services/reference_mapper.py backend/tests -n
```

### Confirm issue if

- Partial title matching uses `.first()` without ranking candidates.
- No scoring/margin exists between multiple possible title matches.
- Similar Act titles can be auto-mapped without requiring Admin review.
- Partial matches get confidence high enough to appear reliable.

### Recommended fix direction

Implement candidate ranking:
- exact Act number + year = strongest
- exact normalized title = strong
- token overlap score
- edit distance or similarity score
- minimum confidence threshold
- minimum margin between best and second-best match
- otherwise mark `NEEDS_REVIEW`

---

## 1.4 Check principal enactment inference

### Why this matters

Many Sri Lankan amendment Acts refer to “the principal enactment.” The system must infer the correct principal Act. Using the first Act reference in the whole document can be wrong.

### Files to inspect

```text
backend/app/services/reference_mapper.py
backend/app/services/reference_extractor.py
```

### What to look for

Search:

```bash
grep -R "principal enactment\|principal_act\|principal_context\|build_mapping_context" backend/app/services -n
```

### Confirm issue if

- Principal enactment context is selected from the first mappable non-principal reference in the entire document.
- Mapping does not consider the closest preceding Act-level citation near the source section or amending clause.
- There is no per-section or per-reference context.

### Recommended fix direction

- Determine principal enactment per source section or per reference.
- Prefer the closest preceding Act-level citation.
- If confidence is weak, mark as `NEEDS_REVIEW`.
- Record `principal_source` evidence in mapping summary.

---

## 1.5 Check metadata extraction limitations

### Why this matters

Bad metadata affects search, mapping, filtering, and evaluation.

### Files to inspect

```text
backend/app/services/metadata_extractor.py
backend/tests/
```

### What to look for

Search:

```bash
grep -R "4000\|first_lines\|ACT_NUMBER_RE\|_looks_like_title\|Ordinance\|Act" backend/app/services/metadata_extractor.py backend/tests -n
```

### Confirm issue if

- Metadata extraction only scans the first fixed character window.
- Title logic only accepts “Act” and not “Ordinance.”
- There is no clear extraction provenance for title/number/date.
- No tests cover unusual Act title placement, Ordinances, or date variants.

### Recommended fix direction

- Scan first N pages or a larger normalized window.
- Add `Ordinance` title support.
- Store extraction reasons/provenance.
- Add tests for:
  - standard Act
  - Ordinance
  - missing title
  - title below header noise
  - certification/publication date variants

---

# Phase 2 — Evaluation and Regression Testing Audit

## 2.1 Check whether evaluation exists and is usable

### Files to inspect

```text
EVALUATION_GUIDE.md
backend/app/services/evaluation_service.py
backend/app/api/routes/evaluation.py
frontend/app/admin/evaluation/
backend/tests/
```

### What to look for

Search:

```bash
grep -R "precision\|recall\|f1\|false_positives\|false_negatives\|gold" EVALUATION_GUIDE.md backend frontend -n
```

### Confirm good status if

- Admin can add gold references.
- Evaluation produces precision, recall, F1.
- Evaluation stores false positives and false negatives.
- Evaluation can be run per Act and across Acts.

### Confirm gap if

- There is no seed/sample gold dataset.
- There are no regression tests based on known false positives/false negatives.
- Evaluation exists but is not integrated into CI.
- The README claims evaluation but no command/test proves it works.

### Recommended fix direction

- Add sample gold dataset under `backend/tests/fixtures/`.
- Add tests for evaluation metrics.
- Add tests for known extraction/mapping mistakes.
- Add a repeatable command or script:

```bash
python -m pytest backend/tests/test_evaluation_service.py
```

---

# Phase 3 — Security Audit

## 3.1 Check production secret-key guard

### Files to inspect

```text
backend/app/core/config.py
backend/app/main.py
.env.example
docker-compose.yml
```

### What to look for

Search:

```bash
grep -R "SECRET_KEY\|change-this-development-secret\|environment\|ENVIRONMENT" backend .env.example docker-compose.yml -n
```

### Confirm issue if

- Default secret key exists.
- App can start with default secret when `ENVIRONMENT=production`.
- No startup guard refuses unsafe production configuration.

### Recommended fix direction

- Add startup validation in config or lifespan:

```python
if settings.environment == "production" and settings.secret_key == "change-this-development-secret":
    raise RuntimeError("Refusing to start with default SECRET_KEY in production")
```

---

## 3.2 Check JWT storage and logout behavior

### Files to inspect

```text
backend/app/api/routes/auth.py
backend/app/core/security.py
backend/app/api/deps.py
frontend/lib/auth.ts
frontend/lib/api.ts
```

### What to look for

Search:

```bash
grep -R "localStorage\|Authorization\|Bearer\|logout\|access_token\|refresh" backend frontend -n
```

### Confirm issue if

- JWT is stored in `localStorage`.
- Backend only returns bearer token.
- Logout only tells client to discard token.
- There is no refresh token or revocation table.
- Tokens are long-lived.

### Recommended fix direction

- Move access token to httpOnly, Secure, SameSite cookie.
- Add short-lived access token.
- Add refresh-token table.
- Implement real logout by revoking refresh token.
- Add CSRF considerations if cookie auth is introduced.

---

## 3.3 Check login/register rate limiting

### Files to inspect

```text
backend/app/api/routes/auth.py
backend/app/main.py
backend/requirements.txt
```

### What to look for

Search:

```bash
grep -R "slowapi\|rate\|limiter\|login\|register" backend -n
```

### Confirm issue if

- No rate limiter exists on `/auth/login`.
- No rate limiter exists on `/auth/register`.
- No account lockout or throttling exists.

### Recommended fix direction

- Add `slowapi` or custom middleware.
- Rate limit by IP and email.
- Log repeated failed login attempts.

---

## 3.4 Check CSV formula injection

### Files to inspect

```text
backend/app/services/export_service.py
backend/tests/
```

### What to look for

Search:

```bash
grep -R "csv.writer\|writerow\|saved_items_csv\|act_references_csv" backend/app/services backend/tests -n
```

### Confirm issue if

- CSV exports write raw user/content values directly.
- No function sanitizes values starting with `=`, `+`, `-`, or `@`.

### Recommended fix direction

Add a sanitizer:

```python
def safe_csv_cell(value: object) -> str:
    text = str(value or "")
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text
```

Apply to all exported cells that come from user input, PDF text, notes, titles, sections, or references.

---

## 3.5 Check upload content sniffing

### Files to inspect

```text
backend/app/api/routes/acts.py
backend/requirements.txt
```

### What to look for

Search:

```bash
grep -R "python-magic\|magic\|content_type\|PDF_SIGNATURE\|%PDF" backend -n
```

### Confirm issue if

- Upload validation only checks extension, MIME, and `%PDF-` signature.
- No `python-magic` or equivalent content sniffing exists.

### Recommended fix direction

- Add `python-magic` or platform-safe equivalent.
- Keep `%PDF-` signature check.
- Reject suspicious content types.
- Keep max upload size.

---

# Phase 4 — Processing Architecture and Reliability Audit

## 4.1 Check synchronous processing

### Files to inspect

```text
backend/app/api/routes/acts.py
backend/app/services/document_processor.py
backend/app/models/processing_job.py
frontend/lib/api.ts
```

### What to look for

Search:

```bash
grep -R "process_act\|BackgroundTasks\|Celery\|RQ\|arq\|ProcessingJob" backend frontend -n
```

### Confirm issue if

- `/acts/{act_id}/process` calls `process_act()` directly in the request.
- There is no background worker or task queue.
- Frontend waits for processing response instead of polling an async job.

### Recommended fix direction

Minimum:
- Use FastAPI `BackgroundTasks`.

Better:
- Use Celery, RQ, or arq.
- Keep `ProcessingJob` polling endpoint.
- Add retry/failure status handling.

---

## 4.2 Check health endpoint

### Files to inspect

```text
backend/app/main.py
backend/app/db/session.py
docker-compose.yml
```

### What to look for

Search:

```bash
grep -R "health\|/health\|select 1\|healthcheck" backend docker-compose.yml -n
```

### Confirm issue if

- `/health` returns static `{"status": "ok"}` only.
- No DB connectivity check exists.
- No upload directory writable check exists.
- No parser configuration check exists.

### Recommended fix direction

Health endpoint should verify:
- API is alive.
- DB responds to `SELECT 1`.
- Upload directory exists/writable.
- Parser configuration is valid.

---

## 4.3 Check Alembic vs create_all conflict

### Files to inspect

```text
backend/app/db/session.py
backend/app/main.py
backend/alembic/
backend/alembic/versions/
backend/Dockerfile
docker-compose.yml
```

### What to look for

Search:

```bash
grep -R "create_all\|init_db\|alembic upgrade\|revision\|down_revision" backend docker-compose.yml -n
```

### Confirm issue if

- App startup calls `Base.metadata.create_all()`.
- Alembic exists but is not the only migration strategy.
- Docker entrypoint does not run `alembic upgrade head`.
- No migration versions exist under `backend/alembic/versions`.

### Recommended fix direction

- Use Alembic as source of truth.
- Move `create_all()` to tests only.
- Add migration files.
- Run `alembic upgrade head` in Docker entrypoint/CI.

---

# Phase 5 — Search Quality Audit

## 5.1 Check ILIKE-only search

### Files to inspect

```text
backend/app/services/search_service.py
backend/alembic/
backend/models/
```

### What to look for

Search:

```bash
grep -R "ilike\|tsvector\|GIN\|to_tsvector\|ts_rank\|pgvector\|embedding" backend -n
```

### Confirm issue if

- Search depends mainly on `ILIKE`.
- No PostgreSQL full-text search exists.
- No `tsvector`/GIN index migration exists.
- No ranking beyond custom Python score exists.

### Recommended fix direction

- Add PostgreSQL full-text search for production.
- Keep SQLite/ILIKE fallback for local mode.
- Add `ts_rank` ranking.
- Add search evaluation tests.
- Add pgvector only after full-text search is stable.

---

# Phase 6 — CI/CD and Deployment Audit

## 6.1 Check GitHub Actions CI

### Files to inspect

```text
.github/workflows/
backend/requirements.txt
frontend/package.json
```

### What to look for

Search:

```bash
find .github -maxdepth 3 -type f
```

PowerShell:

```powershell
Get-ChildItem .github -Recurse -File
```

### Confirm issue if

- No CI workflow exists.
- CI does not run backend ruff/pytest.
- CI does not run frontend typecheck/test/build.

### Recommended fix direction

Add `.github/workflows/ci.yml` with:
- backend ruff
- backend pytest
- frontend npm ci
- frontend typecheck
- frontend tests
- frontend build

---

## 6.2 Check Docker production readiness

### Files to inspect

```text
docker-compose.yml
backend/Dockerfile
frontend/Dockerfile
.env.example
README.md
```

### What to look for

Search:

```bash
grep -R "uvicorn\|gunicorn\|SECRET_KEY\|POSTGRES_PASSWORD\|healthcheck\|SSM\|backup\|nginx\|caddy" Dockerfile docker-compose.yml backend frontend README.md .env.example -n
```

### Confirm issue if

- Production-like Docker uses hardcoded DB password.
- Backend runs bare Uvicorn in production.
- No backend healthcheck exists.
- No reverse proxy plan exists.
- No S3/persistent upload strategy exists beyond local volume.
- No DB backup plan exists.
- No secrets management plan exists.

### Recommended fix direction

- Gunicorn + Uvicorn workers.
- Reverse proxy with HTTPS.
- Secrets through environment/SSM/secrets manager.
- Healthchecks.
- Persistent uploads or S3.
- Daily database backups.
- Separate local and production compose files.

---

# Phase 7 — Frontend Audit

## 7.1 Check form validation stack

### Files to inspect

```text
frontend/package.json
frontend/app/
frontend/components/
```

### What to look for

Search:

```bash
grep -R "react-hook-form\|zod\|useState\|onSubmit\|FormEvent" frontend -n
```

### Confirm issue if

- Forms use mostly manual `useState`.
- No React Hook Form.
- No Zod validation.
- Validation and error display are inconsistent.

### Recommended fix direction

- Add React Hook Form + Zod.
- Start with Admin metadata edit, reference correction, and evaluation gold-reference forms.
- Add reusable field/error components.

---

## 7.2 Check relationship graph quality

### Files to inspect

```text
frontend/components/relationship-graph.tsx
frontend/app/lawyer/relationships/
frontend/package.json
```

### What to look for

Search:

```bash
grep -R "ReactFlow\|reactflow\|RelationshipGraph\|graph-row\|nodes\|edges" frontend -n
```

### Confirm issue if

- Relationship graph is rendered as rows/list instead of visual node-edge graph.
- No React Flow or equivalent graph library exists.

### Recommended fix direction

- Use React Flow.
- Show Act/Section nodes.
- Show relationship edges.
- Show confidence/status badges.
- Keep table as secondary detail view.

---

## 7.3 Check loading, empty, and error states

### Files to inspect

```text
frontend/app/
frontend/components/
```

### What to look for

Search:

```bash
grep -R "Loading\|loading\|error\|empty\|ErrorBanner\|EmptyState\|LoadingState" frontend -n
```

### Confirm issue if

- Loading/error/empty UI is duplicated across pages.
- No shared components exist.
- Some Admin/Lawyer flows do not show retry or clear failure reasons.

### Recommended fix direction

- Add shared:
  - `LoadingState`
  - `EmptyState`
  - `ErrorBanner`
  - `RetryButton`
- Use consistently across Admin, Lawyer, and General User pages.

---

# Phase 8 — OCR and Semantic Search Audit

## 8.1 Check OCR fallback

### Files to inspect

```text
backend/app/services/pdf_parser/
backend/app/services/document_processor.py
backend/app/core/config.py
backend/requirements.txt
.env.example
```

### What to look for

Search:

```bash
grep -R "OCR_ENABLED\|tesseract\|ocr\|image-only\|scanned" backend .env.example README.md -n
```

### Confirm issue if

- OCR is disabled.
- No Tesseract or OCR parser implementation exists.
- Scanned PDFs are reported unsupported.

### Recommended fix direction

- Add OCR fallback later, after extraction/search stability.
- Mark OCR output as `NEEDS_REVIEW`.
- Store OCR confidence and warnings.

---

## 8.2 Check semantic search / pgvector readiness

### Files to inspect

```text
backend/
docker-compose.yml
backend/requirements.txt
```

### What to look for

Search:

```bash
grep -R "pgvector\|vector\|embedding\|sentence-transformers\|semantic" backend docker-compose.yml -n
```

### Confirm issue if

- Embedding service exists but is not wired.
- No pgvector extension/migration exists.
- No chunking/retrieval evaluation exists.

### Recommended fix direction

Only after full-text search is stable:
- Add section/chunk embeddings.
- Use pgvector.
- Store citation metadata.
- Add retrieval accuracy evaluation.

---

# Required Final Output from Agent

Create a report named:

```text
AUDIT_FINDINGS.md
```

The report must use this structure:

```markdown
# AUDIT_FINDINGS.md — Legal Acts Retrieval System

## Summary

- Repo:
- Branch:
- Commit:
- Audit date:
- Tests run:
- Overall status:

## Findings by Priority

### P0 Findings

| ID | Status | Issue | Evidence | Recommended Action |
|---|---|---|---|---|

### P1 Findings

| ID | Status | Issue | Evidence | Recommended Action |
|---|---|---|---|---|

### P2 Findings

| ID | Status | Issue | Evidence | Recommended Action |
|---|---|---|---|---|

## Detailed Findings

### FINDING-001: Stop wiping verified data on reprocess

Status:
Severity:
Files:
Evidence:
Impact:
Reproduction/verification:
Recommended fix:
Implementation risk:

### FINDING-002: Reduce false-positive references

Status:
Severity:
Files:
Evidence:
Impact:
Reproduction/verification:
Recommended fix:
Implementation risk:

Continue this format for all findings.

## Tests and Commands Run

List every command run and result.

## Recommended Implementation Order

1.
2.
3.

## Unknowns / Needs Runtime Verification

List issues that could not be confirmed statically.
```

---

# Suggested Implementation Order After Audit

If the audit confirms the issues, fix in this order:

1. Preserve verified sections/references during reprocess.
2. Add regression tests for reprocess preservation.
3. Tighten reference extraction false positives.
4. Improve fuzzy Act-title mapping.
5. Fix principal enactment inference.
6. Improve metadata extraction.
7. Build gold dataset and evaluation regression tests.
8. Add production secret-key guard.
9. Add CSV formula injection protection.
10. Move processing to background jobs.
11. Add GitHub Actions CI.
12. Add PostgreSQL full-text search.
13. Move migrations fully to Alembic.
14. Harden Docker/deployment.
15. Add frontend validation and real graph.
16. Add OCR and semantic search later.

---

# Important Note

Do not assume an issue exists only because this plan mentions it. Confirm each item from the current codebase. If evidence is weak, mark it `UNKNOWN` or `PARTIAL`.
