# AUDIT_FINDINGS.md — Legal Acts Retrieval System

## Summary

- **Repo:** `legal-acts-retrieval-system`
- **Branch:** `main`
- **Commit:** `a467031c02e2d67952666f889df32da1f2458f80` ("Initial commit")
- **Audit date:** 2026-07-05
- **Tests run:** `backend/.venv\Scripts\python -m pytest -q` → **all passing, exit code 0** (only `datetime.utcnow()` deprecation warnings)
- **Overall status:** Healthy, working academic MVP. One P0 data-integrity defect (verified data lost on reprocess). A cluster of P1/P2 items are production-hardening or accuracy-tightening rather than MVP blockers. This pass is **audit-only; no code was modified.**

---

## Findings by Priority

### P0 Findings

| ID | Status | Issue | Evidence | Recommended Action |
|---|---|---|---|---|
| F-001 | CONFIRMED | Admin-verified sections & references are deleted on reprocess | `backend/app/services/document_processor.py:141-142` | Preserve `VERIFIED` rows or add extraction-run/version tracking |

### P1 Findings

| ID | Status | Issue | Evidence | Recommended Action |
|---|---|---|---|---|
| F-002 | CONFIRMED | No production secret-key guard | `backend/app/core/config.py:24`; `docker-compose.yml:23`; `.env.example:3`; `backend/app/main.py:23-32` | Refuse to boot in `production` with default `SECRET_KEY` |
| F-003 | CONFIRMED | CSV formula injection in exports | `backend/app/services/export_service.py:41-62, 106-118` | Add `safe_csv_cell()` sanitizer for `= + - @` |
| F-004 | CONFIRMED | Fuzzy Act-title mapping uses `.first()` with no ranking/margin | `backend/app/services/reference_mapper.py:183-195` | Rank candidates; require score + margin; else `NEEDS_REVIEW` |
| F-005 | CONFIRMED | Principal enactment inferred from first doc-wide match | `backend/app/services/reference_mapper.py:38-50` | Prefer closest preceding Act citation; per-section context |
| F-006 | CONFIRMED | No CI pipeline | No `.github/workflows/` present | Add CI: ruff + pytest + frontend typecheck/test/build |
| F-007 | CONFIRMED | Synchronous PDF processing in request thread | `backend/app/api/routes/acts.py:164-173` | Move to background job / task queue with polling |
| F-008 | CONFIRMED | No login/register rate limiting | `backend/app/api/routes/auth.py:16-45`; `requirements.txt` (no limiter) | Add `slowapi`/middleware; throttle by IP + email |

### P2 Findings

| ID | Status | Issue | Evidence | Recommended Action |
|---|---|---|---|---|
| F-009 | PARTIAL | Broad regex reference patterns applied globally | `backend/app/services/reference_extractor.py:185-203, 232-239` | Sentence-bounded windows; require operative verbs for strong types |
| F-010 | CONFIRMED | Metadata title logic misses "Ordinance"; scans only first 4000 chars | `backend/app/services/metadata_extractor.py:44, 112` | Add Ordinance support; scan wider window |
| F-011 | CONFIRMED | `/health` is static | `backend/app/main.py:43-45` | Check DB `SELECT 1`, upload dir writable, parser config |
| F-012 | CONFIRMED | Alembic + `create_all()` both used | `backend/app/db/session.py:24-27`; `backend/app/main.py:25`; migrations exist under `backend/alembic/versions/` | Make Alembic source of truth; run `upgrade head` in Docker |
| F-013 | CONFIRMED | Search is ILIKE-only + Python scoring | `backend/app/services/search_service.py` (all `ilike`) | Add Postgres full-text (`tsvector`/GIN) for production |
| F-014 | CONFIRMED | JWT in `localStorage`, long-lived (8h), logout is client-side only | `frontend/lib/auth.ts:7-23`; `frontend/lib/api.ts:36`; `config.py:25`; `auth.py:48-50` | Consider httpOnly cookie, shorter TTL, refresh/revocation |
| F-015 | PARTIAL | Upload validation lacks deep content sniffing | `backend/app/api/routes/acts.py:72-81` | Add `python-magic`; keep `%PDF-` + size checks |
| F-016 | CONFIRMED | Forms use manual `useState`; no schema validation | `frontend/package.json` (no `react-hook-form`/`zod`) | Add React Hook Form + Zod |
| F-017 | CONFIRMED | Relationship "graph" is a list/table, not a visual graph | `frontend/components/relationship-graph.tsx`; no `reactflow` dep | Add React Flow node/edge graph |
| F-018 | NOT_FOUND (by design) | OCR fallback absent | `config.py:31` `ocr_enabled=False`; `pdf_parser/ocr_parser.py` stub | Intentionally deferred; future work |
| F-019 | NOT_FOUND (by design) | Semantic search / pgvector not wired | `backend/app/services/embedding_service.py:1-7` (`enabled=False`) | Intentionally deferred; future work |

---

## Detailed Findings

### FINDING-001: Verified sections/references are deleted on reprocess
- **Status:** CONFIRMED
- **Severity:** P0
- **Files:** `backend/app/services/document_processor.py`
- **Evidence:** Lines 141-142 unconditionally delete all references and sections for the Act:
  `db.execute(delete(LegalReference).where(LegalReference.source_act_id == act.id))` and
  `db.execute(delete(ActSection).where(ActSection.act_id == act.id))`.
  The code counts existing `VERIFIED` rows (110-117, 132-139) and appends a warning (118-129, 197-208) but proceeds to delete anyway. New rows are created with `verification_status=PENDING` (159).
- **Impact:** Any Admin verification of sections/references is permanently lost on reprocess, undermining the core trust model of the system. (Note: Act-level **metadata** IS preserved — 96-99 — so the pattern is understood, just not applied to sections/references.)
- **Reproduction/verification:** Upload → process → verify a section/reference → process again → verified rows are gone and status resets to PENDING.
- **Recommended fix:** Skip deletion of `VERIFIED` rows, or introduce an extraction-run/version model so old runs are retained and verified records are re-linked. Add a regression test.
- **Implementation risk:** Medium — touches core processing logic; needs careful handling of duplicate detection and re-linking.

### FINDING-002: No production secret-key guard
- **Status:** CONFIRMED
- **Severity:** P1
- **Files:** `backend/app/core/config.py`, `backend/app/main.py`, `docker-compose.yml`, `.env.example`
- **Evidence:** `config.py:24` default `secret_key = "change-this-development-secret"`; `docker-compose.yml:23` sets that exact value; no startup validation exists in the `lifespan` handler (`main.py:23-32`).
- **Impact:** JWTs can be forged if the app runs in production with the default key.
- **Reproduction/verification:** Set `ENVIRONMENT=production` with the default key — the app still boots.
- **Recommended fix:** In `lifespan`/config, raise if `environment == "production"` and `secret_key` is the default. ~4 lines.
- **Implementation risk:** Low.

### FINDING-003: CSV formula injection in exports
- **Status:** CONFIRMED
- **Severity:** P1
- **Files:** `backend/app/services/export_service.py`
- **Evidence:** `writer.writerow([...])` at 41-62 and 106-118 writes raw titles, notes, reference text, and section headings (all PDF- or user-derived) with no sanitization.
- **Impact:** A cell beginning with `=`, `+`, `-`, or `@` can execute as a formula when opened in Excel/Sheets.
- **Reproduction/verification:** Save an item whose note is `=HYPERLINK(...)`, export CSV, open in Excel.
- **Recommended fix:** Prefix risky cells with `'`. Apply to all user/PDF-derived cells.
- **Implementation risk:** Low.

### FINDING-004: Fuzzy Act-title mapping without ranking
- **Status:** CONFIRMED
- **Severity:** P1
- **Files:** `backend/app/services/reference_mapper.py`
- **Evidence:** 188-195 take the first `ilike` partial-title match via `.first()` with no candidate ranking, similarity score, or margin. `_mapping_confidence` (265-274) gives a partial+section match 0.88, which clears the 0.85 auto-accept threshold (91-92) — so a wrong partial match can be auto-accepted rather than flagged.
- **Impact:** A reference can be silently mapped to the wrong Act, which is worse than leaving it unresolved.
- **Reproduction/verification:** Two Acts with overlapping title tokens; the arbitrary first row wins.
- **Recommended fix:** Rank candidates (exact number+year > exact title > token overlap > edit distance); require minimum score and margin; otherwise `NEEDS_REVIEW`.
- **Implementation risk:** Medium.

### FINDING-005: Principal enactment inferred from first doc-wide match
- **Status:** CONFIRMED
- **Severity:** P1
- **Files:** `backend/app/services/reference_mapper.py`
- **Evidence:** `build_mapping_context` (38-50) selects the principal Act from the first mappable non-principal reference across the whole document, then reuses it for all "principal enactment" references (152-169). No per-section / closest-preceding-citation logic.
- **Impact:** In documents that cite multiple Acts, "the principal enactment" can resolve to the wrong Act.
- **Reproduction/verification:** Amending Act citing several other Acts before the principal one.
- **Recommended fix:** Determine principal per source section; prefer the closest preceding Act-level citation; record `principal_source` evidence (a field already exists at line 26).
- **Implementation risk:** Medium.

### FINDING-006: No CI pipeline
- **Status:** CONFIRMED
- **Severity:** P1
- **Files:** (absent) `.github/workflows/`
- **Evidence:** No workflow files exist in the repo.
- **Impact:** Regressions (including the deprecation warnings and the P0 above) are not caught automatically.
- **Reproduction/verification:** `ls .github/workflows` → none.
- **Recommended fix:** Add `ci.yml`: backend ruff + pytest; frontend `npm ci` + typecheck + test + build.
- **Implementation risk:** Low.

### FINDING-007: Synchronous PDF processing
- **Status:** CONFIRMED
- **Severity:** P1
- **Files:** `backend/app/api/routes/acts.py`, `backend/app/services/document_processor.py`
- **Evidence:** `process_uploaded_act` (164-173) calls `process_act()` inline in the request. Docling parsing can be slow; there is a `ProcessingJob` model and polling endpoint (176-189) but processing itself is not offloaded.
- **Impact:** Long requests, timeouts, and blocked workers on large PDFs.
- **Reproduction/verification:** Process a large/scanned PDF and observe request duration.
- **Recommended fix:** Minimum: FastAPI `BackgroundTasks`. Better: RQ/arq/Celery with the existing `ProcessingJob` polling and retry/failure states.
- **Implementation risk:** Medium.

### FINDING-008: No rate limiting on auth
- **Status:** CONFIRMED
- **Severity:** P1
- **Files:** `backend/app/api/routes/auth.py`, `backend/requirements.txt`
- **Evidence:** `/auth/login` and `/auth/register` have no throttling; no limiter dependency present.
- **Impact:** Credential-stuffing / brute-force and registration abuse.
- **Recommended fix:** Add `slowapi` or middleware; limit by IP + email; log repeated failures.
- **Implementation risk:** Low.

### FINDING-009: Broad reference regex false-positive risk
- **Status:** PARTIAL
- **Severity:** P2
- **Files:** `backend/app/services/reference_extractor.py`
- **Evidence:** `SECTION_RE`, `SUBSECTION_RE`, `PARAGRAPH_RE`, `ITEM_RE`, `SCHEDULE_RE`, `CHAPTER_RE` are applied globally (185-203). `classify_relationship` (232-239) uses the surrounding ~160-char window (not sentence-bounded) and falls back to `REFERS_TO` for any text containing "section"/"act". **Mitigations already present:** confidence scoring + auto `NEEDS_REVIEW` (84-88), and General Users only see `VERIFIED` + mapped references (`search_service.py:305-314`). So false positives are contained for General Users but still pollute Admin/Lawyer views.
- **Impact:** Noisy low-value references for privileged roles; extra verification burden.
- **Recommended fix:** Sentence-bounded windows; require operative verbs for AMENDS/REPEALS/etc.; add false-positive regression tests.
- **Implementation risk:** Medium.

### FINDING-010: Metadata extraction limitations
- **Status:** CONFIRMED
- **Severity:** P2
- **Files:** `backend/app/services/metadata_extractor.py`
- **Evidence:** `extract_metadata` scans only `text[:4000]` (44); `_looks_like_title` requires `\bact\b` (112), so "Ordinance" titles are not recognized as titles. Provenance (confidence + warnings) IS recorded (56-70).
- **Impact:** Ordinances and Acts with atypical title placement get filename-fallback titles.
- **Recommended fix:** Scan more pages; add Ordinance support; add tests for Ordinance/missing title/date variants.
- **Implementation risk:** Low.

### FINDING-011: Static health endpoint
- **Status:** CONFIRMED
- **Severity:** P2
- **Files:** `backend/app/main.py`
- **Evidence:** `/health` returns `{"status": "ok", ...}` with no dependency checks (43-45).
- **Impact:** Orchestrators/load balancers can route traffic to an instance with a dead DB or unwritable upload dir.
- **Recommended fix:** Verify DB `SELECT 1`, upload dir writable, parser config valid.
- **Implementation risk:** Low.

### FINDING-012: Alembic vs create_all conflict
- **Status:** CONFIRMED
- **Severity:** P2
- **Files:** `backend/app/db/session.py`, `backend/app/main.py`, `backend/alembic/versions/`
- **Evidence:** `init_db()` calls `Base.metadata.create_all()` (session.py:27), invoked in `lifespan` (main.py:25). Two Alembic migrations also exist. Docker does not run `alembic upgrade head`.
- **Impact:** Schema drift between `create_all` and migrations; ambiguous source of truth.
- **Recommended fix:** Alembic as source of truth; restrict `create_all` to tests; run `alembic upgrade head` in the Docker entrypoint/CI.
- **Implementation risk:** Low-Medium.

### FINDING-013: ILIKE-only search
- **Status:** CONFIRMED
- **Severity:** P2
- **Files:** `backend/app/services/search_service.py`
- **Evidence:** All matching uses `ilike`; ranking is a hand-written Python score (`_act_score`/`_section_score`/`_reference_score`). No `tsvector`/GIN.
- **Impact:** Acceptable at MVP scale; weak relevance and performance as the corpus grows.
- **Recommended fix:** Postgres full-text search + `ts_rank` for production; keep ILIKE fallback for SQLite/local. Add search evaluation tests.
- **Implementation risk:** Medium.

### FINDING-014: JWT storage / logout / TTL
- **Status:** CONFIRMED
- **Severity:** P2
- **Files:** `frontend/lib/auth.ts`, `frontend/lib/api.ts`, `backend/app/core/config.py`, `backend/app/api/routes/auth.py`
- **Evidence:** Token stored in `localStorage` (auth.ts:7-23), sent as `Bearer` (api.ts:36); `access_token_expire_minutes=480` (8h, config.py:25); `/auth/logout` only tells the client to discard the token (auth.py:48-50). No refresh token or revocation table.
- **Impact:** XSS token theft risk; no server-side revocation; long token lifetime.
- **Recommended fix:** httpOnly+Secure+SameSite cookie, shorter access TTL, refresh-token table, CSRF handling. (Reasonable to document as a known limitation for the MVP.)
- **Implementation risk:** Medium-High (auth changes are invasive).

### FINDING-015: Upload content sniffing
- **Status:** PARTIAL
- **Severity:** P2
- **Files:** `backend/app/api/routes/acts.py`
- **Evidence:** Validation checks extension, MIME set, `%PDF-` signature, size, and SHA-256 dedupe (72-86). No `python-magic`/libmagic deep sniffing.
- **Impact:** Low residual risk; the magic-byte + size checks already block most malformed uploads.
- **Recommended fix:** Add `python-magic` (or a platform-safe equivalent) as defense-in-depth.
- **Implementation risk:** Low (Windows libmagic packaging needs care).

### FINDING-016: Frontend form validation stack
- **Status:** CONFIRMED
- **Severity:** P2
- **Files:** `frontend/package.json`, `frontend/app/*`
- **Evidence:** No `react-hook-form` or `zod` dependency; forms rely on manual `useState`.
- **Impact:** Inconsistent validation/error UX, especially in Admin metadata/reference/gold-reference forms.
- **Recommended fix:** Add React Hook Form + Zod with reusable field/error components.
- **Implementation risk:** Low.

### FINDING-017: Relationship graph is a list, not a graph
- **Status:** CONFIRMED
- **Severity:** P2
- **Files:** `frontend/components/relationship-graph.tsx`, `frontend/package.json`
- **Evidence:** No graph library (`reactflow`) present; the component renders rows.
- **Impact:** Weaker UX for exploring Act/section relationships.
- **Recommended fix:** React Flow node/edge graph with confidence/status badges; keep table as a detail view.
- **Implementation risk:** Low-Medium.

### FINDING-018: OCR fallback (deferred by design)
- **Status:** NOT_FOUND (intentional)
- **Severity:** P2 / future
- **Files:** `backend/app/core/config.py`, `backend/app/services/pdf_parser/ocr_parser.py`
- **Evidence:** `ocr_enabled=False`; scanned PDFs raise a clear "OCR disabled for this MVP" error (`document_processor.py:79-90`).
- **Recommended fix:** Add Tesseract fallback later; mark OCR output `NEEDS_REVIEW` with confidence.
- **Implementation risk:** Medium.

### FINDING-019: Semantic search / pgvector (deferred by design)
- **Status:** NOT_FOUND (intentional)
- **Severity:** future
- **Files:** `backend/app/services/embedding_service.py`
- **Evidence:** Stub with `enabled = False`, `embed()` returns `None`.
- **Recommended fix:** After full-text search stabilizes: section/chunk embeddings + pgvector + retrieval evaluation.
- **Implementation risk:** High.

---

## Tests and Commands Run

| Command | Result |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `a467031c02e2d67952666f889df32da1f2458f80` |
| `backend/.venv\Scripts\python -m pytest -q` | **PASS**, exit code 0 (only `datetime.utcnow()` DeprecationWarnings) |

---

## Recommended Implementation Order

1. **F-001** — Preserve verified sections/references on reprocess (P0).
2. Add a regression test proving verified data survives reprocess.
3. **F-002** — Production secret-key guard.
4. **F-003** — CSV formula-injection sanitizer.
5. **F-006** — GitHub Actions CI (locks in all of the above).
6. **F-004 / F-005** — Mapping ranking + principal-enactment context.
7. **F-007** — Background processing.
8. **F-008 / F-011 / F-012** — Rate limiting, deep health check, Alembic as source of truth.
9. **F-010 / F-009** — Metadata (Ordinance) + false-positive tightening + tests.
10. **F-013** — Postgres full-text search.
11. **F-014 / F-015** — Auth hardening + upload sniffing.
12. **F-016 / F-017** — Frontend validation + React Flow graph.
13. **F-018 / F-019** — OCR, then semantic search (last).

---

## Unknowns / Needs Runtime Verification

- **F-009 severity in practice:** the real false-positive rate needs a labeled corpus run (use the existing evaluation service + a seed gold dataset).
- **F-013 search relevance:** requires a search-quality evaluation set to quantify the ILIKE gap.
- **Docling runtime behavior:** parser performance/timeouts on large real Sri Lankan Act PDFs is not verifiable statically (F-007 impact).
- **F-015 libmagic on Windows:** feasibility of `python-magic` on the target OS needs a runtime check.
