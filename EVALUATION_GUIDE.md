# Evaluation Guide

This guide describes deterministic academic evaluation for the MVP. The system is not a legal authority and does not provide legal advice, legal opinions, recommendations, or interpretation.

## Gold Dataset Format

Use a CSV or JSON file outside the application, then enter representative rows through the Admin Evaluation page.

Recommended fields:

```csv
document_identifier,act_id,source_section_id,expected_section_number,expected_section_path,expected_raw_text,expected_relationship_type,expected_target_act_title,expected_target_act_number,expected_target_year,expected_target_section_path,notes
```

Minimum required fields for current in-app reference evaluation:

```csv
expected_raw_text,expected_relationship_type,expected_target_act_title,expected_target_section_number
```

## Metric Definitions

- Precision: true positives divided by predicted references.
- Recall: true positives divided by gold references.
- F1-score: harmonic mean of precision and recall.
- False positive: extracted reference not present in the gold dataset.
- False negative: gold reference not detected by the system.
- Section segmentation accuracy: matched expected section identifiers divided by expected section identifiers, when section identifiers are available.

## Recommended Dataset

Use 8-12 public English-language Sri Lankan Legal Act PDFs:

- amendment Acts,
- matching principal Acts where available,
- at least one schedule-heavy Act,
- at least one longer Act,
- at least one document with cross-references.

Manually verify 30-50 references as gold data. Include amendment, repeal, insertion, substitution, addition, schedule, and cross-reference examples.

## Evaluation Method

1. Upload and process the selected PDFs.
2. Admin reviews metadata, sections, references, and mappings.
3. Add manually verified gold references.
4. Run evaluation from the Admin Evaluation page.
5. Record precision, recall, F1-score, mismatch examples, section segmentation accuracy if available, mapping counts, and processing warnings.

## Limitations

- English-language Legal Act PDFs only.
- PDF extraction quality depends on source PDF quality.
- Scanned/image-only PDFs require OCR, which is disabled in the MVP.
- Extraction, segmentation, and mapping are rule-based.
- Unresolved references require Admin review.
- Metrics depend on manually prepared gold data.
- The system is for legal information retrieval support only and is not legal advice.
