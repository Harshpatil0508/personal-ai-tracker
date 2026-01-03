from datetime import datetime, timedelta,timezone
from jose import jwt
from passlib.context import CryptContext
from app.config import JWT_SECRET
import hashlib

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 1

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    password_bytes = password.encode("utf-8")
    safe_password = hashlib.sha256(password_bytes).digest()
    return pwd_context.hash(safe_password)

def verify_password(password: str, hashed: str):
    password_bytes = password.encode("utf-8")
    safe_password = hashlib.sha256(password_bytes).digest()
    return pwd_context.verify(safe_password, hashed)

def create_access_token(user_id: int):
    payload = {
        "sub": str(user_id), # Must be string per JWT spec
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
