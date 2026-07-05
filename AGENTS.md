# Repository Guidelines

## Project Structure & Module Organization

This repository is a monorepo for an academic legal information retrieval MVP.

- `backend/`: FastAPI application, SQLAlchemy models, services, schemas, API routes, and tests.
- `backend/app/api/routes/`: versioned `/api/v1` route modules.
- `backend/app/services/`: PDF parsing, text cleaning, metadata extraction, section segmentation, reference extraction/mapping, search, export, and evaluation logic.
- `backend/app/tests/`: pytest unit and API tests.
- `frontend/`: Next.js App Router frontend.
- `frontend/app/`: pages for public search, auth, Admin, Lawyer, and detail views.
- `frontend/components/`: shared UI components such as role guards, disclaimers, tables, and viewers.
- `frontend/lib/`: API client, auth helpers, and shared TypeScript types.

## Build, Test, and Development Commands

Run commands from the relevant subdirectory.

Backend:

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check app
```

Frontend:

```powershell
cd frontend
npm run dev
npm run typecheck
npm test
npm run build
```

Use `docker compose up --build` from the repository root to run the full stack with PostgreSQL.

## Coding Style & Naming Conventions

Python uses Ruff with a 100-character line length. Keep FastAPI route modules thin and place reusable business logic in `backend/app/services/`. Use `snake_case` for Python functions/files and `PascalCase` for SQLAlchemy model classes.

TypeScript uses strict mode. React components live in `frontend/components/` and use `kebab-case` filenames with exported `PascalCase` components. Keep role and legal-disclaimer logic visible in user-facing legal pages.

## Testing Guidelines

Backend tests use pytest and should be named `test_*.py`. Add focused tests for auth, RBAC, upload validation, extraction, search, and evaluation changes.

Frontend tests use Vitest in `frontend/tests/`. Cover role visibility, auth helper behavior, and safety checks for “no legal advice” restrictions.

## Commit & Pull Request Guidelines

No commit history exists yet. Use concise imperative commit messages, for example:

- `Add admin reference verification flow`
- `Fix frontend auth session validation`

Pull requests should include a short summary, testing results, linked issue or task, screenshots for UI changes, and notes about any legal-safety or role-permission impact.

## Security & Configuration Tips

Never commit `.env`, uploaded PDFs, SQLite databases, `node_modules/`, `.next/`, or virtual environments. Keep `SECRET_KEY`, database URLs, and CORS origins environment-specific. General Users must only see verified references by default, and the system must not generate legal advice.

Demo accounts are intentionally dummy credentials:

- `admin@example.com` / `AdminPass123!`
- `lawyer@example.com` / `LawyerPass123!`
- `user@example.com` / `UserPass123!`
