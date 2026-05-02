"""
REFLECTA — Users Router
Profile management, password change, avatar upload.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import uuid
import os

from app.database.db import get_db
from app.database.models import User
from app.dependencies import get_current_user_id
from app.schemas import UpdateProfile, UpdatePassword, UserProfileOut
from app.auth import verify_password, hash_password

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfileOut)
def get_me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfileOut(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        coach_tone=user.coach_tone.value if hasattr(user.coach_tone, 'value') else user.coach_tone,
        onboarding_complete=user.onboarding_complete,
    )


@router.patch("/profile")
def update_profile(payload: UpdateProfile, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)

    if payload.name is not None:
        user.name = payload.name
    if payload.coach_tone is not None:
        user.coach_tone = payload.coach_tone

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
