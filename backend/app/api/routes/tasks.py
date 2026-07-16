from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.db.session import get_db
from app.models.entities import TestTask
from app.schemas.dto import ApiMessage, DashboardSummary, TaskCreate, TaskRead, TaskUpdate
from app.services.crud import archive_task, create_task, get_or_404, task_counts, update_task

router = APIRouter()


@router.get("", response_model=list[TaskRead])
def list_tasks(db: Session = Depends(get_db)) -> list[TestTask]:
    return list(db.scalars(select(TestTask).where(TestTask.status != "archived").order_by(TestTask.created_at.desc())))


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    task_count, batch_count, completed_count = task_counts(db)
    latest = list(
        db.scalars(
            select(TestTask).where(TestTask.status != "archived").order_by(TestTask.created_at.desc()).limit(5)
        )
    )
    return DashboardSummary(
        task_count=task_count,
        batch_count=batch_count,
        completed_batch_count=completed_count,
        latest_tasks=latest,
    )


@router.post("", response_model=TaskRead)
def create(payload: TaskCreate, db: Session = Depends(get_db)) -> TestTask:
    return create_task(db, payload)


@router.get("/{task_id}", response_model=TaskRead)
def detail(task_id: int, db: Session = Depends(get_db)) -> TestTask:
    return get_or_404(db, TestTask, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
def update(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)) -> TestTask:
    return update_task(db, task_id, payload)


@router.delete("/{task_id}", response_model=ApiMessage)
def delete(task_id: int, db: Session = Depends(get_db)) -> ApiMessage:
    archive_task(db, task_id)
    return ApiMessage(message="task archived")
