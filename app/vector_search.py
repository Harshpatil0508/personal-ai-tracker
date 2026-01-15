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
            SELECT content
            FROM ai_embeddings
            WHERE user_id = :user_id
            ORDER BY embedding <-> CAST(:query_vector AS vector)
            LIMIT :limit
        """)

        results = db.execute(
            sql,
            {
                "user_id": user_id,
                "query_vector": query_vector,
                "limit": limit
            }
        ).fetchall()

        return [row[0] for row in results]

    finally:
        db.close()
