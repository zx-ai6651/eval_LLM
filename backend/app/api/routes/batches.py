from datetime import datetime
import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models.entities import TestBatch, TestResult
from app.schemas.dto import ApiMessage, BatchCreate, BatchDetail, BatchRead, CombinationDetail, GeneratedCombinations
from app.services.execution import create_batch_with_combinations, delete_batch, get_batch_detail, progress_for_batch, run_batch

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/task/{task_id}", response_model=list[BatchRead])
def list_batches(task_id: int, db: Session = Depends(get_db)) -> list[TestBatch]:
    return list(db.scalars(select(TestBatch).where(TestBatch.task_id == task_id).order_by(TestBatch.created_at.desc())))


@router.post("/task/{task_id}", response_model=GeneratedCombinations)
def create_batch(task_id: int, payload: BatchCreate, db: Session = Depends(get_db)) -> GeneratedCombinations:
    batch = create_batch_with_combinations(db, task_id, payload)
    return GeneratedCombinations(batch=batch, combinations=batch.combinations, estimated_count=len(batch.combinations))


@router.get("/{batch_id}", response_model=BatchDetail)
def batch_detail(batch_id: int, db: Session = Depends(get_db)) -> BatchDetail:
    batch = get_batch_detail(db, batch_id)
    return _to_batch_detail(batch)


@router.post("/{batch_id}/run", response_model=BatchRead)
async def start_batch(
    batch_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> TestBatch:
    batch = get_batch_detail(db, batch_id)
    if batch.status in {"running", "completed"}:
        return batch
    background_tasks.add_task(_run_batch_background, batch_id)
    batch.status = "queued"
    db.commit()
    db.refresh(batch)
    return batch


@router.delete("/{batch_id}", response_model=ApiMessage)
def delete(batch_id: int, db: Session = Depends(get_db)) -> ApiMessage:
    delete_batch(db, batch_id)
    return ApiMessage(message="batch deleted")


async def _run_batch_background(batch_id: int) -> None:
    db = SessionLocal()
    try:
        await run_batch(db, batch_id)
    except Exception as exc:
        logger.exception("Batch background task failed: batch_id=%s", batch_id)
        _mark_background_failure(db, batch_id, exc)
    finally:
        db.close()


def _mark_background_failure(db: Session, batch_id: int, exc: Exception) -> None:
    try:
        db.rollback()
        batch = get_batch_detail(db, batch_id)
        now = datetime.utcnow()
        message = _background_error_message(exc)
        batch.status = "failed"
        batch.failure_reason = message
        batch.ended_at = now
        if batch.started_at:
            batch.duration_ms = int((now - batch.started_at).total_seconds() * 1000)
        if batch.task:
            batch.task.status = "failed"
        for combo in batch.combinations:
            if combo.status in {"pending", "queued", "running"}:
                combo.status = "failed"
                combo.ended_at = now
                if combo.started_at:
                    combo.duration_ms = int((now - combo.started_at).total_seconds() * 1000)
                result = combo.result or db.scalar(select(TestResult).where(TestResult.combination_id == combo.id))
                if result is None:
                    db.add(TestResult(combination_id=combo.id, error_message=message))
                elif not result.error_message:
                    result.error_message = message
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist batch background failure: batch_id=%s", batch_id)


def _background_error_message(exc: Exception) -> str:
    text = str(exc)
    detail = f"{exc.__class__.__name__}: {text}" if text else exc.__class__.__name__
    return f"后台任务异常，批次已终止：{detail}"


def _to_batch_detail(batch: TestBatch) -> BatchDetail:
    combinations = []
    for combo in batch.combinations:
        combinations.append(
            CombinationDetail(
                id=combo.id,
                batch_id=combo.batch_id,
                prompt_id=combo.prompt_id,
                model_config_id=combo.model_config_id,
                parameter_config_id=combo.parameter_config_id,
                status=combo.status,
                duration_ms=combo.duration_ms,
                cost=combo.cost,
                created_at=combo.created_at,
                updated_at=combo.updated_at,
                prompt_name=combo.prompt.name,
                model_name=combo.model_config.name,
                parameter_name=combo.parameter_config.name,
                result=combo.result,
                evaluation=combo.evaluation,
            )
        )
    return BatchDetail(
        id=batch.id,
        task_id=batch.task_id,
        name=batch.name,
        status=batch.status,
        started_at=batch.started_at,
        ended_at=batch.ended_at,
        duration_ms=batch.duration_ms,
        total_cost=batch.total_cost,
        failure_reason=batch.failure_reason,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        combinations=combinations,
        progress=progress_for_batch(batch),
    )
