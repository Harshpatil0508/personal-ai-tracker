"""
REFLECTA — Auth Router
Registration, login, logout, token refresh, and deep onboarding.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status, Request
from sqlalchemy.orm import Session
from hashlib import sha256
from jose import jwt, JWTError

from app.dependencies import get_current_user_id
from app.database.models import User, RefreshToken, UserOnboarding
from app.schemas import UserCreate, UserLogin, OnboardingCreate, OnboardingOut
from app.auth import hash_password, verify_password, create_access_token, create_refresh_token
from app.config import JWT_SECRET
from app.database.db import get_db
from app.security.login_rate_limit import enforce_login_rate_limit
from app.security.refresh_rate_limit import enforce_refresh_limit
from app.security.register_rate_limit import enforce_register_limit

router = APIRouter(prefix="/auth", tags=["Auth"])


# ─── REGISTER ────────────────────────────────────────────────────
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host
    enforce_register_limit(client_ip)

    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    db_user = User(
        email=user.email,
        name=user.name,
        role="user",
        password_hash=hash_password(user.password),
        coach_tone=user.coach_tone,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {"message": "User registered successfully", "user_id": db_user.id}


# ─── LOGIN ───────────────────────────────────────────────────────
@router.post("/login")
def login(user: UserLogin, response: Response, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host
    enforce_login_rate_limit(client_ip, user.email)

    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(db_user.id, db_user.role, db_user.token_version)
    refresh_token, token_hash, expires_at = create_refresh_token(db_user.id)

    db.add(RefreshToken(
        token_hash=token_hash,
        user_id=db_user.id,
        expires_at=expires_at,
    ))
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/auth/refresh",
    )

    return {
        "access_token": access_token,
        "onboarding_complete": db_user.onboarding_complete,
    }


# ─── ONBOARDING (Deep Interview) ────────────────────────────────
@router.post("/onboarding", status_code=status.HTTP_201_CREATED)
def save_onboarding(
    data: OnboardingCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Save the deep onboarding interview. Can only be done once."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.onboarding_complete:
        raise HTTPException(status_code=400, detail="Onboarding already completed")

    existing = db.query(UserOnboarding).filter_by(user_id=user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Onboarding already exists")

    onboarding = UserOnboarding(
        user_id=user_id,
        life_area_focus=data.life_area_focus,
        past_failures=data.past_failures,
        ideal_day=data.ideal_day,
        biggest_excuse=data.biggest_excuse,
        life_scores=data.life_scores,
    )

    db.add(onboarding)
    user.onboarding_complete = True
    db.commit()
    db.refresh(onboarding)

    return {"message": "Onboarding completed successfully"}


@router.get("/onboarding", response_model=OnboardingOut)
def get_onboarding(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieve onboarding data for the current user."""
    onboarding = db.query(UserOnboarding).filter_by(user_id=user_id).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")
    return onboarding


# ─── REFRESH ─────────────────────────────────────────────────────
@router.post("/refresh")
def refresh(response: Response, refresh_token: str = Cookie(None), db: Session = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    enforce_refresh_limit(user_id)

    token_hash = sha256(refresh_token.encode()).hexdigest()
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not stored:
        raise HTTPException(status_code=401, detail="Token revoked")

    db.delete(stored)

    new_refresh, new_hash, expires_at = create_refresh_token(user_id)
    db.add(RefreshToken(
        token_hash=new_hash,
        user_id=user_id,
        expires_at=expires_at,
    ))
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/auth/refresh",
    )

    user = db.query(User).get(user_id)
    return {"access_token": create_access_token(user.id, user.role, user.token_version)}


# ─── LOGOUT ──────────────────────────────────────────────────────
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
    user.token_version += 1

    if refresh_token:
        token_hash = sha256(refresh_token.encode()).hexdigest()
        db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).delete()

    db.commit()
    response.delete_cookie("refresh_token", path="/auth/refresh")

    return {"message": "Logged out successfully"}
