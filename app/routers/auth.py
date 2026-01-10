from fastapi import APIRouter, Depends, HTTPException, Response, Cookie,status
from sqlalchemy.orm import Session
from hashlib import sha256
from jose import jwt, JWTError

from app.dependencies import get_current_user_id
from app.models import User, RefreshToken
from app.schemas import UserCreate, UserLogin
from app.auth import hash_password, verify_password, create_access_token, create_refresh_token
from app.config import JWT_SECRET
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    db_user = User(
        email=user.email,
        name=user.name,
        role="user",
        password_hash=hash_password(user.password)
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {"message": "User registered successfully"}

@router.post("/login")
def login(user: UserLogin, response: Response, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(db_user.id, db_user.role, db_user.token_version)
    refresh_token, token_hash, expires_at = create_refresh_token(db_user.id)

    db.add(RefreshToken(
        token_hash=token_hash,
        user_id=db_user.id,
        expires_at=expires_at
    ))
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/auth/refresh"
    )

    return {"access_token": access_token}


@router.post("/refresh")
def refresh(response: Response, refresh_token: str = Cookie(None), db: Session = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_hash = sha256(refresh_token.encode()).hexdigest()

    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not stored:
        raise HTTPException(status_code=401, detail="Token revoked")

    db.delete(stored)

    new_refresh, new_hash, expires_at = create_refresh_token(user_id)
    db.add(RefreshToken(
        token_hash=new_hash,
        user_id=user_id,
        expires_at=expires_at
    ))
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/auth/refresh"
    )

    user = db.query(User).get(user_id)
    return {"access_token": create_access_token(user.id, user.role)}


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str = Cookie(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).get(user_id)
    
    if user.token_version is None:
        user.token_version = 0

    # Invalidate ALL existing tokens
    user.token_version += 1

    if refresh_token:
        token_hash = sha256(refresh_token.encode()).hexdigest()
        db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).delete()

    db.commit()

    # Clear refresh token cookie
    response.delete_cookie("refresh_token", path="/auth/refresh")

    return {"message": "Logged out successfully"}

