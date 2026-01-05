from fastapi import APIRouter, Depends
from app.dependencies import require_role

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/dashboard")
def dashboard(user=Depends(require_role("admin"))):
    return {"message": "Welcome admin"}
