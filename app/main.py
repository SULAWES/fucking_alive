from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.admin_alerts import router as admin_alerts_router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.services.feishu_longconn import start_feishu_long_connection


configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_feishu_long_connection()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(health_router)
app.include_router(admin_alerts_router)
