import html
import re

_EMBEDDED_BOLD_SECTION_RE = re.compile(
    r"(?m)(?P<leading>[^\n])[ \t]*\*\*(?P<number>\d{1,3}[A-Z]?)\.\*\*[ \t]*"
)
_BOLD_SECTION_RE = re.compile(
    r"(?m)^[ \t]*\*\*(?P<number>\d{1,3}[A-Z]?)\.\*\*[ \t]*"
)
_MARKDOWN_LINK_RE = re.compile(r"!?\[(?P<label>[^\]]*)\]\([^)]*\)")
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
_LEGAL_TABLE_SECTION_RE = re.compile(
    r"(?m)^\|(?P<number>\d{1,3}[A-Z]?)\.\|(?P<remaining>.+)\|$"
)


def markdown_to_legal_text(markdown: str) -> str:
    """Convert parser Markdown into line-oriented text for legal extraction.

    Section markers are restored to the plain ``4.`` form expected by the
    section segmenter. Table rows remain delimited so table-of-contents entries
    cannot accidentally become operative section boundaries.
    """

    text = html.unescape(markdown.replace("\r\n", "\n").replace("\r", "\n"))
    text = _MARKDOWN_LINK_RE.sub(lambda match: match.group("label"), text)
    text = _HTML_TAG_RE.sub("", text)
    text = _LEGAL_TABLE_SECTION_RE.sub(_restore_table_section_row, text)
    text = _EMBEDDED_BOLD_SECTION_RE.sub(
        lambda match: f"{match.group('leading').rstrip()}\n{match.group('number')}. ", text
    )
    text = _BOLD_SECTION_RE.sub(lambda match: f"{match.group('number')}. ", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w)", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _restore_table_section_row(match: re.Match[str]) -> str:
    cells = match.group("remaining").split("|")
    if len(cells) < 3:
        return match.group(0)
    content = " ".join(cell.strip() for cell in cells if cell.strip())
    return f"{match.group('number')}. {content}".rstrip()
