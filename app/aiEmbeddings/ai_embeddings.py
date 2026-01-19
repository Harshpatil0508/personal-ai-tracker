import requests
from app.config import JINA_API_KEY

_JINA_URL = "https://api.jina.ai/v1/embeddings"
_MODEL = "jina-embeddings-v3"

_session = requests.Session()
_session.headers.update({
    "Authorization": f"Bearer {JINA_API_KEY}",
    "Content-Type": "application/json",
})


def generate_embedding(text: str) -> list[float]:
    
    if not text or not text.strip():
        return []

    try:
        response = _session.post(
            _JINA_URL,
            json={
                "model": _MODEL,
                "input": text
            },
            timeout=20
        )
        response.raise_for_status()

        return response.json()["data"][0]["embedding"]

    except requests.RequestException as e:
        raise RuntimeError(f"Jina v3 embedding failed: {e}")
