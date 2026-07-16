from fastapi import APIRouter

from app.api.routes import batches, configs, health, model_library, optimization, pipeline, reports, tasks

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(configs.router, tags=["configs"])
api_router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
api_router.include_router(batches.router, prefix="/batches", tags=["batches"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(model_library.router, tags=["model_library"])
api_router.include_router(optimization.router, prefix="/optimization", tags=["optimization"])
