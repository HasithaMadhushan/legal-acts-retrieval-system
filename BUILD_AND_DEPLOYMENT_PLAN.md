# BUILD_AND_DEPLOYMENT_PLAN.md

## 1. Executive Summary

The project is an academic MVP for section-level retrieval and statutory reference mapping of selected English-language Sri Lankan Legal Act PDFs. The repository already contains more than Phase 1 and Phase 2: FastAPI backend, Next.js frontend, SQLAlchemy models, JWT authentication, role guards, PDF upload, processing, reference extraction, search, relationship views, saved items, exports, evaluation endpoints, tests, Dockerfiles, and Docker Compose.

The main technical direction should be:

- Keep the current monorepo and preserve existing work.
- Use PostgreSQL as the main project database.
- Keep SQLite only as a lightweight local/test fallback.
- Add Alembic migration revisions before treating PostgreSQL deployment as production-ready.
- Keep keyword and metadata search as the required baseline.
- Add pgvector only after baseline search and verification workflows are stable.
- Deploy the academic demo on a single VPS with Docker Compose, a reverse proxy, persistent uploads, PostgreSQL backups, and clear legal disclaimers.

Legal boundary: the system must remain a legal information retrieval support prototype only. It must not provide legal advice, legal opinions, legal conclusions, legal recommendations, or authoritative consolidation.

## 2. Current Repository Audit

### Repository Structure

Current root:

```text
legal-acts-retrieval-system/
  backend/
  frontend/
  docker-compose.yml
  .env.example
  .gitignore
  README.md
  PRD.md
  AGENTS.md
```

Backend:

- `backend/app/main.py`: FastAPI app, CORS, health endpoint, legal disclaimer endpoint, route registration.
- `backend/app/core/`: configuration, roles/enums, security, legal-safety checks.
- `backend/app/db/`: SQLAlchemy base/session and demo user seed logic.
- `backend/app/models/`: SQLAlchemy models for users, acts, sections, references, processing jobs, saved items, evaluation.
- `backend/app/schemas/`: Pydantic request/response schemas.
- `backend/app/api/routes/`: auth, users, acts, sections, references, search, relationships, saved items, exports, evaluation.
- `backend/app/services/`: PDF parsing, text cleaning, metadata extraction, section segmentation, reference extraction/mapping, search, export, evaluation.
- `backend/app/tests/`: pytest tests for auth, upload permissions, segmentation, references, search, evaluation.

Frontend:

- `frontend/app/`: Next.js App Router pages for login, register, search, Act/section detail, Admin, Lawyer, dashboard.
- `frontend/components/`: shared UI components including role guard, legal disclaimer, upload, tables, graph, viewer.
- `frontend/lib/`: API client, auth helpers, shared types.
- `frontend/tests/`: Vitest smoke tests.

### Already Implemented

- FastAPI app with `/health` and `/api/v1/legal-disclaimer`.
- JWT login, current-user endpoint, registration, logout response.
- Demo users: Admin, Lawyer, General User.
- Role-based backend dependencies: Admin-only and Lawyer/Admin.
- Frontend token storage for MVP, role-aware navigation, logout, protected route guard.
- SQLAlchemy domain models for the main MVP.
- Docker Compose with PostgreSQL, backend, and frontend services.
- Local SQLite default via `DATABASE_URL=sqlite:///./legal_acts.db`.
- PDF upload endpoint with Admin-only access, generated safe filename, SHA-256 duplicate check.
- PyMuPDF parser and optional Docling adapter path.
- Processing job model and synchronous document processing service.
- Metadata extraction, section segmentation, reference extraction, normalization, mapping.
- Admin verification endpoints for sections and references.
- Keyword/metadata search service.
- Basic relationship table/graph API and frontend.
- Lawyer saved-items API and frontend workspace.
- CSV/Markdown export service.
- Evaluation gold references and run metrics.
- Backend tests and frontend type/build/test scripts.

### Missing or Incomplete

- Alembic has `env.py`, but no migration revision files. Current startup uses `Base.metadata.create_all`.
- PostgreSQL full-text indexes are not implemented yet.
- pgvector is not configured yet.
- No separate `uploaded_files`, `extracted_text`, `processing_logs`, `verification_history`, or `audit_logs` tables.
- Upload validation should add MIME detection and stored file size.
- Docling is optional by interface only; PyMuPDF is the practical parser today.
- OCR is only a placeholder.
- Document processing is synchronous; long PDFs can block the request.
- Search is simple SQL `ilike`, not production PostgreSQL full-text.
- Admin reference creation/manual correction UI is basic and should be expanded.
- Frontend pages are MVP-level and need stronger loading/error states and form validation.
- Docker Compose is good for local development but incomplete for production: no reverse proxy, SSL, secrets, backups, migration step, or app health checks.
- Docker is not currently installed or not on PATH in this local environment, so `docker compose config` cannot run here.

### Current Database Use

- SQLite: default local/test fallback through `.env.example` and `Settings.database_url`.
- PostgreSQL: Docker Compose target through backend `DATABASE_URL=postgresql+psycopg://...`.
- Current table creation: SQLAlchemy `Base.metadata.create_all()` on app startup.
- Migration state: Alembic configured but not yet used with revision files.

### Current Local Development

Without Docker, backend runs against SQLite and frontend runs with npm. With Docker installed, Compose should start PostgreSQL, backend, and frontend containers, but production hardening is still needed.

## 3. Recommended Architecture

### Runtime Components

- Frontend: Next.js app served on `http://localhost:3000` locally.
- Backend API: FastAPI served on `http://127.0.0.1:8000` locally.
- Database: PostgreSQL 16 in Docker for integrated local runs and production-like testing.
- Local fallback: SQLite for quick tests and machines without Docker.
- File storage: local `uploads/` folder or Docker volume for MVP.
- Optional semantic search: pgvector extension in PostgreSQL later.

### Data Flow

1. Admin logs in.
2. Admin uploads a PDF.
3. Backend validates and stores the file with a generated filename.
4. Backend creates a LegalAct row with `UPLOADED` status.
5. Admin triggers processing.
6. Processing extracts text, cleans text, extracts metadata, segments sections, extracts references, maps references, records job summary.
7. Admin verifies/rejects/corrects sections and references.
8. Lawyer and General User search verified data according to role.
9. Evaluation module compares extracted references with manually entered gold samples.

## 4. Database Decision

### Decision

Use PostgreSQL as the main database. Keep SQLite only as a development/test fallback. Add pgvector only after keyword and metadata search are stable.

### Why PostgreSQL

PostgreSQL fits this project better than MongoDB or Firebase because the domain is relational:

- Acts have many sections.
- Sections have many references.
- References map source Acts/sections to target Acts/sections.
- Users have roles and saved items.
- Verification and evaluation require joins, constraints, transactions, and indexes.
- PostgreSQL supports strong relational integrity, JSON summaries where needed, full-text search, and optional pgvector in one database.

MongoDB is less suitable because legal references and verification workflows need relational joins and constraints. Firebase is less suitable because the backend needs server-side PDF processing, structured SQL querying, local Docker deployment, and academic explainability.

### Entity Plan

| Entity | Purpose | Key Fields | Relationships | Indexes | Status |
|---|---|---|---|---|---|
| `users` | Auth and role management | `id`, `full_name`, `email`, `hashed_password`, `role`, `is_active` | uploads Acts, verifies refs, saved items | unique/index `email`, `role` optional | Required now, implemented |
| role field | Role-based permissions | `ADMIN`, `LAWYER`, `GENERAL_USER` enum | stored on `users` | role index optional | Required now, implemented |
| `legal_acts` | Main uploaded Act record | title, normalized title, act number, year, source filename, stored path, hash, raw text, status | user, sections, refs | title, normalized title, number, year, status, hash | Required now, implemented |
| uploaded files | File-specific metadata | original name, stored name/path, size, MIME, hash | belongs to Act | hash, upload date | Currently folded into `legal_acts`; separate table later |
| extracted text | Raw/cleaned text history | raw text, cleaned text, parser, warnings | belongs to Act/job | act id, parser | Raw text in `legal_acts`; cleaned text not separately stored |
| processing logs | Processing trace | status, step, progress, error, summary JSON | belongs to Act/user | act id, status, created_at | Required now, implemented as `processing_jobs` |
| act metadata | Editable legal metadata | title, number, year, dates, category, source URL | belongs to Act | title, number, year | Currently part of `legal_acts` |
| `act_sections` | Searchable sections | section number/path, heading, text, normalized text, type, status | belongs to Act; parent section | act id, number, path, status, sort order | Required now, implemented |
| `legal_references` | Extracted references and relationships | raw text, snippet, relationship type, target fields, confidence, status | source/target Act and section; verifier | source ids, target ids, type, status | Required now, implemented |
| reference mappings | Mapping source to target | source ids, target ids, confidence | self-contained in references | target/source indexes | Implemented inside `legal_references`; separate table later only if needed |
| verification status records | Verification history | item type, item id, old/new status, user, notes | user + verified item | item id, user, timestamp | Current status fields only; history later |
| `saved_items` | Lawyer/Admin workspace | user, type, act/section/ref id, note | belongs to user and selected item | user id, item ids | Required for workspace, implemented |
| `evaluation_gold_references` | Manual gold samples | expected raw text/type/target | optional Act/section | act id | Required for evaluation, implemented |
| `evaluation_runs` | Evaluation outputs | precision, recall, F1, counts, JSON | optional Act | act id, created_at | Required for evaluation, implemented |
| audit logs | Admin changes and safety trace | actor, action, target, before/after, timestamp | user + target | actor, action, timestamp | Later; useful before production/public demo |

## 5. Local Development Setup

### Backend URL

`http://127.0.0.1:8000`

### Frontend URL

`http://127.0.0.1:3000`

### PostgreSQL URL

Docker Compose:

```text
postgresql+psycopg://legal_acts:legal_acts@localhost:5432/legal_acts
```

Inside backend container:

```text
postgresql+psycopg://legal_acts:legal_acts@db:5432/legal_acts
```

### Uploads Directory

- Local no-Docker: `backend/uploads/`
- Docker: named volume mounted at `/app/uploads`
- Git: ignored by `.gitignore`

### Backend PowerShell Commands

From repository root:

```powershell
cd C:\Users\h.user\Desktop\Final_Project\legal-acts-retrieval-system
python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

Run checks:

```powershell
cd backend
.venv\Scripts\python -m ruff check app
.venv\Scripts\python -m pytest
```

Start backend with SQLite fallback:

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start backend with PostgreSQL:

```powershell
cd backend
$env:DATABASE_URL="postgresql+psycopg://legal_acts:legal_acts@localhost:5432/legal_acts"
.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend PowerShell Commands

```powershell
cd frontend
npm install
npm run typecheck
npm test
npm run build
npm run dev -- -H 127.0.0.1 -p 3000
```

### Docker Compose Local Run

If Docker is installed:

```powershell
cd C:\Users\h.user\Desktop\Final_Project\legal-acts-retrieval-system
docker compose config
docker compose up --build
```

If Docker is not installed:

- Use SQLite fallback for backend.
- Run frontend with `npm run dev`.
- Install PostgreSQL locally only if PostgreSQL-specific behavior must be tested.

## 6. Environment Variable Plan

### Backend Variables

| Variable | Purpose | Example for `.env.example` | Commit real value? |
|---|---|---|---|
| `APP_NAME` | Display/API metadata | `Automated Legal Acts Retrieval System` | Safe |
| `ENVIRONMENT` | `development`, `test`, `production` | `development` | Safe |
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///./legal_acts.db` | No for production |
| `SECRET_KEY` or `JWT_SECRET_KEY` | JWT signing secret | `change-this-development-secret` | Never real secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime | `480` | Safe |
| `CORS_ORIGINS` | Allowed frontend origins | `http://localhost:3000,http://127.0.0.1:3000` | Safe if non-secret |
| `UPLOAD_DIR` | Upload storage path | `uploads` | Safe |
| `MAX_UPLOAD_SIZE_MB` | Upload limit | `50` | Safe |
| `DOCLING_ENABLED` | Try Docling parser | `true` | Safe |
| `DOCLING_TIMEOUT_SECONDS` | Docling conversion timeout before PyMuPDF fallback | `60` | Safe |
| `OCR_ENABLED` | Future OCR fallback | `false` | Safe |
| `ENABLE_PGVECTOR` | Future semantic search gate | `false` | Safe |
| `DOC_PARSER_PRIMARY` | Primary parser selector | `docling` or `pymupdf` | Safe |

Production secrets must live in `.env`, Docker secrets, or server environment variables. Never commit production `DATABASE_URL`, JWT secret, SMTP/API keys, or cloud credentials.

### Frontend Variables

| Variable | Purpose | Example |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Browser API base URL | `http://127.0.0.1:8000/api/v1` locally, `/api/v1` behind same-domain reverse proxy |

Only `NEXT_PUBLIC_*` values are exposed to the browser.

## 7. Backend Build Plan From Phase 3 Onward

### Existing Backend Architecture

- App entry: `app/main.py`
- Routers: `app/api/routes/*`
- Auth dependencies: `app/api/deps.py`
- Config/security: `app/core/*`
- Models: `app/models/*`
- Schemas: `app/schemas/*`
- Services: `app/services/*`
- Database/session: `app/db/*`

### Phase 3: Document Upload and Management

- Keep current upload endpoint but harden validation.
- Add MIME detection and stored file size to Act or a new `uploaded_files` table.
- Confirm duplicate hash behavior and Admin-only access.
- Add tests for MIME, size, duplicate, path traversal, and non-admin blocking.
- Improve Admin document list filters/status display.

### Phase 4: PDF Extraction Pipeline

- Use Docling as the primary parser for richer document conversion.
- Keep PyMuPDF fallback as the reliable baseline when Docling is unavailable or fails.
- Keep explicit parser selection using `DOC_PARSER_PRIMARY`.
- Store parser warnings in `processing_jobs.summary_json`.
- Decide whether to store cleaned text in `legal_acts` or a new extracted-text table.
- Make processing safe for failures and large PDFs.
- Later: move long-running processing to background task or queue.

### Phase 5: Metadata Extraction

- Keep current regex-based extractor.
- Add Admin editable fields and uncertainty status.
- Add tests for Act number/year/title/certified date patterns.
- Add source URL/name validation.

### Phase 6: Section Segmentation

- Keep current section drafts and `act_sections`.
- Improve schedule/part/subsection handling incrementally.
- Preserve sort order and parent-child links.
- Add tests for section gaps, schedules, parts, and no-section fallback.

### Phase 7: Reference Extraction

- Keep centralized `reference_patterns.py`.
- Add patterns gradually for Sri Lankan Act citation variants.
- Add deduplication by source section + raw reference + target.
- Add tests for amendments, repeals, insertions, substitutions, cross-references.

### Phase 8: Normalization and Mapping

- Keep current mapper but add stricter confidence policy.
- Add unresolved status reporting.
- Add fuzzy matching only with deterministic rules and review status.

### Phase 9: Admin Verification

- Add manual reference creation endpoint if missing.
- Add verification history or audit log if time allows.
- Ensure General Users only see verified references.

### Phase 10: Search and Retrieval

- Replace `ilike` baseline with PostgreSQL full-text search when using PostgreSQL.
- Add indexes and ranking.
- Keep semantic search optional.
- Do not use paid external AI APIs.

### Phase 11-14

- Relationship views: expand table and graph after verified reference flow is stable.
- Lawyer workspace: strengthen saved item ownership and export filters.
- General User: simplify search and hide unverified data.
- Evaluation: add dashboard counts and sample import/export.

## 8. Frontend Build Plan From Phase 3 Onward

### Existing Frontend Architecture

- App Router pages under `frontend/app`.
- `RoleGuard` validates token through `/auth/me`.
- `AppShell` renders role-aware navigation and logout.
- `api.ts` centralizes fetch and bearer token attachment.
- `LegalDisclaimer` is shared and visible on key pages.

### Phase 3: Upload and Admin Document Management

- Keep `UploadDropzone`.
- Add client-side file type/size messaging matching backend limits.
- Improve Admin Acts page filters and refresh state after upload/process.
- Show source filename, upload date, and processing status clearly.

### Phase 4-6: Processing, Metadata, Sections

- Add processing job detail/log display.
- Add metadata edit form with validation.
- Add section review UI with status badges and save feedback.
- Add loading and error states for all Admin document pages.

### Phase 7-9: Reference Extraction and Verification

- Expand reference table filters by type/status.
- Add edit/correct modal for target fields.
- Add manual target link controls.
- Add manual reference creation after backend support.

### Phase 10-13: Search, Relationships, Workspace, General UI

- General search: simple query, metadata filters, verified-only references.
- Lawyer search: advanced filters, optional pending results clearly marked.
- Relationship page: keep table primary; graph is secondary.
- Workspace: save/unsave from result cards and detail pages, export CSV/Markdown.

### Phase 14: Evaluation UI

- Add count cards: Acts, sections, references, verified, rejected, unresolved.
- Add gold sample form/import.
- Show precision, recall, F1, segmentation accuracy.

## 9. Deployment Strategy Comparison

### Option A: Single VPS with Docker Compose

Pros:

- Runs frontend, backend, PostgreSQL, uploads, reverse proxy, and backups in one place.
- Best fit for PDF processing and local file uploads.
- Simple mental model for academic demonstration.
- Easy to preserve uploaded files with Docker volumes.
- Docker Compose is already part of the repo.

Cons:

- Requires server administration.
- Requires SSL, firewall, backups, and monitoring setup.
- Single server is a single point of failure unless backups are reliable.

Cost/complexity: medium.

Upload/PDF suitability: high.

Database suitability: high with PostgreSQL container or managed PostgreSQL.

Backup: use `pg_dump` plus uploads volume archive.

Suitability: recommended.

### Option B: Split Deployment

Example: Vercel frontend + Render/Fly/Railway backend + Supabase/Neon PostgreSQL.

Pros:

- Managed services reduce some server maintenance.
- Vercel is strong for Next.js.
- Managed PostgreSQL improves backup/reliability.

Cons:

- File uploads and PDF processing are harder across multiple providers.
- Backend may need persistent disk or cloud object storage.
- Cross-origin auth/CORS is more complex.
- Free/low-cost tiers may sleep, throttle, or limit file processing.

Cost/complexity: medium to high.

Upload/PDF suitability: medium unless adding object storage.

Database suitability: high if Supabase/Neon/PostgreSQL is used.

Backup: mostly managed DB backup plus object storage backup.

Suitability: acceptable later, not the simplest MVP path.

### Option C: Local-Only Academic Demo

Pros:

- Lowest cost.
- No public security exposure.
- Easiest for development.

Cons:

- Not accessible to supervisors remotely.
- Demo depends on one machine.
- No production deployment learning outcome.

Cost/complexity: low.

Upload/PDF suitability: high locally.

Database suitability: SQLite or local PostgreSQL.

Backup: copy project, database, and uploads manually.

Suitability: acceptable fallback, but not best final deployment.

### Recommendation

Use Option A: single VPS with Docker Compose for demo/production. It best matches this system because the backend needs PDF processing, persistent uploads, PostgreSQL, and predictable networking. Use Caddy or Nginx as reverse proxy. Caddy is simpler for SSL because it can manage HTTPS automatically. Docker Compose remains the orchestration tool; official Docker Compose docs are the reference for service composition. Caddy automatic HTTPS and PostgreSQL `pg_dump` are appropriate references for SSL and backups.

## 10. Production Deployment Design

### Recommended Public URL Shape

Simplest:

- Frontend: `https://your-domain.com`
- Backend API: `https://your-domain.com/api/v1`

Use same-domain routing to reduce CORS complexity. The reverse proxy routes `/api/*` to backend and all other paths to frontend.

Alternative:

- Frontend: `https://your-domain.com`
- API: `https://api.your-domain.com/api/v1`

Use this only if there is a strong reason to separate domains.

### Container Layout

Production services:

- `proxy`: Caddy or Nginx.
- `frontend`: Next.js standalone/start server.
- `backend`: FastAPI app with Uvicorn/Gunicorn.
- `db`: PostgreSQL 16, or external managed PostgreSQL.
- `backup`: optional scheduled backup container or host cron script.

### Production Backend Command

Prefer Gunicorn with Uvicorn workers after adding dependency:

```text
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000
```

Current Dockerfile uses:

```text
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

This is acceptable for MVP demo, but Gunicorn is better for production-like VPS deployment.

### Production Frontend Command

Current Dockerfile:

```text
npm run build
npm run start
```

Set:

```text
NEXT_PUBLIC_API_BASE_URL=/api/v1
```

when using same-domain reverse proxy.

### Volumes

- `postgres_data:/var/lib/postgresql/data`
- `backend_uploads:/app/uploads`
- `caddy_data:/data`
- `caddy_config:/config`

### Reverse Proxy Routes

Same-domain plan:

- `your-domain.com/api/*` -> backend `backend:8000`
- `your-domain.com/*` -> frontend `frontend:3000`

### SSL Plan

Use Caddy for automatic HTTPS. Configure DNS A record to VPS IP, open ports 80 and 443, and let Caddy obtain/renew certificates.

### Backup Plan

Daily:

- `pg_dump` PostgreSQL database to timestamped file.
- Compress uploads volume.
- Copy backups off-server or to a separate disk/cloud bucket.

Example host cron target:

```powershell
docker exec legal_db pg_dump -U legal_acts legal_acts > backups\legal_acts_%DATE%.sql
```

On Linux VPS use shell date syntax and gzip.

### Log Plan

- Use `docker compose logs`.
- Configure Docker local log rotation.
- Keep backend processing errors in `processing_jobs`.
- For production, add structured logs and request IDs later.

### Security Checklist

- Use strong production `SECRET_KEY`.
- Never commit `.env`.
- Restrict CORS to production domain.
- Use HTTPS only.
- Keep uploads outside public web root.
- Validate file type, extension, MIME, size, and hash.
- Do not serve uploaded PDFs publicly unless intentionally implemented.
- Run database backups.
- Keep OS and Docker updated.
- Rotate demo credentials if publicly exposed.
- Keep legal disclaimers visible.
- Do not add legal advice generation.

## 11. Migration and Seed Plan

### Current Behavior

- SQLAlchemy models define tables.
- `init_db()` calls `Base.metadata.create_all()` at app startup.
- Demo users are seeded at app startup.
- Alembic is configured but has no migration revisions.

### Recommendation

Short term:

- Keep `create_all()` for SQLite local development and tests.
- Keep idempotent demo seed users.

Before VPS production:

- Add Alembic revision files for the current schema.
- Add a migration command to backend Docker entrypoint or deployment runbook.
- Stop relying on automatic `create_all()` in production.
- Keep seed script idempotent and environment-aware.

Seed data:

- Admin demo user: `admin@example.com` / `AdminPass123!`
- Lawyer demo user: `lawyer@example.com` / `LawyerPass123!`
- General demo user: `user@example.com` / `UserPass123!`
- Optional sample Act metadata, sections, and verified references for demo.
- Do not include real participant data or personal credentials.

## 12. File Upload and Storage Plan

Current behavior:

- Admin-only upload endpoint.
- Only `.pdf` extension accepted.
- Size checked against `MAX_UPLOAD_SIZE_MB`.
- SHA-256 hash calculated.
- Duplicate hash rejected.
- Stored filename is generated UUID.
- Original filename stored as `source_file_name`.
- Stored path stored in DB.
- Upload folder ignored by Git.

Next improvements:

- Store file size.
- Store MIME type.
- Validate MIME with file signature/content sniffing.
- Keep generated filenames only.
- Prevent path traversal by never trusting client paths.
- Back up uploads volume with database backups.
- Add optional cloud storage later only if using split deployment.

Future cloud option:

- S3-compatible storage for PDFs.
- Store object key and checksum in DB.
- Keep processing worker able to fetch objects securely.

## 13. Security Plan

- JWT: signed with strong secret; short or moderate expiry; store token in localStorage for MVP only.
- Passwords: bcrypt hashing already implemented.
- RBAC: backend dependencies must enforce Admin and Lawyer/Admin restrictions.
- CORS: local origins for dev; production domain only in production.
- Uploads: extension, MIME, size, hash, generated filename, no path traversal.
- Secrets: `.env` ignored; production values never committed.
- Database: strong password, no public PostgreSQL port in production unless firewalled.
- Legal safety: disclaimer visible on login, search, Act detail, section detail, relationship pages, and exports.
- No legal advice: no chatbot, no personalized recommendations, no authoritative interpretations.
- Privacy: collect only account identity fields needed for demo auth; no participant data unless ethics-approved.
- Admin verification: unverified extraction remains clearly marked and restricted for General Users.

## 14. Testing Plan

### Backend Tests

Required:

- Auth: password hashing, successful login, invalid login, current user, inactive user.
- RBAC: Admin allowed, Lawyer blocked from Admin, General blocked from Lawyer/Admin.
- Public routes: health and legal disclaimer.
- Upload: Admin upload, non-admin blocked, non-PDF rejected, duplicate hash, file size.
- Document CRUD: list/detail/update/delete permissions.
- Processing: job success/failure status, parser fallback, no crash on bad PDFs.
- Metadata extraction: title, Act number, year, certified date.
- Section segmentation: numbered sections, schedules, no lost text.
- Reference extraction: amendment, repeal, insertion, substitution, cross-reference.
- Mapping: exact Act number/year, title match, unresolved review status.
- Search: query, filters, role-specific visibility.
- Evaluation: precision, recall, F1, segmentation accuracy.

Commands:

```powershell
cd backend
.venv\Scripts\python -m ruff check app
.venv\Scripts\python -m pytest
```

### Frontend Tests

Required:

- Login page renders.
- Login error message.
- Role redirect/guard behavior.
- Admin navigation hidden from non-admin.
- Lawyer links hidden from General User.
- Admin upload page protected.
- Document list renders.
- Lawyer search page filters.
- General User restrictions.
- Legal disclaimer display on key pages.

Commands:

```powershell
cd frontend
npm run typecheck
npm test
npm run build
```

### Docker/Build Validation

If Docker is installed:

```powershell
cd ..
docker compose config
docker compose up --build
```

Manual smoke:

- Open frontend.
- Login as Admin.
- Upload sample PDF.
- Process.
- Verify one reference.
- Login as Lawyer.
- Search and save item.
- Export.
- Login as General User.
- Confirm only verified references and disclaimers.

## 15. CI/CD Plan

Use GitHub Actions for validation only at first.

Workflow jobs:

- Backend:
  - setup Python
  - install `backend/requirements.txt`
  - `ruff check app`
  - `pytest`
- Frontend:
  - setup Node
  - `npm ci`
  - `npm run typecheck`
  - `npm test`
  - `npm run build`

No automatic deployment is required initially. For the academic MVP, manual VPS deployment is simpler and easier to explain.

Later optional CI:

- Build Docker images.
- Run `docker compose config`.
- Publish images to GHCR.
- Manual deployment via SSH script.

## 16. Phase-by-Phase Build Roadmap

### Completed

- Phase 1: project foundation.
- Phase 2: authentication and roles.

### Next Phases

Phase 3: Document Upload and Management

- Harden existing upload.
- Add file size/MIME metadata.
- Improve Admin document dashboard.
- Add tests.

Phase 4: PDF Extraction Pipeline

- Strengthen parser selection.
- Store extraction warnings/logs.
- Handle processing failures robustly.

Phase 5: Metadata Extraction

- Improve metadata patterns.
- Add Admin metadata edit workflow.

Phase 6: Section Segmentation

- Improve section, schedule, part, subsection segmentation.
- Add review workflow and tests.

Phase 7: Reference Extraction

- Expand legal citation patterns.
- Add stronger confidence and deduplication.

Phase 8: Normalization and Mapping

- Improve exact/fuzzy mapping and unresolved reporting.

Phase 9: Admin Verification

- Add manual reference creation/correction.
- Add verification history if time allows.

Phase 10: Search and Retrieval

- Add PostgreSQL full-text search.
- Add pgvector only after baseline search is stable.

Phase 11: Relationship Views

- Improve table first; keep graph simple.

Phase 12: Lawyer Workspace

- Add save/unsave from search/detail pages and export polish.

Phase 13: General User UI

- Simplify search and verified-only related references.

Phase 14: Evaluation

- Add metrics dashboard counts and sample comparison.

Phase 15: Final Testing and Documentation

- Complete test report, user manual, deployment guide, final demo checklist.

## 17. Risk List

| Risk | Impact | Mitigation |
|---|---:|---|
| PDF extraction quality varies | High | PyMuPDF fallback, Admin verification, clear processing errors |
| Citation formats are inconsistent | High | Centralized regex patterns, confidence scores, manual correction |
| Synchronous processing blocks requests | Medium | Accept for MVP; move to background worker later |
| PostgreSQL migrations missing | High for deployment | Add Alembic revisions before production |
| Upload storage loss | High | Persistent volume and off-server backups |
| Legal advice misunderstanding | High | Repeated disclaimers, no chatbot, no interpretation generation |
| CORS/auth deployment mismatch | Medium | Prefer same-domain `/api/v1` reverse proxy |
| Docker unavailable on demo machine | Medium | Keep local SQLite fallback and manual backend/frontend commands |
| pgvector overcomplication | Medium | Add only after keyword/metadata search is stable |

## 18. Final Technical Deliverables

- Working source code.
- Full `README.md`.
- Full `PRD.md`.
- `BUILD_AND_DEPLOYMENT_PLAN.md`.
- Database schema documentation.
- Alembic migrations.
- API documentation via FastAPI OpenAPI.
- Deployment guide.
- User manual.
- Test report.
- Evaluation report.
- Final demo checklist.
- Backup/restore instructions.

## 19. Final Recommendation

Continue development on the existing repository. Use PostgreSQL as the primary database, SQLite only for local/test fallback, and Docker Compose as the local and VPS deployment foundation. Before public demo deployment, add Alembic migrations, upload MIME/size metadata, production environment files, reverse proxy, SSL, backups, and a documented manual deployment process.

Recommended deployment: single VPS with Docker Compose, same-domain routing, Caddy reverse proxy, PostgreSQL container or managed PostgreSQL, persistent uploads volume, daily database and upload backups, and manual GitHub Actions-validated releases.

Reference docs used for deployment planning:

- Docker Compose documentation: https://docs.docker.com/compose/
- Caddy automatic HTTPS: https://caddyserver.com/docs/automatic-https
- PostgreSQL `pg_dump`: https://www.postgresql.org/docs/current/app-pgdump.html
- pgvector: https://github.com/pgvector/pgvector
