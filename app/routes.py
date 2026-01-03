from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import DailyLog, User
from app.schemas import DailyLogCreate, UserCreate, UserLogin
from app.auth import hash_password, verify_password,create_access_token
from app.dependencies import get_current_user
from fastapi import HTTPException


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    db_user = User(
        email=user.email,
        name=user.name,
        password_hash=hash_password(user.password)
    )
    db.add(db_user)
    db.commit()
    return {"message": "User registered successfully"}

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(db_user.id)
    return {"access_token": token, "token_type": "bearer"}

@router.post("/daily-log")
def create_daily_log(
    log: DailyLogCreate,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = DailyLog(user_id=user_id, **log.model_dump())
    db.add(entry)
    db.commit()
    return {"message": "Daily log saved"}
