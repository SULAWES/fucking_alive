from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "app_env": settings.app_env}

