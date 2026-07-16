from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    EvaluationTarget,
    ModelConfig,
    ParameterConfig,
    Prompt,
    TestBatch,
    TestTask,
)
from app.schemas.dto import (
    EvaluationTargetCreate,
    ModelConfigCreate,
    ParameterConfigCreate,
    PromptCreate,
    TaskCreate,
    TaskUpdate,
)
from app.services.defaults import DEFAULT_EVALUATION_TARGETS

ModelT = TypeVar("ModelT")


def _apply_updates(instance: object, payload: object) -> object:
    data = payload.model_dump(exclude_unset=True)
    if instance.__class__.__name__ == "Prompt":
        if data.get("system_prompt") and "content" not in data:
            data["content"] = data["system_prompt"]
        if data.get("content") and "system_prompt" not in data:
            data["system_prompt"] = data["content"]
    for key, value in data.items():
        setattr(instance, key, value)
    return instance


def get_or_404(db: Session, model: type[ModelT], item_id: int) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


def list_items(db: Session, stmt: Select) -> list:
    return list(db.scalars(stmt).all())


def create_task(db: Session, payload: TaskCreate) -> TestTask:
    task = TestTask(**payload.model_dump(exclude={"use_default_targets"}))
    db.add(task)
    db.flush()
    if payload.use_default_targets:
        for target in DEFAULT_EVALUATION_TARGETS:
            db.add(EvaluationTarget(task_id=task.id, **target))
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task_id: int, payload: TaskUpdate) -> TestTask:
    task = get_or_404(db, TestTask, task_id)
    _apply_updates(task, payload)
    db.commit()
    db.refresh(task)
    return task


def archive_task(db: Session, task_id: int) -> None:
    task = get_or_404(db, TestTask, task_id)
    task.status = "archived"
    db.commit()


def create_prompt(db: Session, task_id: int, payload: PromptCreate) -> Prompt:
    get_or_404(db, TestTask, task_id)
    data = payload.model_dump()
    data["content"] = data.get("content") or data["system_prompt"]
    data["system_prompt"] = data.get("system_prompt") or data["content"]
    data["user_prompt"] = data.get("user_prompt") or ""
    item = Prompt(task_id=task_id, **data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_model_config(db: Session, task_id: int, payload: ModelConfigCreate) -> ModelConfig:
    get_or_404(db, TestTask, task_id)
    item = ModelConfig(task_id=task_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_parameter_config(db: Session, task_id: int, payload: ParameterConfigCreate) -> ParameterConfig:
    get_or_404(db, TestTask, task_id)
    item = ParameterConfig(task_id=task_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_evaluation_target(db: Session, task_id: int, payload: EvaluationTargetCreate) -> EvaluationTarget:
    get_or_404(db, TestTask, task_id)
    item = EvaluationTarget(task_id=task_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def task_counts(db: Session) -> tuple[int, int, int]:
    task_count = db.scalar(select(func.count(TestTask.id))) or 0
    batch_count = db.scalar(select(func.count(TestBatch.id))) or 0
    completed_count = db.scalar(select(func.count(TestBatch.id)).where(TestBatch.status == "completed")) or 0
    return task_count, batch_count, completed_count
