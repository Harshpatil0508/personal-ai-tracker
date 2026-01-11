from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from app.config import JWT_SECRET
from hashlib import sha256

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10
REFRESH_TOKEN_EXPIRE_DAYS = 1

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password too long (max 72 bytes)")
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_access_token(user_id: int, role: str, token_version: int) -> str:
    payload = {
        "sub": str(user_id),   # must be string
        "role": role,
        "tv": token_version,
        "type": "access",
        "exp": datetime.now(timezone.utc)
               + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def create_refresh_token(user_id: int):
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expires_at
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    token_hash = sha256(token.encode()).hexdigest()
    return token, token_hash, expires_at

