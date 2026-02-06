from sqlalchemy.orm import Session

from app.database.models import AIEmbedding
from app.aiEmbeddings.ai_embeddings import generate_embedding
from app.cache.embedding_cache import (
    get_cached_embedding,
    set_cached_embedding,
)


def store_embedding(
    db: Session,
    user_id: int,
    source: str,
    source_id: int,
    content: str
):
    """
    Stores embedding in DB.
    Uses Redis caching to avoid repeated third-party embedding API calls.
    """

    if not content or not content.strip():
        return None

    # Try Redis cache first
    vector = get_cached_embedding(content)

    # If not found, generate + cache forever
    if vector is None:
        vector = generate_embedding(content)
        set_cached_embedding(content, vector)

    # Store in DB
    record = AIEmbedding(
        user_id=user_id,
        source=source,
        source_id=source_id,
        content=content,
        embedding=vector
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record
