from sqlalchemy import text
from app.database import SessionLocal
from app.ai_embeddings import generate_embedding

def semantic_search(user_id: int, query: str, limit: int = 3):
    db = SessionLocal()
    try:
        query_vector = generate_embedding(query)
        if not query_vector:
            return []

        sql = text("""
            SELECT
                e.content,
                (
                    (e.embedding <-> CAST(:query_vector AS vector))
                    *
                    CASE
                        WHEN f.is_helpful = true THEN 0.8   -- boost helpful
                        WHEN f.is_helpful = false THEN 2.0  -- penalize unhelpful
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
                "query_vector": query_vector,
                "limit": limit,
            }
        ).fetchall()

        return [row.content for row in rows]

    finally:
        db.close()
