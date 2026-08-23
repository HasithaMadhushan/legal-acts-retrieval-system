from __future__ import annotations

import hashlib
import math
import re

from app.core.config import get_settings


def embed_text(text: str) -> list[float]:
    """Deterministic embedding used when no external model is configured.

    Hash-based vectors keep SQLite tests and local dev working without
    sentence-transformers or paid APIs. Swap `embedding_provider` to a model
    backend when running the retrieval evaluation.
    """
    settings = get_settings()
    dimension = settings.embedding_dimension
    normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not normalized:
        return [0.0] * dimension
    seed = hashlib.sha256(normalized.encode("utf-8")).digest()
    values: list[float] = []
    block = seed
    while len(values) < dimension:
        block = hashlib.sha256(block).digest()
        values.extend((byte / 255.0) * 2 - 1 for byte in block)
    vector = values[:dimension]
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [item / norm for item in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))
