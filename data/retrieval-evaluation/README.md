# LexAtlas Retrieval Gold Set candidate v0.1

This directory defines the retrieval-evaluation contract for the fixed 12-Act corpus. It is separate from the statutory-reference extraction gold set.

`queries.csv` contains one row per query/relevant-section judgment. A query may therefore occur more than once. `document_identifier` is the immutable corpus PDF filename and `expected_section_path` is the parser's stable top-level section path; runtime UUIDs are deliberately excluded.

Relevance grades are:

- `2`: directly answers the query or is the exact identifier target.
- `1`: related and useful but less direct than a grade-2 target.
- `0`: no relevant section exists in this corpus; `expected_section_path` must be empty.

The query categories cover exact Act identifiers, exact sections, legal terminology, paraphrases, amendment relationships, ambiguous language, spelling/format variants, and hard negatives.

## Annotation status

The current file is a source-grounded candidate, not yet the frozen v1.0 release set. `codex-source-pass-1` and `codex-source-pass-2` identify two separate inspection passes over the checksum-pinned PDFs; they are not claims of two human annotators. Entries marked `adjudicated` had competing relevant sections resolved into graded judgments during the second pass.

Before calling this `LexAtlas Retrieval Gold Set v1.0` or using it to enable semantic serving, two human domain reviewers must independently check at least 20% of the queries and record/adjudicate disagreements. Until then evaluation results are engineering evidence only, not a validated legal-relevance benchmark.

## Integrity rules

- Preserve query IDs and document identifiers after freeze.
- Add another row for an additional relevant section; never put multiple paths in one cell.
- Never use extractor or search output as relevance truth.
- Verify judgments against the PDF and checksum in `SOURCES.md`.
- Historical evaluation results must be written to a new timestamped directory and never overwritten.
