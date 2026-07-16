"""优化方案 API 路由"""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dto import ApiMessage, OptimizationPlanRead
from app.services.optimization_planner import (
    apply_optimization_plan,
    generate_optimization_plan,
    get_optimization_plan,
    list_optimization_plans,
    optimize_and_retest,
)

router = APIRouter()


@router.post("/batches/{batch_id}/plan", response_model=OptimizationPlanRead)
async def create_optimization_plan(
    batch_id: int,
    round_number: int = 1,
    db: Session = Depends(get_db),
) -> OptimizationPlanRead:
    """根据已完成批次的测试结果生成优化方案"""
    return await generate_optimization_plan(db, batch_id, round_number)


@router.post("/plans/{plan_id}/apply", response_model=OptimizationPlanRead)
def apply_plan(
    plan_id: int,
    db: Session = Depends(get_db),
) -> OptimizationPlanRead:
    """应用优化方案：创建新 Prompt/参数/模型配置"""
    return apply_optimization_plan(db, plan_id)


@router.get("/tasks/{task_id}/plans", response_model=list[OptimizationPlanRead])
def list_plans(
    task_id: int,
    db: Session = Depends(get_db),
) -> list[OptimizationPlanRead]:
    """列出任务的所有优化方案"""
    return list_optimization_plans(db, task_id)


@router.get("/plans/{plan_id}", response_model=OptimizationPlanRead)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
) -> OptimizationPlanRead:
    """获取单个优化方案详情"""
    return get_optimization_plan(db, plan_id)


@router.post("/batches/{batch_id}/optimize-and-retest", response_model=OptimizationPlanRead)
async def optimize_and_retest_endpoint(
    batch_id: int,
    max_rounds: int = 3,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
) -> OptimizationPlanRead:
    """一键优化并复测：生成方案→应用→创建新批次→运行→对比
    
    这是一个长运行操作，会在后台执行完整的优化迭代循环。
    """
    return await optimize_and_retest(db, batch_id, max_rounds)
