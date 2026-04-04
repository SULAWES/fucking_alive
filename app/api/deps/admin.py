from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_admin_token(authorization: str | None = Header(default=None)) -> None:
    expected = settings.admin_token.strip()
    if not expected:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="ADMIN_TOKEN is not configured.")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token.")
