import json
import hashlib
from app.cache.redis_client import redis_client


def _hash_text(text: str) -> str:
    """
    Stable hash for embedding cache keys.
    """
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def get_cached_embedding(text: str):
    """
    Fetch embedding from Redis if present.
    """
    key = f"embedding:{_hash_text(text)}"
    cached = redis_client.get(key)

    if not cached:
        return None

    try:
        return json.loads(cached)
    except json.JSONDecodeError:
        redis_client.delete(key)
        return None


def set_cached_embedding(text: str, embedding: list):
    """
    Store embedding in Redis (no TTL).
    """
    key = f"embedding:{_hash_text(text)}"
    redis_client.set(key, json.dumps(embedding))
