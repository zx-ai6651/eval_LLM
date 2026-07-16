from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.db.session import get_db
from app.models.entities import EvaluationTarget, ModelConfig, ParameterConfig, Prompt
from app.schemas.dto import (
    EvaluationTargetCreate,
    EvaluationTargetRead,
    EvaluationTargetUpdate,
    ModelConfigCreate,
    ModelConfigRead,
    ModelConfigUpdate,
    ParameterConfigCreate,
    ParameterConfigRead,
    ParameterConfigUpdate,
    PromptCompareRead,
    PromptCreate,
    PromptDiagnoseRequest,
    PromptDiagnosisRead,
    PromptOptimizedCopyCreate,
    PromptOptimizeRead,
    PromptOptimizeRequest,
    PromptRead,
    PromptUpdate,
)
from app.services.crud import (
    _apply_updates,
    create_evaluation_target,
    create_model_config,
    create_parameter_config,
    create_prompt,
    get_or_404,
)
from app.core.model_adapters import agent_model_options, provider_options
from app.services.prompt_optimization import (
    compare_prompts,
    diagnose_prompt,
    optimize_prompt,
    save_optimized_prompt,
)

router = APIRouter()


@router.get("/model-adapters")
def list_model_adapters() -> dict:
    return {
        "providers": provider_options(),
        "agents": agent_model_options(),
    }


@router.get("/tasks/{task_id}/prompts", response_model=list[PromptRead])
def list_prompts(task_id: int, db: Session = Depends(get_db)) -> list[Prompt]:
    return list(
        db.scalars(
            select(Prompt)
            .where(Prompt.task_id == task_id, Prompt.is_enabled.is_(True))
            .order_by(Prompt.created_at.desc())
        )
    )


@router.post("/tasks/{task_id}/prompts", response_model=PromptRead)
def add_prompt(task_id: int, payload: PromptCreate, db: Session = Depends(get_db)) -> Prompt:
    return create_prompt(db, task_id, payload)


@router.get("/prompts/compare", response_model=PromptCompareRead)
def compare_prompt_scores(
    original_prompt_id: int,
    optimized_prompt_id: int,
    original_batch_id: int | None = None,
    optimized_batch_id: int | None = None,
    db: Session = Depends(get_db),
) -> PromptCompareRead:
    return compare_prompts(db, original_prompt_id, optimized_prompt_id, original_batch_id, optimized_batch_id)


@router.post("/prompts/{prompt_id}/diagnose", response_model=PromptDiagnosisRead)
async def diagnose_prompt_endpoint(
    prompt_id: int,
    payload: PromptDiagnoseRequest,
    db: Session = Depends(get_db),
) -> PromptDiagnosisRead:
    return await diagnose_prompt(db, prompt_id, payload.batch_id, payload.combination_id)


@router.post("/prompts/{prompt_id}/optimize", response_model=PromptOptimizeRead)
async def optimize_prompt_endpoint(
    prompt_id: int,
    payload: PromptOptimizeRequest,
    db: Session = Depends(get_db),
) -> PromptOptimizeRead:
    return await optimize_prompt(
        db,
        prompt_id,
        diagnosis=payload.diagnosis,
        optimization_goal=payload.optimization_goal,
        batch_id=payload.batch_id,
        combination_id=payload.combination_id,
    )


@router.post("/prompts/{prompt_id}/optimized-copy", response_model=PromptRead)
def save_optimized_prompt_endpoint(
    prompt_id: int,
    payload: PromptOptimizedCopyCreate,
    db: Session = Depends(get_db),
) -> Prompt:
    return save_optimized_prompt(
        db,
        prompt_id,
        name=payload.name,
        system_prompt=payload.system_prompt,
        user_prompt=payload.user_prompt,
        optimization_note=payload.optimization_note,
        version=payload.version,
    )


@router.patch("/prompts/{prompt_id}", response_model=PromptRead)
def update_prompt(prompt_id: int, payload: PromptUpdate, db: Session = Depends(get_db)) -> Prompt:
    item = get_or_404(db, Prompt, prompt_id)
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/prompts/{prompt_id}", response_model=PromptRead)
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)) -> Prompt:
    item = get_or_404(db, Prompt, prompt_id)
    item.is_enabled = False
    db.commit()
    db.refresh(item)
    return item


@router.get("/tasks/{task_id}/models", response_model=list[ModelConfigRead])
def list_models(task_id: int, db: Session = Depends(get_db)) -> list[ModelConfig]:
    return list(
        db.scalars(
            select(ModelConfig)
            .where(ModelConfig.task_id == task_id, ModelConfig.is_enabled.is_(True))
            .order_by(ModelConfig.created_at.desc())
        )
    )


@router.post("/tasks/{task_id}/models", response_model=ModelConfigRead)
def add_model(task_id: int, payload: ModelConfigCreate, db: Session = Depends(get_db)) -> ModelConfig:
    return create_model_config(db, task_id, payload)


@router.patch("/models/{model_id}", response_model=ModelConfigRead)
def update_model(model_id: int, payload: ModelConfigUpdate, db: Session = Depends(get_db)) -> ModelConfig:
    item = get_or_404(db, ModelConfig, model_id)
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/models/{model_id}", response_model=ModelConfigRead)
def delete_model(model_id: int, db: Session = Depends(get_db)) -> ModelConfig:
    item = get_or_404(db, ModelConfig, model_id)
    item.is_enabled = False
    db.commit()
    db.refresh(item)
    return item


@router.get("/tasks/{task_id}/parameters", response_model=list[ParameterConfigRead])
def list_parameters(task_id: int, db: Session = Depends(get_db)) -> list[ParameterConfig]:
    return list(
        db.scalars(
            select(ParameterConfig)
            .where(ParameterConfig.task_id == task_id, ParameterConfig.is_enabled.is_(True))
            .order_by(ParameterConfig.created_at.desc())
        )
    )


@router.post("/tasks/{task_id}/parameters", response_model=ParameterConfigRead)
def add_parameter(task_id: int, payload: ParameterConfigCreate, db: Session = Depends(get_db)) -> ParameterConfig:
    return create_parameter_config(db, task_id, payload)


@router.patch("/parameters/{parameter_id}", response_model=ParameterConfigRead)
def update_parameter(
    parameter_id: int,
    payload: ParameterConfigUpdate,
    db: Session = Depends(get_db),
) -> ParameterConfig:
    item = get_or_404(db, ParameterConfig, parameter_id)
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/parameters/{parameter_id}", response_model=ParameterConfigRead)
def delete_parameter(parameter_id: int, db: Session = Depends(get_db)) -> ParameterConfig:
    item = get_or_404(db, ParameterConfig, parameter_id)
    item.is_enabled = False
    db.commit()
    db.refresh(item)
    return item


@router.get("/tasks/{task_id}/evaluation-targets", response_model=list[EvaluationTargetRead])
def list_targets(task_id: int, db: Session = Depends(get_db)) -> list[EvaluationTarget]:
    return list(
        db.scalars(select(EvaluationTarget).where(EvaluationTarget.task_id == task_id).order_by(EvaluationTarget.created_at))
    )


@router.post("/tasks/{task_id}/evaluation-targets", response_model=EvaluationTargetRead)
def add_target(task_id: int, payload: EvaluationTargetCreate, db: Session = Depends(get_db)) -> EvaluationTarget:
    return create_evaluation_target(db, task_id, payload)


@router.patch("/evaluation-targets/{target_id}", response_model=EvaluationTargetRead)
def update_target(
    target_id: int,
    payload: EvaluationTargetUpdate,
    db: Session = Depends(get_db),
) -> EvaluationTarget:
    item = get_or_404(db, EvaluationTarget, target_id)
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item
