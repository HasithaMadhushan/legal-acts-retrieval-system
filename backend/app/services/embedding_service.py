class EmbeddingService:
    """Optional extension point for pgvector/sentence-transformer search."""

    enabled = False

    def embed(self, text: str) -> list[float] | None:
        return None
