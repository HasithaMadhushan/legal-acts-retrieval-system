from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON

SECTION_EMBEDDING_DIMENSION = 384
embedding_type = JSON().with_variant(Vector(SECTION_EMBEDDING_DIMENSION), "postgresql")
