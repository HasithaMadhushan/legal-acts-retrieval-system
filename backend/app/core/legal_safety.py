import re

from fastapi import HTTPException, status

from app.core.config import NO_LEGAL_ADVICE_MESSAGE

ADVICE_INTENT_RE = re.compile(
    r"\b("
    r"what should i do|should i sue|can i sue|am i liable|my case|my situation|"
    r"do i have a claim|will i win|give me legal advice|legal opinion"
    r")\b",
    re.IGNORECASE,
)


def ensure_no_legal_advice_query(query: str | None) -> None:
    if query and ADVICE_INTENT_RE.search(query):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_LEGAL_ADVICE_MESSAGE,
        )
