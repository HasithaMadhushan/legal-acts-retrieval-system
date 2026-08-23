# LexAtlas — Automated Legal Acts Retrieval System

Section-level retrieval, statutory reference extraction and mapping, Admin verification, attorney-verified lawyer access, and evaluation metrics for English-language Sri Lankan Legal Acts.

Machine-extracted references are labeled and hidden from General Users until verified by an Admin — the system presents retrieval support, not authoritative law. Always verify legal material against official sources.

## Features

- **Ingest:** PDF upload (SHA-256 dedupe, optional metadata) → Docling/PyMuPDF extraction → section segmentation → regex reference extraction → fuzzy mapping with confidence bands.
- **Verify:** Admin split-view verification of sections and references (verify / reject / link-target), preserved across reprocessing.
- **Search:** keyword + Postgres full-text with filters; semantic mode planned (pgvector — see `docs/pgvector-and-llm-extraction.md`).
- **Roles:** Admin (corpus + governance), Lawyer (attorney-verified: workspace, exports, relationship tools), General User (verified content only).
- **Product features:** attorney verification with proof upload, password reset, reading history ("Continue reading"), saved workspace with CSV/Markdown export.
- **Evaluation:** gold-reference precision/recall/F1 with confusion breakdown and corpus-wide metrics summary.
- **Design:** LexAtlas design system (navy/gold/parchment) with high-fidelity mockups in `design/mockups/`.

## Stack

- Backend: Python 3.13, FastAPI, SQLAlchemy 2, Pydantic v2, JWT, bcrypt, PyMuPDF + Docling.
- Frontend: Next.js 16 (App Router), React 19, TypeScript, Tailwind v4 + shadcn/ui.
- Database: PostgreSQL 16 in Docker; SQLite fallback for local dev/tests.
- Ops: Gunicorn + uvicorn workers, structured logging, optional Sentry, rate limiting, Caddy TLS overlay, CI (ruff/pytest/typecheck/build).

## Demo Accounts

Demo accounts for all three roles are seeded automatically on backend startup (see `backend/app/db/seed.py`). Sign in at http://127.0.0.1:3000/login after `docker compose up`.

## Docker Setup (recommended)

Runs PostgreSQL, FastAPI backend, and Next.js frontend together. No local Python/Node install required.

```bash
cd legal-acts-retrieval-system

# First time or after code changes
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

Open:

- Frontend: http://127.0.0.1:3000
- Backend health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

Postgres is **not** published to host port `5432` (avoids conflict with a system PostgreSQL install). The backend reaches it as `db:5432` inside the compose network. For ad-hoc SQL:

```bash
docker compose exec db psql -U legal_acts -d legal_acts
```

After UI or API changes, rebuild the affected service:

```bash
docker compose up --build -d backend    # backend only
docker compose up --build -d frontend   # frontend only
```

Data persists in Docker volumes (`postgres_data`, `backend_uploads`) until you run `docker compose down -v`.

### Production deployment

`docker-compose.prod.yml` overlays the file above (secrets, JSON logs, Caddy HTTPS). See that file's header and `PRODUCTION_ROADMAP.md` Phase 3.

## Local Setup (without Docker)

```bash
cd legal-acts-retrieval-system

python3 -m venv backend/.venv
source backend/.venv/bin/activate   # Windows: backend\.venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# separate terminal
cd frontend && npm install && npm run dev -- -H 127.0.0.1 -p 3000
```

Uses SQLite by default (`backend/legal_acts.db`). Good for fast UI iteration; use Docker for Postgres full-text search behavior.

## Core Workflows

**Admin:** upload PDF → process (live pipeline progress) → review sections & references → verify/reject/link targets → approve attorney requests → run evaluation.

**Lawyer (attorney-verified):** register → upload proof → admin approval → advanced search with relationship filters → save items + notes to workspace → export CSV/Markdown.

**General user:** register → search & browse verified Acts → read sections (reading history tracked) → resume from dashboard.

**Evaluation:** enter or import gold references → run evaluation → precision/recall/F1 with FP/FN breakdown.

## Final Demo Setup

1. Start the project locally or with Docker Compose.
2. Use the demo accounts above only; do not use real personal credentials.
3. Prepare 8-12 public/sample English-language Sri Lankan Legal Act PDFs.
4. Include amendment Acts, principal Acts, one schedule-heavy Act, one longer Act, and Acts with cross-references.
5. Manually verify 30-50 references as gold data before presenting evaluation results.
6. Follow the Admin → Lawyer → General User walkthrough below.

## Evaluation Method

Evaluation is deterministic and rule-based. Admin users add manually verified gold references, run the evaluation, and report precision, recall, F1-score, mismatch examples, section segmentation accuracy where section identifiers are available, mapping counts, verification counts, and processing warnings.

## Project Limits

- English Legal Act PDFs only; no OCR yet (scanned PDFs fail processing).
- No chatbot and no personalized legal advice generation.
- Extracted references are labeled and not authoritative until verified by an Admin.
- Semantic search is not implemented yet (`search_mode=semantic` returns 501); keyword + full-text are the baseline.
- PDF extraction quality depends on source PDF quality; rule-based extraction can miss complex drafting (LLM hybrid extraction planned).
- Unresolved references require Admin review.
- Evaluation results must be based on manually verified gold data; do not invent accuracy numbers.

