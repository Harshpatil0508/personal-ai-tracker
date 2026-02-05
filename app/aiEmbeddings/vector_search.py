from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cache.embedding_cache import get_cached_embedding, set_cached_embedding
from app.aiEmbeddings.ai_embeddings import generate_embedding


def semantic_search(db: Session, user_id: int, query: str, limit: int = 3):
    """
    Semantic recall using pgvector.
    Uses Redis caching for query embedding.
    """

    query_clean = query.strip().lower()
    if not query_clean:
        return []

    # 1️⃣ Embedding cache lookup
    query_embedding = get_cached_embedding(query_clean)
    if query_embedding is None:
        query_embedding = generate_embedding(query_clean)
        set_cached_embedding(query_clean, query_embedding)

    sql = text("""
        SELECT
            e.content,
            (
                (e.embedding <-> CAST(:query_vector AS vector))
                *
                CASE
                    WHEN f.is_helpful = true THEN 0.9   -- boost helpful
                    WHEN f.is_helpful = false THEN 1.3  -- penalize unhelpful
                    ELSE 1.0
                END
            ) AS final_score
        FROM ai_embeddings e
        LEFT JOIN ai_feedback f
          ON e.user_id = f.user_id
         AND e.source = f.source
         AND e.source_id = f.source_id
        WHERE e.user_id = :user_id
        ORDER BY final_score ASC
        LIMIT :limit
    """)

    rows = db.execute(
        sql,
        {
            "user_id": user_id,
            "query_vector": query_embedding,
            "limit": limit,
        }
    ).fetchall()

    return [row.content for row in rows]
