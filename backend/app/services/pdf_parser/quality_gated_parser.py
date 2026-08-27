import math

from app.services.pdf_parser.base import ParsedPdf, PdfExtractionError, PdfParser
from app.services.pdf_parser.preparation import prepare_act_pages
from app.services.reference_extractor import extract_references
from app.services.section_segmenter import segment_act_text
from app.services.text_cleaner import normalize_for_search

STRUCTURAL_REVIEW_WARNING = (
    "Native structural validation failed and no fallback passed; manual review required."
)


class QualityGatedPdfParser:
    """Try parsers in order, accepting only structurally usable intermediate output."""

    parser_name = "QUALITY_GATED"

    def __init__(
        self,
        primary: PdfParser,
        docling_fallback: PdfParser | None,
        final_fallback: PdfParser,
    ) -> None:
        self.primary = primary
        self.docling_fallback = docling_fallback
        self.final_fallback = final_fallback

    def extract(self, file_path: str) -> ParsedPdf:
        warnings: list[str] = []
        baseline: ParsedPdf | None = None
        baseline_error: Exception | None = None
        try:
            baseline = self.final_fallback.extract(file_path)
        except Exception as exc:
            baseline_error = exc
            warnings.append(f"{self.final_fallback.parser_name} baseline extraction failed: {exc}")

        baseline_text = prepare_act_pages(baseline).text if baseline is not None else None
        candidates = [self.primary]
        if self.docling_fallback is not None:
            candidates.append(self.docling_fallback)

        for parser in candidates:
            try:
                parsed = parser.extract(file_path)
            except Exception as exc:
                warnings.append(f"{parser.parser_name} extraction failed: {exc}")
                continue

            quality_errors = segmentation_quality_errors(
                parsed,
                processing_text=prepare_act_pages(parsed).text,
                baseline_text=baseline_text,
            )
            if not quality_errors:
                parsed.warnings = [*warnings, *parsed.warnings]
                return parsed
            warnings.append(
                f"{parsed.parser_name} quality gate failed: {'; '.join(quality_errors)}"
            )
            warnings.extend(parsed.warnings)

        if baseline is None:
            raise PdfExtractionError(
                f"All PDF extraction routes failed; final fallback error: {baseline_error}",
                parser_name=getattr(self.final_fallback, "parser_name", "UNKNOWN"),
                warnings=warnings,
            ) from baseline_error
        if baseline_text is not None and segmentation_quality_errors(
            baseline, processing_text=baseline_text
        ):
            warnings.append(STRUCTURAL_REVIEW_WARNING)
        baseline.warnings = [*warnings, *baseline.warnings]
        return baseline


def segmentation_quality_errors(
    parsed: ParsedPdf,
    *,
    processing_text: str,
    baseline_text: str | None = None,
) -> list[str]:
    text = processing_text.strip()
    if not text:
        return ["no text was extracted"]

    errors: list[str] = []
    if parsed.page_count > 0 and len(text) / parsed.page_count < 40:
        errors.append("extracted text is implausibly sparse")

    segmentation = segment_act_text(text)
    section_count = int(segmentation.summary["sections_detected"])
    minimum_sections = min(5, max(1, parsed.page_count // 20))
    if segmentation.summary["fallback_used"] or section_count < minimum_sections:
        errors.append(
            f"detected {section_count} numbered section(s); expected at least {minimum_sections}"
        )
    if baseline_text is not None and baseline_text.strip():
        errors.extend(_baseline_coverage_errors(text, section_count, baseline_text))
    return errors


def _baseline_coverage_errors(text: str, section_count: int, baseline_text: str) -> list[str]:
    errors: list[str] = []
    baseline_sections = int(segment_act_text(baseline_text).summary["sections_detected"])
    if baseline_sections and section_count < math.ceil(baseline_sections * 0.8):
        errors.append(
            f"section coverage is below PyMuPDF baseline ({section_count}/{baseline_sections})"
        )

    baseline_spans = {
        span
        for draft in extract_references(baseline_text)
        if len(span := normalize_for_search(draft.raw_reference_text)) >= 12
    }
    if baseline_spans:
        normalized_candidate = normalize_for_search(text)
        retained = sum(span in normalized_candidate for span in baseline_spans)
        if retained < math.ceil(len(baseline_spans) * 0.8):
            errors.append(
                "citation-bearing text is below PyMuPDF baseline "
                f"({retained}/{len(baseline_spans)} spans retained)"
            )
    return errors
