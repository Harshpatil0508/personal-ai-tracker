from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import uuid, os

from app.database.db import get_db
from app.database.models import User
from app.dependencies import get_current_user_id
from app.schemas import UpdateProfile, UpdatePassword, UpdatePreferences
from app.auth import verify_password, hash_password

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
def get_me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return db.query(User).get(user_id)


@router.patch("/profile")
def update_profile(payload: UpdateProfile, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    user.name = payload.name
    db.commit()
    return {"message": "Profile updated"}


@router.patch("/password")
def change_password(payload: UpdatePassword, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "Wrong current password")

    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    db.commit()

    return {"message": "Password updated"}


@router.patch("/preferences")
def update_preferences(payload: UpdatePreferences, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)

    for k, v in payload.model_dump().items():
        setattr(user, k, v)

    db.commit()
    return {"message": "Preferences saved"}


@router.post("/avatar")
def upload_avatar(file: UploadFile = File(...), user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    os.makedirs("uploads", exist_ok=True)

    filename = f"{uuid.uuid4()}_{file.filename}"
    path = f"uploads/{filename}"

    with open(path, "wb") as f:
        f.write(file.file.read())

    user = db.query(User).get(user_id)
    user.avatar_url = f"/uploads/{filename}"
    db.commit()

    return {"avatar_url": user.avatar_url}
