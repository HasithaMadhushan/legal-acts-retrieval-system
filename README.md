# Automated Legal Acts Retrieval System

Academic MVP for section-level retrieval, statutory reference extraction, Admin verification, role-based legal research access, and evaluation metrics for English-language Sri Lankan Legal Acts.

## Legal Status

This system is an academic research prototype for legal information retrieval support only. It does not provide legal advice, legal opinions, authoritative legal interpretation, or legally authoritative consolidation of Acts. Users must verify legal material using official sources and qualified legal professionals where required.

## Stack

- Backend: FastAPI, SQLAlchemy 2, Pydantic v2, JWT, bcrypt, PyMuPDF adapter.
- Frontend: Next.js App Router, React, TypeScript.
- Local database default: SQLite.
- Docker database: PostgreSQL 16.

## Demo Accounts

- Admin: `admin@example.com` / `AdminPass123!`
- Lawyer: `lawyer@example.com` / `LawyerPass123!`
- General User: `user@example.com` / `UserPass123!`

## Local Setup

```bash
cd legal-acts-retrieval-system

python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python -m uvicorn app.main:app --reload --app-dir backend

cd frontend
npm install
npm run dev
```

Backend health: `http://localhost:8000/health`

Frontend: `http://localhost:3000`

PDF processing uses Docling by default for richer document conversion, with PyMuPDF as the
automatic fallback when Docling is unavailable or cannot parse a PDF. Keep
`DOC_PARSER_PRIMARY=docling`, `DOCLING_ENABLED=true`, `DOCLING_TIMEOUT_SECONDS=60`, and
`OCR_ENABLED=false` for the current baseline. If Docling exceeds the timeout, processing falls
back to PyMuPDF and records a warning. Image-only or scanned PDFs are reported as
OCR-required/unsupported until OCR is intentionally enabled later.

Act metadata extraction is rule-based and explainable. Admin users should review and correct
extracted titles, numbers, years, dates, categories, and source fields before treating them as
reliable project data.

Section segmentation is also rule-based. Admin users should review extracted section records,
especially schedules, marginal notes, and continuation text from scanned or complex PDFs.

Statutory reference extraction is regex/rule-based. Admin users should review detected
relationships, unresolved targets, confidence scores, and warnings before treating references as
reliable project data.

Reference normalization and mapping are deterministic/rule-based. Unresolved Act, section,
schedule, and principal-enactment mappings must be reviewed by an Admin before demonstration or
evaluation use.

Extracted metadata, section records, references, and mapped relationships should be treated as
review-required data until an Admin verifies or corrects them in the Admin review screens.

Search is keyword, metadata, section-level, and relationship-based. General Users receive verified
sections and verified references only, and search results remain legal information retrieval
support, not legal advice or authoritative interpretation.

Relationship views are generated from extracted and mapped references. Unresolved relationships
require Admin review, and relationship tables/graphs are not legal advice or authoritative legal
interpretation.

The Lawyer workspace is for organizing saved Acts, sections, references, notes, and exportable
research lists only. Workspace exports include the legal disclaimer and are not legal advice,
legal opinions, or authoritative interpretation.

The General User UI is simplified for non-lawyer users and shows verified information only,
including reviewed mapped relationships. It does not provide legal advice, legal opinions,
recommendations, or authoritative interpretation.

## Docker Setup

```bash
cd legal-acts-retrieval-system
docker compose up --build
```

## MVP Workflow

1. Log in as Admin.
2. Upload an English-language Sri Lankan Legal Act PDF.
3. Process the document.
4. Review extracted metadata, sections, and references.
5. Verify or reject references.
6. Log in as Lawyer to run advanced search, inspect relationships, save items, and export summaries.
7. Log in as General User to search simplified verified content only.
8. Use Admin evaluation tools to enter gold references and calculate precision, recall, and F1.

## Final Demo Setup

1. Start the project locally or with Docker Compose.
2. Use the demo accounts above only; do not use real personal credentials.
3. Prepare 8-12 public/sample English-language Sri Lankan Legal Act PDFs.
4. Include amendment Acts, principal Acts, one schedule-heavy Act, one longer Act, and Acts with cross-references.
5. Manually verify 30-50 references as gold data before presenting evaluation results.
6. Follow `DEMO_SCRIPT.md` for Admin, Lawyer, and General User flows.

## Evaluation Method

Evaluation is deterministic and rule-based. Admin users add manually verified gold references, run the evaluation, and report precision, recall, F1-score, mismatch examples, section segmentation accuracy where section identifiers are available, mapping counts, verification counts, and processing warnings. See `EVALUATION_GUIDE.md` for the gold dataset format and metric definitions.

## Project Limits

- English Legal Act PDFs only.
- No chatbot and no personalized legal advice generation.
- Extracted references are not authoritative until verified by an Admin.
- Semantic embeddings are optional; keyword and metadata search are the MVP baseline.
- PDF extraction quality depends on source PDF quality.
- Rule-based extraction and mapping can miss complex drafting patterns.
- Unresolved references require Admin review.
- Evaluation results must be based on manually verified gold data; do not invent accuracy numbers.
- The system remains an academic legal information retrieval support prototype and is not legal advice.
