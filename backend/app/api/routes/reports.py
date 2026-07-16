from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Report
from app.schemas.dto import ReportRead
from app.services.execution import get_latest_report

router = APIRouter()


@router.get("/batch/{batch_id}", response_model=ReportRead)
def report_for_batch(batch_id: int, db: Session = Depends(get_db)) -> Report:
    report = get_latest_report(db, batch_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not generated")
    return report


@router.get("/{report_id}", response_model=ReportRead)
def report_detail(report_id: int, db: Session = Depends(get_db)) -> Report:
    report = db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report

