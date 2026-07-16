"""模型库服务层 - 管理模型配置、特点标签和性能统计"""

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    EvaluationResult,
    ModelConfig,
    ModelProfile,
    TestCombination,
)
from app.schemas.dto import ModelProfileCreate, ModelProfileUpdate
from app.services.crud import get_or_404


def _serialize_characteristics(characteristics: list[str]) -> str:
    """将特点标签列表序列化为 JSON 字符串"""
    return json.dumps(characteristics, ensure_ascii=False)


def _deserialize_characteristics(characteristics_json: str) -> list[str]:
    """将 JSON 字符串反序列化为特点标签列表"""
    if not characteristics_json or characteristics_json == "[]":
        return []
    try:
        return json.loads(characteristics_json)
    except (json.JSONDecodeError, TypeError):
        return []


def get_model_profile(db: Session, provider: str, name: str) -> ModelProfile | None:
    """根据 provider 和 name 获取模型档案"""
    stmt = select(ModelProfile).where(
        ModelProfile.provider == provider,
        ModelProfile.name == name,
    )
    return db.scalar(stmt)


def get_model_profile_by_id(db: Session, profile_id: int) -> ModelProfile:
    """根据 ID 获取模型档案，不存在则抛出 404"""
    return get_or_404(db, ModelProfile, profile_id)


def list_model_profiles(db: Session, active_only: bool = True) -> list[ModelProfile]:
    """列出所有模型档案"""
    stmt = select(ModelProfile).order_by(ModelProfile.provider, ModelProfile.name)
    if active_only:
        stmt = stmt.where(ModelProfile.is_active == True)
    return list(db.scalars(stmt).all())


def create_model_profile(db: Session, payload: ModelProfileCreate) -> ModelProfile:
    """创建新模型档案"""
    # 检查是否已存在相同 provider + name 的模型
    existing = get_model_profile(db, payload.provider, payload.name)
    if existing:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Model {payload.provider}/{payload.name} already exists",
        )

    data = payload.model_dump(exclude={"characteristics"})
    data["characteristics_json"] = _serialize_characteristics(payload.characteristics)

    profile = ModelProfile(**data)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_model_profile(db: Session, profile_id: int, payload: ModelProfileUpdate) -> ModelProfile:
    """更新模型档案"""
    profile = get_model_profile_by_id(db, profile_id)

    data = payload.model_dump(exclude_unset=True, exclude={"characteristics"})

    # 处理 characteristics 字段
    if payload.characteristics is not None:
        data["characteristics_json"] = _serialize_characteristics(payload.characteristics)

    for key, value in data.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile


def deactivate_model_profile(db: Session, profile_id: int) -> ModelProfile:
    """禁用模型（不删除，保留历史数据）"""
    profile = get_model_profile_by_id(db, profile_id)
    profile.is_active = False
    db.commit()
    db.refresh(profile)
    return profile


def activate_model_profile(db: Session, profile_id: int) -> ModelProfile:
    """启用模型"""
    profile = get_model_profile_by_id(db, profile_id)
    profile.is_active = True
    db.commit()
    db.refresh(profile)
    return profile


def update_model_characteristics(db: Session, profile_id: int, characteristics: list[str]) -> ModelProfile:
    """更新模型特点标签"""
    profile = get_model_profile_by_id(db, profile_id)
    profile.characteristics_json = _serialize_characteristics(characteristics)
    db.commit()
    db.refresh(profile)
    return profile


def aggregate_model_performance(db: Session, profile_id: int) -> ModelProfile:
    """从所有已完成的测试组合中聚合该模型的平均评分，更新到 ModelProfile"""
    profile = get_model_profile_by_id(db, profile_id)

    # 查找所有使用该 provider + name 的 ModelConfig
    model_configs_stmt = select(ModelConfig.id).where(
        ModelConfig.provider == profile.provider,
        ModelConfig.name == profile.name,
    )
    model_config_ids = [row[0] for row in db.execute(model_configs_stmt).all()]

    if not model_config_ids:
        # 没有测试数据，重置统计
        profile.avg_total_score = 0
        profile.avg_truthfulness_score = 0
        profile.avg_cost_efficiency_score = 0
        profile.total_test_count = 0
        db.commit()
        db.refresh(profile)
        return profile

    # 查询这些 ModelConfig 对应的已完成测试组合的评估结果
    stmt = (
        select(
            func.count(EvaluationResult.id).label("count"),
            func.avg(EvaluationResult.total_score).label("avg_total"),
            func.avg(EvaluationResult.truthfulness_score).label("avg_truthfulness"),
            func.avg(EvaluationResult.cost_efficiency_score).label("avg_cost_efficiency"),
        )
        .join(TestCombination, EvaluationResult.combination_id == TestCombination.id)
        .where(
            TestCombination.model_config_id.in_(model_config_ids),
            TestCombination.status == "completed",
        )
    )

    result = db.execute(stmt).one()
    count = result.count or 0
    avg_total = result.avg_total or 0
    avg_truthfulness = result.avg_truthfulness or 0
    avg_cost_efficiency = result.avg_cost_efficiency or 0

    profile.total_test_count = count
    profile.avg_total_score = round(avg_total, 2)
    profile.avg_truthfulness_score = round(avg_truthfulness, 2)
    profile.avg_cost_efficiency_score = round(avg_cost_efficiency, 2)

    db.commit()
    db.refresh(profile)
    return profile


def get_recommended_models(db: Session, task_requirement: str, limit: int = 3) -> list[ModelProfile]:
    """根据任务需求推荐模型（基于特点标签和历史评分）

    当前实现：按平均总分排序，返回评分最高的 limit 个活跃模型。
    后续可基于 task_requirement 做更智能的匹配（如关键词匹配特点标签）。
    """
    stmt = (
        select(ModelProfile)
        .where(ModelProfile.is_active == True)
        .order_by(ModelProfile.avg_total_score.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def model_profile_to_dict(profile: ModelProfile) -> dict[str, Any]:
    """将 ModelProfile 转换为字典，用于注入到 Agent Prompt 中"""
    return {
        "id": profile.id,
        "provider": profile.provider,
        "name": profile.name,
        "display_name": profile.display_name or profile.name,
        "supports_search": profile.supports_search,
        "search_mode": profile.search_mode,
        "input_price_per_1k": profile.input_price_per_1k,
        "output_price_per_1k": profile.output_price_per_1k,
        "characteristics": _deserialize_characteristics(profile.characteristics_json),
        "avg_total_score": profile.avg_total_score,
        "avg_truthfulness_score": profile.avg_truthfulness_score,
        "avg_cost_efficiency_score": profile.avg_cost_efficiency_score,
        "total_test_count": profile.total_test_count,
    }
