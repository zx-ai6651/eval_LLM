from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.dto import HealthRead

router = APIRouter()


@router.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    settings = get_settings()
    return HealthRead(status="ok", app=settings.app_name, environment=settings.app_env)

