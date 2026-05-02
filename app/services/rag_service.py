"""
REFLECTA — RAG Service
Semantic memory recall using pgvector + JINA embeddings.
Adapted from the legacy vector_search module.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.aiEmbeddings.ai_embeddings import generate_embedding
from app.cache.embedding_cache import get_cached_embedding, set_cached_embedding

logger = logging.getLogger(__name__)


def semantic_recall(
    db: Session,
    user_id: int,
    query: str,
    limit: int = 3,
    memory_type: str | None = None,
) -> list[str]:
    """
    Retrieve semantically relevant memories for a user.
    Uses pgvector cosine distance with optional memory_type filter.
    """
    query_clean = query.strip().lower()
    if not query_clean:
        return []

    # Embedding cache lookup
    query_embedding = get_cached_embedding(query_clean)
    if query_embedding is None:
        query_embedding = generate_embedding(query_clean)
        set_cached_embedding(query_clean, query_embedding)

    # Build query with optional type filter
    type_filter = "AND e.memory_type = :memory_type" if memory_type else ""

    sql = text(f"""
        SELECT e.content,
               (e.embedding <-> CAST(:query_vector AS vector)) AS distance
        FROM memory_embeddings e
        WHERE e.user_id = :user_id
        {type_filter}
        ORDER BY distance ASC
        LIMIT :limit
    """)

    params = {
        "user_id": user_id,
        "query_vector": query_embedding,
        "limit": limit,
    }

    if memory_type:
        params["memory_type"] = memory_type

    rows = db.execute(sql, params).fetchall()

    return [row.content for row in rows]


def store_memory(
    db: Session,
    user_id: int,
    content: str,
    memory_type: str,
) -> None:
    """
    Generate embedding and store in memory_embeddings table.
    """
    if not content or not content.strip():
        return

    vector = get_cached_embedding(content)
    if vector is None:
        vector = generate_embedding(content)
        set_cached_embedding(content, vector)

    from app.database.models import MemoryEmbedding

    record = MemoryEmbedding(
        user_id=user_id,
        content=content.strip(),
        embedding=vector,
        memory_type=memory_type,
    )

    db.add(record)
    db.commit()

    logger.info(f"[MEMORY] Stored {memory_type} memory for user {user_id}")
