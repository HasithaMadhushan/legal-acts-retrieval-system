# PRD.md - Automated Section-Level Reference Mapping and Semantic Retrieval System for Sri Lankan Legal Acts

**Version:** 1.0  
**Prepared for:** Codex implementation from scratch  
**Project owner:** Hasitha Madhushan  
**Academic context:** BSc (Hons) Software Engineering Top Up - Development Project  
**Primary source documents:** Final Project Proposal and Ethics Approval Form  
**Core product type:** Role-based legal information retrieval prototype  
**Important legal status:** Research prototype only. The system must not provide legal advice, legal opinions, authoritative legal interpretation, or legally authoritative consolidation of legislation.

---

## 1. Product Summary

Build a full-stack web application that converts selected English-language Sri Lankan Legal Act PDF documents into structured, searchable, section-level legal information. The system must allow an Admin to upload Legal Act PDFs, process them into metadata and sections, detect statutory references and amendment-related relationships, verify/correct extracted results, and make verified data available for Lawyer and General User search.

The system must move beyond simple document-level PDF search. It must support section-level retrieval, statutory reference mapping, relationship discovery, and lightweight semantic/metadata-assisted search for English-language Sri Lankan Legal Acts.

### One-sentence product vision

A research-support web system that transforms static Sri Lankan Legal Act PDFs into structured sections, mapped statutory relationships, and searchable legal research outputs.

---

## 2. Problem Statement

Sri Lankan Legal Acts are commonly available as PDF documents or document-level records. Existing access methods help users download or search whole documents, but they do not sufficiently expose section-level structure, statutory references, amendments, repeals, insertions, substitutions, or cross-document legal relationships.

Legal users often need to answer questions such as:

- Which exact section is relevant?
- Has this section been amended, repealed, substituted, or inserted by another Act?
- Which Act or section does this provision refer to?
- Which later Act affects this earlier Act?
- Are related provisions discoverable without manually opening multiple PDFs?

The system must reduce manual PDF inspection by creating a structured database of Acts, sections, references, and relationships.

---

## 3. Goals and Objectives

### 3.1 Primary goals

1. Upload and manage selected English-language Sri Lankan Legal Act PDFs.
2. Extract Act-level metadata such as title, Act number, year, date, category, source file name, and processing status.
3. Segment Acts into searchable sections, subsections, paragraphs, headings, definitions, and schedules where possible.
4. Detect statutory references using rule-based patterns, regular expressions, and lightweight NLP.
5. Map references and relationships such as:
   - Act-to-Act reference
   - Section-to-section reference
   - Amendment
   - Repeal
   - Insertion
   - Substitution
6. Provide Admin verification/correction before extracted relationships become trusted.
7. Provide role-based search and relationship exploration for Admins, Lawyers, and General Users.
8. Evaluate extraction and retrieval quality using manually verified sample references and test queries.

### 3.2 Success outcomes

The final system must demonstrate:

- Uploaded and processed Legal Act records.
- Extracted Act metadata.
- Segmented section-level legal text.
- Detected statutory references.
- Mapped Act-to-Act and section-to-section relationships.
- Search results using keyword, metadata, and lightweight semantic relevance.
- Reference visualization views.
- Evaluation metrics for section segmentation and reference extraction.

---

## 4. Non-goals and Scope Exclusions

The system must not attempt to solve all legal information problems. Keep the MVP academically realistic.

### 4.1 Out of scope for MVP

- Sinhala Legal Acts.
- Tamil Legal Acts.
- Court judgments.
- Bills.
- Gazettes.
- Regulations.
- Law reports.
- Legal commentaries.
- Legal advice generation.
- Legal opinion generation.
- Authoritative legal interpretation.
- Legally authoritative consolidation of Acts.
- Full point-in-time versioning of every Act.
- Advanced legal reasoning or legal argument generation.
- Large-scale legal knowledge graph covering all Sri Lankan law.
- Public production deployment with real users unless explicitly approved.

### 4.2 Ethical and legal boundaries

Every page that displays legal information must show a clear disclaimer:

> This system is an academic research prototype for legal information retrieval support only. It does not provide legal advice, legal opinions, authoritative legal interpretation, or legally authoritative consolidation of Acts. Users must verify legal material using official sources and qualified legal professionals where required.

Do not build a chatbot that answers legal questions as advice. Search explanations may summarize why a result matched, but must not tell users what the law means for their personal situation.

---

## 5. Target Users and Roles

### 5.1 Admin

Admins maintain the legal document database and verify extraction results.

Admin capabilities:

- Log in securely.
- Manage users and roles.
- Upload English-language Sri Lankan Legal Act PDFs.
- View uploaded document status.
- Trigger processing/reprocessing.
- Edit extracted metadata.
- Review extracted sections.
- Review detected statutory references.
- Verify, reject, or correct references.
- Manually link references to target Acts/sections.
- View processing reports and evaluation metrics.

### 5.2 Lawyer

Lawyers use advanced statutory research features.

Lawyer capabilities:

- Log in securely.
- Search Acts and sections.
- Filter by Act title, Act number, year, category, relationship type, and verification status.
- View section-level search results.
- View relationship maps for Acts and sections.
- Identify amendments, repeals, insertions, substitutions, and references.
- Save selected Acts or sections to a workspace.
- Export selected reference summaries as CSV or Markdown.

### 5.3 General User

General Users use simplified search and viewing.

General User capabilities:

- Register or use a seeded demo account.
- Search Acts using keywords or plain-language queries.
- View basic Act details.
- View simplified section information.
- View limited related references that are verified.
- See clear disclaimers that the system is not legal advice.

---

## 6. Recommended Technology Stack

Use the stack stated in the project proposal, with pragmatic fallbacks so Codex can build a working prototype.

### 6.1 Backend

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic migrations
- PostgreSQL 15/16
- pgvector extension where available
- JWT authentication
- Passlib or bcrypt password hashing
- PyMuPDF for reliable baseline PDF text extraction
- Docling adapter interface as primary/optional parser if installation succeeds
- Tesseract OCR adapter as optional future fallback; do not block MVP on OCR
- Regex-based legal reference extraction
- Optional spaCy rule matcher if available; MVP must work without spaCy
- Optional sentence-transformers for embeddings; MVP must work with PostgreSQL full-text search if embeddings are unavailable

### 6.2 Frontend

- Next.js 14+ with App Router
- React
- TypeScript
- Tailwind CSS
- shadcn/ui or equivalent clean component system
- React Hook Form + Zod validation
- TanStack Query or equivalent for API data fetching
- Cytoscape.js, React Flow, or a simple custom SVG/table relationship viewer

### 6.3 Infrastructure and tooling

- Docker Compose for local development
- PostgreSQL container
- Backend container
- Frontend container or local Node dev server
- `.env.example` files for backend and frontend
- Pytest for backend tests
- Vitest/Playwright or minimal frontend tests
- Ruff or Black for Python formatting
- ESLint/Prettier for frontend formatting
- GitHub-ready repository structure

---

## 7. Repository Structure

Codex must create a clean monorepo:

```text
legal-acts-retrieval-system/
  README.md
  PRD.md
  docker-compose.yml
  .gitignore
  .env.example

  backend/
    app/
      main.py
      core/
        config.py
        security.py
        roles.py
      db/
        session.py
        base.py
      models/
        user.py
        legal_act.py
        act_section.py
        legal_reference.py
        processing_job.py
        saved_item.py
        evaluation.py
      schemas/
        auth.py
        user.py
        legal_act.py
        section.py
        reference.py
        search.py
        evaluation.py
      api/
        deps.py
        routes/
          auth.py
          users.py
          acts.py
          sections.py
          references.py
          search.py
          relationships.py
          evaluation.py
          exports.py
      services/
        pdf_parser/
          base.py
          pymupdf_parser.py
          docling_parser.py
          ocr_parser.py
        text_cleaner.py
        metadata_extractor.py
        section_segmenter.py
        reference_extractor.py
        reference_normalizer.py
        reference_mapper.py
        search_service.py
        embedding_service.py
        evaluation_service.py
        export_service.py
      tests/
        test_auth.py
        test_section_segmenter.py
        test_reference_extractor.py
        test_reference_mapper.py
        test_search.py
    alembic/
    pyproject.toml
    requirements.txt

  frontend/
    app/
      layout.tsx
      page.tsx
      login/page.tsx
      register/page.tsx
      dashboard/page.tsx
      admin/
        acts/page.tsx
        acts/upload/page.tsx
        acts/[id]/page.tsx
        acts/[id]/sections/page.tsx
        acts/[id]/references/page.tsx
        users/page.tsx
        evaluation/page.tsx
      lawyer/
        search/page.tsx
        workspace/page.tsx
        relationships/page.tsx
      search/page.tsx
      acts/[id]/page.tsx
      sections/[id]/page.tsx
    components/
      app-shell.tsx
      role-guard.tsx
      legal-disclaimer.tsx
      upload-dropzone.tsx
      status-badge.tsx
      relationship-graph.tsx
      search-results.tsx
      reference-table.tsx
      section-viewer.tsx
    lib/
      api.ts
      auth.ts
      types.ts
    package.json
    tsconfig.json
```

---

## 8. Core Domain Model

Use UUID primary keys unless there is a strong reason not to.

### 8.1 User

Fields:

- id
- full_name
- email
- hashed_password
- role: `ADMIN | LAWYER | GENERAL_USER`
- is_active
- created_at
- updated_at

Rules:

- Email must be unique.
- Seed one Admin account during development.
- Only Admin can change another user's role.

### 8.2 LegalAct

Fields:

- id
- title
- normalized_title
- act_number
- year
- certification_date nullable
- publication_date nullable
- category nullable
- source_name nullable
- source_url nullable
- source_file_name
- stored_file_path
- file_sha256
- page_count
- raw_text nullable
- processing_status: `UPLOADED | PROCESSING | PROCESSED | FAILED | VERIFIED`
- parser_used: `DOCLING | PYMUPDF | OCR | MANUAL | UNKNOWN`
- processing_error nullable
- uploaded_by_user_id
- uploaded_at
- updated_at

Indexes:

- title
- normalized_title
- act_number
- year
- processing_status
- full-text index on title + raw_text if practical

### 8.3 ActSection

Fields:

- id
- act_id
- section_number
- section_path nullable, e.g. `5`, `5(1)`, `5(1)(a)`, `Schedule I`
- heading nullable
- section_type: `SECTION | SUBSECTION | PARAGRAPH | SCHEDULE | PART | PREAMBLE | OTHER`
- text
- normalized_text
- page_start nullable
- page_end nullable
- sort_order
- parent_section_id nullable
- verification_status: `PENDING | VERIFIED | REJECTED | NEEDS_REVIEW`
- created_at
- updated_at

Indexes:

- act_id
- section_number
- section_path
- verification_status
- full-text index on heading + text
- vector index on embedding if pgvector is enabled

### 8.4 LegalReference

Fields:

- id
- source_act_id
- source_section_id nullable
- raw_reference_text
- context_snippet
- relationship_type: `REFERS_TO | AMENDS | REPEALS | INSERTS | SUBSTITUTES | COMMENCES | DEFINES | CROSS_REFERENCE | UNKNOWN`
- target_act_title_raw nullable
- target_act_number nullable
- target_act_year nullable
- target_section_number nullable
- target_section_path nullable
- target_act_id nullable
- target_section_id nullable
- confidence_score decimal 0-1
- extraction_method: `REGEX | NLP_RULE | MANUAL`
- verification_status: `PENDING | VERIFIED | REJECTED | NEEDS_REVIEW`
- verified_by_user_id nullable
- verified_at nullable
- notes nullable
- created_at
- updated_at

Rules:

- Detected references start as `PENDING`.
- General Users should see only verified references by default.
- Lawyers may see pending references if explicitly enabled in filters, clearly marked.
- Admins can edit all fields and verify/reject.

### 8.5 ProcessingJob

Fields:

- id
- act_id
- status: `QUEUED | RUNNING | COMPLETED | FAILED`
- current_step
- progress_percent
- started_at nullable
- completed_at nullable
- error_message nullable
- summary_json
- created_by_user_id
- created_at
- updated_at

### 8.6 SavedItem

Fields:

- id
- user_id
- item_type: `ACT | SECTION | REFERENCE`
- act_id nullable
- section_id nullable
- reference_id nullable
- note nullable
- created_at

### 8.7 EvaluationGoldReference

Fields:

- id
- act_id
- source_section_id nullable
- expected_raw_text
- expected_relationship_type
- expected_target_act_title nullable
- expected_target_section_number nullable
- notes nullable
- created_at

### 8.8 EvaluationRun

Fields:

- id
- run_name
- act_id nullable
- precision
- recall
- f1_score
- section_segmentation_accuracy nullable
- total_gold_references
- true_positives
- false_positives
- false_negatives
- run_summary_json
- created_at

---

## 9. Processing Pipeline Requirements

The document processing pipeline must be modular and testable. Each step must be callable independently in backend tests.

### 9.1 Step 1 - Upload validation

Admin uploads PDF.

Validation:

- Only `.pdf` files allowed.
- File size configurable; default maximum 50MB.
- Store file with safe generated name, not original name only.
- Calculate SHA-256 hash.
- Prevent duplicate upload by hash unless Admin confirms re-upload.
- Create LegalAct record with status `UPLOADED`.

### 9.2 Step 2 - Text extraction

Implement parser interface:

```python
class PdfParser(Protocol):
    def extract(self, file_path: str) -> ParsedPdf:
        ...
```

ParsedPdf should include:

- full_text
- page_count
- page_texts list
- parser_name
- warnings list

Parser order:

1. Try Docling parser if configured and installed.
2. Fallback to PyMuPDF parser.
3. Optional OCR parser only if enabled.

MVP must work with PyMuPDF even if Docling/OCR are unavailable.

### 9.3 Step 3 - Text cleaning

Normalize:

- Repeated whitespace.
- Broken line hyphenation.
- Page headers/footers where detectable.
- Common OCR artifacts where possible.
- Unicode oddities into normalized ASCII-friendly forms where safe.

Keep raw text separately from normalized text.

### 9.4 Step 4 - Metadata extraction

Extract, with confidence if possible:

- Act title.
- Act number.
- Year.
- Date of certification or publication where available.
- Category/subject if Admin provides or if detected.
- Source file name.

Typical patterns:

- `No. 12 of 2020`
- `Act, No. 12 of 2020`
- uppercase title blocks near the first page
- `Certified on ...`

If metadata is uncertain, save it and mark as needing Admin review.

### 9.5 Step 5 - Section segmentation

Segment legal text into sections and schedules.

Minimum patterns:

- Main sections: `1.`, `2.`, `3.` at beginning of line.
- Section heading following a number.
- Subsections: `(1)`, `(2)`, `(3)`.
- Paragraphs: `(a)`, `(b)`, `(c)`.
- Schedules: `SCHEDULE`, `FIRST SCHEDULE`, `SECOND SCHEDULE`.
- Parts: `PART I`, `PART II`.

MVP acceptance:

- Store at least main sections as separate records.
- Store subsections within the parent section text if fine-grained segmentation is unreliable.
- Do not lose text between sections.
- Preserve original section order.

### 9.6 Step 6 - Reference detection

Detect references using regex and legal-domain phrase rules.

Relationship phrase examples:

- `amended by`
- `is amended`
- `shall be amended`
- `is hereby repealed`
- `shall be repealed`
- `is substituted by`
- `the following section is substituted`
- `the following new section is inserted`
- `inserted immediately after section`
- `referred to in section`
- `subject to the provisions of`
- `in accordance with section`

Reference target examples:

- `section 5`
- `subsection (2)`
- `paragraph (a)`
- `Schedule I`
- `[Act Title] Act, No. 12 of 2020`
- `[Act Title] Act`
- `Chapter 123`

Each detection must create a LegalReference with:

- raw reference text
- context snippet
- relationship type
- target title/section/year if detected
- confidence score
- status `PENDING`

### 9.7 Step 7 - Reference normalization

Normalize common variations:

- Case-insensitive titles.
- Strip punctuation from title matching.
- Normalize `No.`, `Number`, `Act No.` formats.
- Normalize section references such as `section 5`, `s. 5`, `sec. 5` where possible.
- Normalize years to 4-digit years.

### 9.8 Step 8 - Reference mapping

Attempt to link detected references to existing LegalAct and ActSection records.

Mapping rules:

- Exact match by act_number + year has highest confidence.
- Exact normalized title match has high confidence.
- Fuzzy title match has medium confidence and should remain pending.
- Target section match only if target Act is known or source Act context makes it clear.
- If mapping is uncertain, leave target IDs null and mark `NEEDS_REVIEW`.

### 9.9 Step 9 - Search indexing

After processing:

- Update PostgreSQL full-text indexes.
- Generate embeddings if embedding service is configured.
- Store section vectors if pgvector is available.
- If embeddings are not available, app must still support keyword and metadata search.

### 9.10 Step 10 - Admin verification

Admin can:

- Edit metadata.
- Edit section heading/text if extraction is wrong.
- Verify/reject sections.
- Verify/reject references.
- Manually link a reference to target Act/section.
- Add notes.

Verified data becomes visible in default Lawyer and General User results.

---

## 10. Search and Retrieval Requirements

### 10.1 Search inputs

Users can search by:

- Act title.
- Act number.
- Year.
- Section number.
- Legal keyword.
- Plain-language query.
- Relationship type.
- Verification status, for Admin/Lawyer only.

### 10.2 Search behavior

Search must return mixed result types:

- Acts.
- Sections.
- References/relationships.

Result cards must show:

- Result type.
- Act title.
- Act number/year.
- Section number if applicable.
- Snippet with highlighted matched terms.
- Relationship badges where applicable.
- Verification badge.
- Link to detail page.

### 10.3 Ranking

MVP ranking can combine:

- Exact title/number/year matches.
- Full-text rank.
- Metadata filter match.
- Verified status boost.
- Semantic similarity score if enabled.

### 10.4 Semantic retrieval

Implement semantic retrieval as optional but architecturally supported.

Acceptable MVP approaches:

- PostgreSQL full-text search as required baseline.
- pgvector + sentence-transformers as optional enhancement.
- If embeddings fail, log warning and continue with keyword search.

Do not use paid external AI APIs unless explicitly configured by the developer.

---

## 11. Relationship Visualization Requirements

The system must provide an understandable way to explore relationships.

### 11.1 MVP visualization modes

1. Table view:
   - Source Act.
   - Source Section.
   - Relationship Type.
   - Target Act.
   - Target Section.
   - Confidence.
   - Verification Status.

2. Graph view:
   - Nodes represent Acts or sections.
   - Edges represent reference relationships.
   - Edge labels show `AMENDS`, `REPEALS`, `INSERTS`, `SUBSTITUTES`, or `REFERS_TO`.
   - Clicking a node opens Act/section details.

### 11.2 Role visibility

- Admin: all relationships, including rejected and pending.
- Lawyer: verified by default, pending optional with warning.
- General User: verified only.

---

## 12. Functional Requirements

### FR-001 Authentication

Users must be able to log in and log out securely using email and password.

Acceptance criteria:

- Passwords are hashed.
- JWT or secure session is used.
- Invalid credentials return safe error messages.
- Protected routes cannot be accessed without authentication.

### FR-002 Role-based access control

System must enforce Admin, Lawyer, and General User permissions.

Acceptance criteria:

- Admin-only pages/API endpoints reject Lawyer and General User access.
- Lawyer-only features reject General User access.
- Frontend hides unauthorized actions.
- Backend enforces authorization regardless of frontend.

### FR-003 Admin PDF upload

Admin must upload English-language Sri Lankan Legal Act PDFs.

Acceptance criteria:

- PDF validation works.
- LegalAct record is created.
- Upload status is visible.
- Duplicate hash is detected.

### FR-004 Document processing trigger

Admin must trigger processing for uploaded PDFs.

Acceptance criteria:

- ProcessingJob is created.
- Status changes from queued to running to completed/failed.
- Errors are stored and displayed.
- Extracted metadata, sections, and references are saved.

### FR-005 Metadata extraction and editing

System must extract and allow editing of metadata.

Acceptance criteria:

- Title, Act number, year, source file name, upload date, and processing status are visible.
- Admin can edit title, category, dates, and source details.
- Edits are audited with updated_at.

### FR-006 Section segmentation

System must split processed Acts into section-level records.

Acceptance criteria:

- Sections are displayed in correct order.
- Each section links to parent Act.
- Section detail page displays full text.
- Admin can mark a section verified or needing review.

### FR-007 Reference extraction

System must detect statutory references and relationship phrases.

Acceptance criteria:

- Detected references are stored with context snippets.
- Relationship types are classified where possible.
- Confidence score is assigned.
- References are pending until verified.

### FR-008 Reference verification

Admin must verify, reject, or correct detected references.

Acceptance criteria:

- Admin can edit raw target information.
- Admin can manually select target Act/section.
- Verified references become visible to General Users.
- Rejected references are hidden from non-admin users.

### FR-009 Search

Users must search Acts and sections.

Acceptance criteria:

- Search endpoint supports query string and filters.
- Results include Acts and sections.
- Results show snippets and metadata.
- Empty searches produce helpful guidance.

### FR-010 Relationship exploration

Users must explore statutory relationships.

Acceptance criteria:

- Act detail page shows outgoing and incoming relationships.
- Section detail page shows related sections/references.
- Relationship table and graph view are available.

### FR-011 Lawyer workspace

Lawyer users must save selected Acts, sections, or references.

Acceptance criteria:

- Lawyer can save/unsave items.
- Saved workspace lists selected items.
- Lawyer can add personal notes.
- Lawyer can export saved references.

### FR-012 General User simplified interface

General Users must have simplified legal search.

Acceptance criteria:

- General user search does not show admin controls.
- Only verified references are visible.
- Legal disclaimer is visible.
- Results are understandable and not presented as legal advice.

### FR-013 Export

Lawyer and Admin users must export reference summaries.

Acceptance criteria:

- CSV export works.
- Markdown export works.
- Export includes disclaimer.
- Export includes selected Act/section/reference metadata.

### FR-014 Evaluation dashboard

Admin must view technical evaluation metrics.

Acceptance criteria:

- Gold reference sample can be entered or imported.
- Evaluation run calculates precision, recall, and F1-score.
- Section segmentation accuracy can be manually recorded or calculated from sample data.
- Metrics are displayed in the admin dashboard.

### FR-015 Audit and safety messaging

System must clearly state limitations.

Acceptance criteria:

- Legal disclaimer appears on login, search, Act detail, section detail, and export outputs.
- System does not generate legal advice.
- System labels unverified/pending extraction results clearly.

---

## 13. Non-functional Requirements

### 13.1 Security

- Passwords must be hashed.
- Role checks must be enforced server-side.
- Uploaded files must be validated.
- Original file names must be sanitized.
- CORS must be configured safely.
- Environment secrets must not be committed.
- API must not expose local file system paths to normal users.

### 13.2 Privacy and ethics

- Use test/dummy accounts where possible.
- Do not collect sensitive personal data in the system.
- Do not implement participant feedback collection as a public feature unless explicitly requested.
- If feedback forms are implemented later, they must support anonymized/coded responses.
- The final application must not publish participant details.

### 13.3 Reliability

- Processing failures must not crash the app.
- Failed jobs must show clear errors to Admin.
- Reprocessing must be possible.
- Database transactions must protect partial processing where practical.

### 13.4 Performance

For MVP sample dataset:

- Search results should return in under 2 seconds for up to 100 uploaded Acts.
- Act detail page should load in under 2 seconds for typical processed Acts.
- PDF processing can be asynchronous or synchronous, but UI must display progress/status.
- Processing large/scanned PDFs may take longer and should show status clearly.

### 13.5 Usability

- Admin dashboard must clearly show upload and processing state.
- Search must be simple enough for General Users.
- Lawyer interface may include advanced filters.
- Relationship badges must be visually distinct.
- Verification status must be obvious.

### 13.6 Accessibility

- Use semantic HTML.
- All forms must have labels.
- Buttons must be keyboard accessible.
- Color must not be the only way status is communicated.

### 13.7 Maintainability

- Keep parsing, segmentation, reference extraction, mapping, and search services separate.
- Write tests for text-processing functions.
- Keep regex patterns centralized and documented.
- Provide README setup instructions.

---

## 14. UI Page Requirements

### 14.1 Public/General pages

#### `/`

Landing page with:

- Product name.
- Short description.
- Search entry point.
- Login/register links.
- Legal disclaimer.

#### `/login`

- Email/password login.
- Link to register if enabled.

#### `/search`

- Simple query input.
- Filters: year, Act number, relationship type.
- Results list.
- Disclaimer.

#### `/acts/[id]`

- Act metadata.
- Section list.
- Verified relationship summary.
- Link to source PDF if allowed.
- Disclaimer.

#### `/sections/[id]`

- Section text.
- Parent Act metadata.
- Verified references.
- Related sections.
- Disclaimer.

### 14.2 Admin pages

#### `/admin/acts`

- List uploaded Acts.
- Status filters.
- Upload button.
- Search/filter.

#### `/admin/acts/upload`

- Upload dropzone.
- File validation.
- Optional category/source URL fields.

#### `/admin/acts/[id]`

- Metadata editor.
- Processing status.
- Trigger process/reprocess.
- Processing logs/errors.

#### `/admin/acts/[id]/sections`

- Section list.
- Edit section heading/text.
- Verification controls.

#### `/admin/acts/[id]/references`

- Reference table.
- Filters by relationship/status.
- Edit/correct reference.
- Link target Act/section.
- Verify/reject buttons.

#### `/admin/users`

- List users.
- Create/edit/deactivate user.
- Change role.

#### `/admin/evaluation`

- Import/manage gold references.
- Run evaluation.
- Show precision, recall, F1, segmentation accuracy.
- Show false positives/false negatives where possible.

### 14.3 Lawyer pages

#### `/lawyer/search`

- Advanced search.
- Filters by Act, year, relationship, status.
- Section-level result display.

#### `/lawyer/relationships`

- Relationship graph/table explorer.
- Filter by relationship type.
- Click-through to Act/section.

#### `/lawyer/workspace`

- Saved Acts/sections/references.
- Notes.
- Export buttons.

---

## 15. API Requirements

Use `/api/v1` prefix.

### Auth

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout` if session-based
- `GET /api/v1/auth/me`

### Users

- `GET /api/v1/users` Admin only
- `POST /api/v1/users` Admin only
- `PATCH /api/v1/users/{id}` Admin only
- `DELETE /api/v1/users/{id}` Admin only or deactivate

### Acts

- `GET /api/v1/acts`
- `POST /api/v1/acts/upload` Admin only
- `GET /api/v1/acts/{id}`
- `PATCH /api/v1/acts/{id}` Admin only
- `DELETE /api/v1/acts/{id}` Admin only
- `POST /api/v1/acts/{id}/process` Admin only
- `GET /api/v1/acts/{id}/processing-jobs` Admin only

### Sections

- `GET /api/v1/acts/{id}/sections`
- `GET /api/v1/sections/{id}`
- `PATCH /api/v1/sections/{id}` Admin only
- `POST /api/v1/sections/{id}/verify` Admin only
- `POST /api/v1/sections/{id}/reject` Admin only

### References

- `GET /api/v1/acts/{id}/references`
- `GET /api/v1/sections/{id}/references`
- `GET /api/v1/references/{id}`
- `PATCH /api/v1/references/{id}` Admin only
- `POST /api/v1/references/{id}/verify` Admin only
- `POST /api/v1/references/{id}/reject` Admin only
- `POST /api/v1/references/{id}/link-target` Admin only

### Search

- `GET /api/v1/search?q=&year=&act_number=&relationship_type=&role_view=`
- `GET /api/v1/search/suggest?q=` optional

### Relationships

- `GET /api/v1/relationships/act/{id}`
- `GET /api/v1/relationships/section/{id}`
- `GET /api/v1/relationships/graph?act_id=&section_id=&depth=1`

### Saved workspace

- `GET /api/v1/saved-items` Lawyer/Admin
- `POST /api/v1/saved-items` Lawyer/Admin
- `PATCH /api/v1/saved-items/{id}` Lawyer/Admin owner only
- `DELETE /api/v1/saved-items/{id}` Lawyer/Admin owner only

### Export

- `GET /api/v1/exports/saved-items.csv` Lawyer/Admin
- `GET /api/v1/exports/saved-items.md` Lawyer/Admin
- `GET /api/v1/exports/act/{id}/references.csv` Lawyer/Admin

### Evaluation

- `GET /api/v1/evaluation/gold-references` Admin only
- `POST /api/v1/evaluation/gold-references` Admin only
- `POST /api/v1/evaluation/run` Admin only
- `GET /api/v1/evaluation/runs` Admin only
- `GET /api/v1/evaluation/runs/{id}` Admin only

---

## 16. Reference Extraction Pattern Specification

Create a centralized `reference_patterns.py` or equivalent module.

### 16.1 Relationship classification

Use phrase detection near a reference to classify relationship.

Examples:

```text
AMENDS:
- amended by
- is amended
- shall be amended
- amendment of section
- in section X of the principal enactment ...

REPEALS:
- is hereby repealed
- shall be repealed
- repeal of
- the following section is repealed

INSERTS:
- the following new section is inserted
- inserted immediately after section
- there shall be inserted

SUBSTITUTES:
- is substituted by
- the following section is substituted
- substitute therefor the following

REFERS_TO/CROSS_REFERENCE:
- referred to in section
- subject to section
- in accordance with section
- under section
- for the purposes of section
```

### 16.2 Target extraction

Extract target values when possible:

```text
Act title:
- <Title> Act, No. <number> of <year>
- <Title> Act
- Chapter <number>

Section:
- section <number>
- sections <number> and <number>
- subsection (<number>)
- paragraph (<letter>)
- Schedule / First Schedule / Second Schedule
```

### 16.3 Confidence scoring

Suggested scoring:

- 0.95: exact Act number + year + relationship phrase found.
- 0.85: exact title + section number + relationship phrase found.
- 0.70: title or section reference found but target Act uncertain.
- 0.50: relationship phrase found but target incomplete.
- 0.30: weak cross-reference only.

All non-manual detections must start as `PENDING` or `NEEDS_REVIEW`.

---

## 17. Evaluation Requirements

The system must support academic evaluation.

### 17.1 Metrics

Calculate:

- Precision = true positives / (true positives + false positives)
- Recall = true positives / (true positives + false negatives)
- F1-score = 2 * precision * recall / (precision + recall)
- Section segmentation accuracy = correctly segmented sections / manually identified sections

### 17.2 Gold sample

Admin can create/import a manually verified reference sample.

Minimum CSV columns:

```csv
act_title,source_section,raw_reference_text,relationship_type,target_act_title,target_section,notes
```

### 17.3 Retrieval usefulness

Provide an evaluation page where Admin can record selected legal search queries and mark whether returned Acts/sections were relevant. Keep this simple for MVP.

---

## 18. Seed Data and Demo Requirements

Create seed script:

- Admin user:
  - email: `admin@example.com`
  - password: `Admin123!`
- Lawyer user:
  - email: `lawyer@example.com`
  - password: `Lawyer123!`
- General user:
  - email: `user@example.com`
  - password: `User123!`

Do not include real participant data.

Provide optional sample text fixtures for tests. Do not require real Legal Act PDFs in the repository.

---

## 19. Implementation Plan for Codex

Build incrementally. Do not attempt all features in one pass.

### Phase 0 - Project scaffold

- Create monorepo structure.
- Create Docker Compose.
- Configure FastAPI backend.
- Configure Next.js frontend.
- Add README setup instructions.
- Add `.env.example`.

Acceptance:

- `docker compose up --build` starts backend, frontend, and database.
- Backend health endpoint works.
- Frontend landing page works.

### Phase 1 - Database, auth, and RBAC

- Add SQLAlchemy models.
- Add Alembic migrations.
- Add auth endpoints.
- Add seeded demo users.
- Add role guard middleware/dependencies.
- Add frontend login and role-based redirects.

Acceptance:

- Admin, Lawyer, and General User can log in.
- Protected routes work.
- Backend tests cover role restrictions.

### Phase 2 - Admin upload and document management

- Add PDF upload endpoint.
- Store files safely.
- Create LegalAct records.
- Build Admin Acts list/upload/detail pages.

Acceptance:

- Admin can upload PDF.
- Upload appears in Admin list.
- Non-admin upload attempt is blocked.

### Phase 3 - PDF text extraction, metadata, and sections

- Implement PyMuPDF parser.
- Add Docling adapter interface but make it optional.
- Implement text cleaner.
- Implement metadata extractor.
- Implement section segmenter.
- Add processing endpoint/job status.
- Show sections in Admin UI.

Acceptance:

- Uploaded PDF can be processed.
- Extracted sections are stored and visible.
- Tests cover sample segmentation cases.

### Phase 4 - Reference extraction and mapping

- Implement reference extractor.
- Implement relationship classification.
- Implement normalization.
- Implement mapper.
- Add Admin reference verification UI.

Acceptance:

- Sample text produces expected references.
- Admin can verify/reject references.
- Tests cover amendment/repeal/insertion/substitution examples.

### Phase 5 - Search and relationship exploration

- Implement keyword and metadata search.
- Add optional semantic service interface.
- Add Act/section detail pages.
- Add relationship table and simple graph.

Acceptance:

- General User can search verified content.
- Lawyer can use advanced filters.
- Relationship graph/table works.

### Phase 6 - Lawyer workspace and exports

- Implement saved items.
- Implement notes.
- Implement CSV and Markdown exports.

Acceptance:

- Lawyer can save a section/reference.
- Export includes selected items and disclaimer.

### Phase 7 - Evaluation dashboard

- Implement gold reference sample management.
- Implement evaluation run.
- Calculate precision, recall, F1.
- Display metrics.

Acceptance:

- Admin can add gold sample references.
- Evaluation run outputs metrics.

### Phase 8 - Polish, tests, and documentation

- Improve UI consistency.
- Add loading and empty states.
- Add error handling.
- Add README screenshots placeholders.
- Ensure disclaimers across relevant pages.
- Run all tests and linters.

Acceptance:

- Clean local setup.
- Core tests pass.
- App is demo-ready.

---

## 20. Testing Requirements

### 20.1 Backend unit tests

Must cover:

- Password hashing and login.
- Role authorization.
- PDF upload validation.
- Metadata extraction from sample text.
- Section segmentation from sample legal text.
- Reference extraction for:
  - amendment
  - repeal
  - insertion
  - substitution
  - simple cross-reference
- Reference normalization.
- Search endpoint basic behavior.
- Evaluation metric calculations.

### 20.2 Frontend tests or smoke checks

Must cover at least:

- Login page renders.
- Admin navigation is hidden from non-admin.
- Search page renders.
- Upload page requires Admin role.

### 20.3 Manual demo test checklist

1. Start app locally.
2. Login as Admin.
3. Upload a sample PDF.
4. Process document.
5. View extracted metadata.
6. View sections.
7. View detected references.
8. Verify one reference.
9. Login as Lawyer.
10. Search for the verified reference.
11. Save section/reference.
12. Export saved item summary.
13. Login as General User.
14. Confirm only verified content is visible.
15. Confirm disclaimers are visible.

---

## 21. UI/UX Style Direction

Use a clean academic/legal research interface.

Suggested visual style:

- Neutral background.
- Dark text for readability.
- Simple cards and tables.
- Status badges for processing and verification.
- Relationship type badges.
- Clear section text viewer.
- Avoid overly commercial design.

Status badge examples:

- Uploaded
- Processing
- Processed
- Failed
- Pending Review
- Verified
- Rejected
- Needs Review

Relationship badge examples:

- Refers To
- Amends
- Repeals
- Inserts
- Substitutes
- Cross Reference

---

## 22. Legal and Ethical Implementation Rules

Codex must implement these rules directly into the system:

1. The app must display legal research prototype disclaimers.
2. The app must not describe results as authoritative legal interpretation.
3. The app must not generate personalized legal advice.
4. Unverified extracted references must be clearly marked.
5. General Users must see verified content by default.
6. Participant feedback data must not be collected by default.
7. No sensitive personal data collection should be added.
8. Development/demo accounts must be dummy accounts.
9. Public legal documents may be stored for academic processing, but uploaded file source metadata should be tracked.
10. Errors and limitations must be transparent in Admin processing reports.

---

## 23. Definition of Done

The project is done when:

- Full-stack app runs locally using documented setup.
- Admin can upload and process PDF Legal Acts.
- System extracts metadata and sections.
- System detects and stores statutory references.
- Admin can verify/correct references.
- Lawyer can search section-level data and explore relationships.
- General User can search simplified verified content.
- Search supports keyword and metadata filters.
- Relationship table/graph exists.
- Legal disclaimer appears across relevant pages.
- Evaluation dashboard calculates precision, recall, and F1 using a sample gold set.
- Seed users exist.
- README explains setup, usage, architecture, limitations, and demo steps.
- Backend tests pass.
- Frontend builds successfully.

---

## 24. Codex Build Instruction

When using Codex, give this PRD as the project source of truth and instruct it:

> Build the system from scratch according to PRD.md. Work incrementally phase by phase. After each phase, run tests/build checks, summarize changed files, and do not move to optional features until the MVP acceptance criteria pass. Prioritize a working, demo-ready academic prototype over over-engineered architecture. Keep all legal disclaimers and role-based restrictions implemented in both backend and frontend.

---

## 25. Risk Register

| Risk | Impact | Mitigation |
|---|---:|---|
| Poor PDF quality | High | Use PyMuPDF fallback, optional OCR, Admin verification, clear limitations |
| Inconsistent legal citation formats | High | Centralized regex patterns, confidence scoring, manual verification |
| Overly complex semantic search | Medium | Use PostgreSQL full-text as required baseline; pgvector optional |
| Legal advice misunderstanding | High | Repeated disclaimers, no advice chatbot, verified/unverified labels |
| Too large project scope | High | Restrict to English Legal Acts and MVP modules |
| Participant data concerns | Medium | Do not collect participant data by default; use dummy accounts |
| Codex overbuilding | Medium | Follow phases; require tests/build after each phase |

---

## 26. Final Notes for Implementation

This is an academic software engineering development project, not a commercial legal platform. The priority is to demonstrate the technical concept clearly:

- PDF to structured Act metadata.
- Act text to sections.
- Sections to detected references.
- References to mapped relationships.
- Relationships to searchable and visual outputs.
- Admin verification to improve reliability.
- Evaluation metrics to support the final report.

Keep the MVP focused, testable, and explainable.
