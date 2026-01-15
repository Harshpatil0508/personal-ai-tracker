from app.database import SessionLocal
from app.models import AIEmbedding
from app.ai_embeddings import generate_embedding

def store_embedding(db, user_id: int, source: str, source_id: int, content: str):
    vector = generate_embedding(content)

    record = AIEmbedding(
        user_id=user_id,
        source=source,
        source_id=source_id,
        content=content,
        embedding=vector
    )

    db.add(record)
    db.commit()

