from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.orm import Session
from hashlib import sha256
from app.database import SessionLocal
from app.models import DailyLog, User, RefreshToken
from app.schemas import DailyLogCreate, UserCreate, UserLogin
from app.auth import hash_password, verify_password, create_access_token, create_refresh_token
from app.dependencies import get_current_user,require_role, get_current_user_id
from app.config import JWT_SECRET
from jose import jwt, JWTError

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
def login(
    user: UserLogin,
    response: Response,
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(db_user.id, db_user.role)
    refresh_token, token_hash, expires_at = create_refresh_token(db_user.id)

    db.add(
        RefreshToken(
            token_hash=token_hash,
            user_id=db_user.id,
            expires_at=expires_at
        )
    )
    db.commit()

    # HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,        # HTTPS only in prod
        samesite="strict",
        path="/refresh"
    )

    return {"access_token": access_token}

@router.post("/daily-log")
def create_daily_log(
    log: DailyLogCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    entry = DailyLog(
        user_id=user_id,
        **log.model_dump()
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {"message": "Daily log saved successfully"}

@router.get("/admin/dashboard")
def admin_dashboard(
    user = Depends(require_role("admin"))
):
    return {"message": "Welcome admin"}

@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    if refresh_token:
        token_hash = sha256(refresh_token.encode()).hexdigest()
        db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).delete()
        db.commit()

    response.delete_cookie("refresh_token", path="/refresh")

    return {"message": "Logged out successfully"}


# from fastapi import Cookie
# from jose import jwt, JWTError
# from hashlib import sha256
# from app.config import JWT_SECRET

@router.post("/refresh")
def refresh(
    response: Response,
    refresh_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=["HS256"])

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token")

        user_id = int(payload["sub"])

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_hash = sha256(refresh_token.encode()).hexdigest()

    stored_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not stored_token:
        raise HTTPException(status_code=401, detail="Token revoked")

    # 🔁 ROTATION: delete old token
    db.delete(stored_token)

    new_refresh_token, new_hash, expires_at = create_refresh_token(user_id)
    db.add(
        RefreshToken(
            token_hash=new_hash,
            user_id=user_id,
            expires_at=expires_at
        )
    )

    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/refresh"
    )

    user = db.query(User).get(user_id)

    return {
        "access_token": create_access_token(user.id, user.role)
    }
