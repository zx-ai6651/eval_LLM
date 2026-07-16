"""模型库 API 路由 - 管理模型配置、特点标签和性能统计"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import ModelProfile
from app.schemas.dto import ModelProfileCreate, ModelProfileRead, ModelProfileUpdate
from app.services.model_library import (
    activate_model_profile,
    aggregate_model_performance,
    create_model_profile,
    deactivate_model_profile,
    get_model_profile_by_id,
    get_recommended_models,
    list_model_profiles,
    model_profile_to_dict,
    update_model_profile,
)

router = APIRouter()


@router.get("/models", response_model=list[ModelProfileRead])
def list_models(
    active_only: bool = Query(True, description="是否只返回启用的模型"),
    db: Session = Depends(get_db),
) -> list[ModelProfile]:
    """列出所有模型档案"""
    return list_model_profiles(db, active_only=active_only)


@router.post("/models", response_model=ModelProfileRead)
def create_model(
    payload: ModelProfileCreate,
    db: Session = Depends(get_db),
) -> ModelProfile:
    """添加新模型到模型库"""
    return create_model_profile(db, payload)


@router.get("/models/recommend", response_model=list[ModelProfileRead])
def recommend_models(
    requirement: str = Query(..., description="任务需求描述"),
    limit: int = Query(3, ge=1, le=10, description="推荐数量"),
    db: Session = Depends(get_db),
) -> list[ModelProfile]:
    """根据任务需求推荐模型"""
    return get_recommended_models(db, requirement, limit=limit)


@router.get("/models/{model_id}", response_model=ModelProfileRead)
def get_model(
    model_id: int,
    db: Session = Depends(get_db),
) -> ModelProfile:
    """获取单个模型档案"""
    return get_model_profile_by_id(db, model_id)


@router.put("/models/{model_id}", response_model=ModelProfileRead)
def update_model(
    model_id: int,
    payload: ModelProfileUpdate,
    db: Session = Depends(get_db),
) -> ModelProfile:
    """更新模型档案"""
    return update_model_profile(db, model_id, payload)


@router.post("/models/{model_id}/deactivate", response_model=ModelProfileRead)
def deactivate_model(
    model_id: int,
    db: Session = Depends(get_db),
) -> ModelProfile:
    """禁用模型（不删除，保留历史数据）"""
    return deactivate_model_profile(db, model_id)


@router.post("/models/{model_id}/activate", response_model=ModelProfileRead)
def activate_model(
    model_id: int,
    db: Session = Depends(get_db),
) -> ModelProfile:
    """启用模型"""
    return activate_model_profile(db, model_id)


@router.post("/models/{model_id}/refresh-stats", response_model=ModelProfileRead)
def refresh_model_stats(
    model_id: int,
    db: Session = Depends(get_db),
) -> ModelProfile:
    """手动触发性能统计聚合（从历史测试结果中重新计算）"""
    return aggregate_model_performance(db, model_id)
