"""Cache the pinned embedding model while the release image has network access."""

import os

from sentence_transformers import SentenceTransformer

SentenceTransformer(
    os.environ["EMBEDDING_MODEL"],
    revision=os.environ["EMBEDDING_MODEL_REVISION"],
)
