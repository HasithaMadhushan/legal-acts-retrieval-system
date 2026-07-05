import re
import unicodedata


def clean_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"(\w)-\n(\w)", r"\1\2", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"(?im)^\s*(printed on|page)\s+\d+.*$", "", normalized)
    return normalized.strip()


def normalize_for_search(text: str | None) -> str:
    if not text:
        return ""
    lowered = unicodedata.normalize("NFKC", text).lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()
