from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dto import PipelineCommitRead, PipelineCommitRequest, PipelineDraftRead, PipelineDraftRequest
from app.services.pipeline import commit_pipeline_draft, generate_pipeline_draft

router = APIRouter()


@router.post("/draft", response_model=PipelineDraftRead)
async def create_pipeline_draft(payload: PipelineDraftRequest) -> PipelineDraftRead:
    return await generate_pipeline_draft(payload.requirement)


@router.post("/commit", response_model=PipelineCommitRead)
def commit_pipeline(payload: PipelineCommitRequest, db: Session = Depends(get_db)) -> PipelineCommitRead:
    return commit_pipeline_draft(db, payload.draft)
