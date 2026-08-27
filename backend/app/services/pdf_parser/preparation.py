from dataclasses import dataclass

from app.services.pdf_parser.base import PAGE_SEPARATOR, ParsedPdf
from app.services.text_cleaner import clean_text


@dataclass(frozen=True)
class PageSpan:
    page_number: int
    start: int
    end: int


@dataclass(frozen=True)
class PreparedPages:
    text: str
    page_spans: list[PageSpan] | None


def prepare_act_pages(parsed: ParsedPdf) -> PreparedPages:
    pages = (
        parsed.structured_document.pages
        if parsed.structured_document is not None
        else None
    )
    if pages is None:
        return PreparedPages(text=clean_text(parsed.full_text), page_spans=None)

    cleaned_pages = [clean_text(page.text) for page in pages]
    joined, spans = _join_cleaned_pages(cleaned_pages)
    text, rebased = _rebase_spans(joined, spans)
    return PreparedPages(text=text, page_spans=rebased)


def _join_cleaned_pages(cleaned_pages: list[str]) -> tuple[str, list[PageSpan]]:
    parts: list[str] = []
    spans: list[PageSpan] = []
    offset = 0
    last_index = len(cleaned_pages) - 1
    for index, page_text in enumerate(cleaned_pages):
        start = offset
        end = start + len(page_text)
        spans.append(PageSpan(page_number=index + 1, start=start, end=end))
        parts.append(page_text)
        offset = end
        if index != last_index:
            parts.append(PAGE_SEPARATOR)
            offset += len(PAGE_SEPARATOR)
    return "".join(parts), spans


def _rebase_spans(text: str, spans: list[PageSpan]) -> tuple[str, list[PageSpan]]:
    stripped = text.strip()
    lead = len(text) - len(text.lstrip())
    length = len(stripped)
    rebased = [_rebased_span(span, lead, length) for span in spans]
    return stripped, rebased


def _rebased_span(span: PageSpan, lead: int, length: int) -> PageSpan:
    start = _clip(span.start - lead, length)
    end = max(_clip(span.end - lead, length), start)
    return PageSpan(page_number=span.page_number, start=start, end=end)


def _clip(value: int, length: int) -> int:
    return min(max(value, 0), length)
