# Demo Script

This script demonstrates the academic MVP as a legal information retrieval prototype only. It does not provide legal advice, legal opinions, recommendations, or authoritative interpretation.

## Preparation

1. Start the system with `docker compose up --build` or the local backend/frontend commands in `README.md`.
2. Prepare 8-12 public English-language Sri Lankan Legal Act PDFs.
3. Include amendment Acts, their principal Acts where possible, one schedule-heavy Act, and one longer Act.
4. Log in with the demo accounts listed in `README.md`.

## Admin Flow

1. Sign in as Admin.
2. Open `Admin Acts` and upload a sample PDF.
3. Process the uploaded Act.
4. Review extraction status, parser used, page count, warnings, and errors.
5. Review and correct Act metadata.
6. Review extracted sections and verify or reject representative sections.
7. Review extracted references, mapping status, and confidence.
8. Correct or manually link mappings where appropriate.
9. Add 30-50 manually verified gold references across the demo dataset.
10. Open `Evaluation` and run the evaluation.
11. Show precision, recall, F1-score, mismatch rows, processing counts, and latest warnings.

## Lawyer Flow

1. Sign in as Lawyer.
2. Use Lawyer Search with relationship and verification filters.
3. Open an Act or section result.
4. Open the relationship explorer for an Act or section.
5. Save an Act, section, or reference to the Lawyer workspace.
6. Add a private note.
7. Export saved items as CSV or Markdown.
8. Point out the export disclaimer.

## General User Flow

1. Sign in as General User.
2. Open Browse Acts.
3. Search verified legal information.
4. Open an Act detail page and view verified sections.
5. Open a section detail page and view verified mapped references.
6. Confirm no Admin upload, verification, correction, Lawyer workspace, or export controls are visible.

## Demo Checklist

- PDF upload works.
- Processing creates metadata, sections, references, and mappings.
- Admin review screens are usable.
- Evaluation metrics are visible.
- Lawyer search, relationships, workspace, and exports work.
- General User sees simplified verified information only.
- Legal disclaimer is visible in UI and exports.
