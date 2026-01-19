from app.database.database import SessionLocal
from app.database.models import AIEmbedding
from app.aiEmbeddings import generate_embedding

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

