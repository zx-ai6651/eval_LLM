import asyncio
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.model_adapters import provider_uses_builtin_search
from app.models.entities import (
    EvaluationResult,
    ModelConfig,
    ParameterConfig,
    Prompt,
    Report,
    TestBatch,
    TestCombination,
    TestResult,
    TestTask,
)
from app.schemas.dto import BatchCreate
from app.services.crud import get_or_404
from app.services.evaluator import evaluate_result
from app.services.recommendation import recommendation_sort_key
from app.services.reporting import upsert_report
from app.services.search_planning import build_search_plan
from app.services.source_normalization import normalize_sources
from app.tools.model_client import ModelClient
from app.tools.search_client import SearchClient


def _load_batch(db: Session, batch_id: int) -> TestBatch:
    stmt = (
        select(TestBatch)
        .where(TestBatch.id == batch_id)
        .options(
            selectinload(TestBatch.task).selectinload(TestTask.evaluation_targets),
            selectinload(TestBatch.combinations).selectinload(TestCombination.prompt),
            selectinload(TestBatch.combinations).selectinload(TestCombination.model_config),
            selectinload(TestBatch.combinations).selectinload(TestCombination.parameter_config),
            selectinload(TestBatch.combinations).selectinload(TestCombination.result),
            selectinload(TestBatch.combinations).selectinload(TestCombination.evaluation),
            selectinload(TestBatch.reports),
        )
    )
    batch = db.scalar(stmt)
    if batch is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="TestBatch not found")
    return batch


def create_batch_with_combinations(db: Session, task_id: int, payload: BatchCreate) -> TestBatch:
    settings = get_settings()
    task = get_or_404(db, TestTask, task_id)
    prompt_stmt = select(Prompt).where(Prompt.task_id == task_id, Prompt.is_enabled.is_(True))
    if payload.prompt_ids is not None:
        if not payload.prompt_ids:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="prompt_ids 不能为空；如需测试全部 Prompt，请不要传 prompt_ids。")
        prompt_stmt = prompt_stmt.where(Prompt.id.in_(payload.prompt_ids))
    prompts = list(db.scalars(prompt_stmt))
    if payload.prompt_ids is not None and len(prompts) != len(set(payload.prompt_ids)):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="选择的 Prompt 不存在、未启用或不属于当前任务。")
    models = list(db.scalars(select(ModelConfig).where(ModelConfig.task_id == task_id, ModelConfig.is_enabled.is_(True))))
    params = list(
        db.scalars(select(ParameterConfig).where(ParameterConfig.task_id == task_id, ParameterConfig.is_enabled.is_(True)))
    )
    if not prompts or not models or not params:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="需要至少启用 1 个 Prompt、1 个模型和 1 组参数")

    estimated = len(prompts) * len(models) * len(params)
    if estimated > settings.max_test_combinations:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=f"测试组合数量 {estimated} 超过上限 {settings.max_test_combinations}")

    batch = TestBatch(task_id=task_id, name=payload.name, status="pending")
    task.status = "configured"
    db.add(batch)
    db.flush()
    for prompt in prompts:
        for model in models:
            for param in params:
                db.add(
                    TestCombination(
                        batch_id=batch.id,
                        prompt_id=prompt.id,
                        model_config_id=model.id,
                        parameter_config_id=param.id,
                    )
                )
    db.commit()
    return _load_batch(db, batch.id)


async def run_batch(db: Session, batch_id: int) -> TestBatch:
    batch = _load_batch(db, batch_id)
    settings = get_settings()
    batch.status = "running"
    batch.task.status = "running"
    batch.started_at = datetime.utcnow()
    batch.failure_reason = ""
    db.commit()

    model_client = ModelClient()
    batch_started = datetime.utcnow()
    total_cost = 0.0

    for combination in batch.combinations:
        combination_id = combination.id
        combination.status = "running"
        combination.started_at = datetime.utcnow()
        db.commit()
        combo_started = datetime.utcnow()
        try:
            search_plan = build_search_plan(batch.task)
            sources, search_logs, search_duration_ms = await _prepare_search_context(combination, search_plan)
            task_payload = _build_task_payload(batch.task, sources, search_plan, combination.prompt.user_prompt)
            model_result = await asyncio.wait_for(
                model_client.complete(
                    combination.model_config,
                    combination.parameter_config,
                    combination.prompt.system_prompt or combination.prompt.content,
                    task_payload,
                ),
                timeout=settings.model_call_timeout_seconds,
            )
            if model_result.sources:
                sources = normalize_sources([*sources, *model_result.sources], default_source=combination.model_config.provider)
            if model_result.search_logs:
                search_logs.extend(model_result.search_logs)
            if model_result.cost_breakdown:
                search_logs.append(
                    {
                        "mode": "cost_breakdown",
                        "provider": combination.model_config.provider,
                        "model": combination.model_config.name,
                        "cost": model_result.cost_breakdown,
                    }
                )

            combination.duration_ms = model_result.duration_ms + search_duration_ms
            combination.cost = model_result.estimated_cost
            total_cost += combination.cost
            combination.status = "completed" if model_result.success else "failed"
            combination.ended_at = datetime.utcnow()

            result = _upsert_test_result(
                db,
                combination.id,
                raw_output=model_result.output,
                structured_output=model_result.output,
                sources=sources,
                search_logs=search_logs,
                error_message=model_result.error_message,
            )
            db.commit()

            if combination.parameter_config.enable_evaluator:
                try:
                    scores = await asyncio.wait_for(
                        evaluate_result(result, combination, combination.cost),
                        timeout=settings.evaluator_call_timeout_seconds * 2 + 30,
                    )
                except Exception as eval_exc:
                    scores = _evaluation_failure_scores(eval_exc)
                _upsert_evaluation_result(db, combination.id, scores)
        except Exception as exc:
            db.rollback()
            combination = db.get(TestCombination, combination_id)
            if combination is None:
                raise
            combination.status = "failed"
            combination.ended_at = datetime.utcnow()
            combination.duration_ms = int((datetime.utcnow() - combo_started).total_seconds() * 1000)
            _upsert_test_result(db, combination.id, error_message=_format_exception("组合执行异常", exc))
        db.commit()

    batch = _load_batch(db, batch_id)
    _mark_recommendations(batch)
    batch.ended_at = datetime.utcnow()
    batch.duration_ms = int((batch.ended_at - batch_started).total_seconds() * 1000)
    batch.total_cost = total_cost

    failed_count = sum(1 for combo in batch.combinations if combo.status == "failed")
    if failed_count == len(batch.combinations):
        batch.status = "failed"
        batch.task.status = "failed"
        batch.failure_reason = "所有测试组合均执行失败"
    else:
        batch.status = "completed"
        batch.task.status = "completed"
        if failed_count:
            batch.failure_reason = f"{failed_count} 个测试组合执行失败，其余组合已完成"

    report = upsert_report(batch)
    if report.id is None:
        db.add(report)
    db.commit()
    return _load_batch(db, batch_id)


def recover_interrupted_batches(db: Session) -> int:
    stmt = (
        select(TestBatch)
        .where(TestBatch.status.in_(("queued", "running")))
        .options(
            selectinload(TestBatch.task),
            selectinload(TestBatch.combinations).selectinload(TestCombination.result),
        )
    )
    batches = list(db.scalars(stmt))
    if not batches:
        return 0
    now = datetime.utcnow()
    message = "服务重启或后台任务中断，上一轮运行未正常结束，请重新创建批次运行。"
    for batch in batches:
        batch.status = "failed"
        batch.failure_reason = message
        batch.ended_at = now
        if batch.started_at:
            batch.duration_ms = int((now - batch.started_at).total_seconds() * 1000)
        if batch.task:
            batch.task.status = "failed"
        for combination in batch.combinations:
            if combination.status in {"pending", "queued", "running"}:
                combination.status = "failed"
                combination.ended_at = now
                if combination.started_at:
                    combination.duration_ms = int((now - combination.started_at).total_seconds() * 1000)
                _upsert_test_result(db, combination.id, error_message=message)
    db.commit()
    return len(batches)


def get_batch_detail(db: Session, batch_id: int) -> TestBatch:
    return _load_batch(db, batch_id)


def delete_batch(db: Session, batch_id: int) -> None:
    batch = _load_batch(db, batch_id)
    if batch.status in {"running", "queued"}:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="运行中或排队中的批次不能删除")
    db.delete(batch)
    db.commit()


def get_latest_report(db: Session, batch_id: int) -> Report | None:
    batch = _load_batch(db, batch_id)
    return batch.reports[0] if batch.reports else None


def _upsert_test_result(
    db: Session,
    combination_id: int,
    raw_output: str = "",
    structured_output: str = "",
    sources: list[dict] | None = None,
    search_logs: list[dict] | None = None,
    error_message: str = "",
) -> TestResult:
    result = db.scalar(select(TestResult).where(TestResult.combination_id == combination_id))
    if result is not None and not raw_output and not structured_output and sources is None and search_logs is None:
        if error_message:
            result.error_message = error_message
        db.flush()
        return result
    payload = {
        "raw_output": raw_output,
        "structured_output": structured_output,
        "sources_json": json.dumps(sources or [], ensure_ascii=False),
        "search_logs_json": json.dumps(search_logs or [], ensure_ascii=False),
        "error_message": error_message,
    }
    if result is None:
        result = TestResult(combination_id=combination_id, **payload)
        db.add(result)
    else:
        for key, value in payload.items():
            setattr(result, key, value)
    db.flush()
    return result


def _upsert_evaluation_result(db: Session, combination_id: int, scores: dict) -> EvaluationResult:
    evaluation = db.scalar(select(EvaluationResult).where(EvaluationResult.combination_id == combination_id))
    if evaluation is None:
        evaluation = EvaluationResult(combination_id=combination_id, **scores)
        db.add(evaluation)
    else:
        for key, value in scores.items():
            setattr(evaluation, key, value)
        evaluation.is_recommended = False
    db.flush()
    return evaluation


def _format_exception(prefix: str, exc: Exception) -> str:
    text = str(exc)
    detail = f"{exc.__class__.__name__}: {text}" if text else exc.__class__.__name__
    return f"{prefix}：{detail}"


def _evaluation_failure_scores(exc: Exception) -> dict:
    return {
        "total_score": 0,
        "truthfulness_score": 0,
        "completeness_score": 0,
        "source_quality_score": 0,
        "stability_score": 0,
        "structure_score": 0,
        "cost_efficiency_score": 0,
        "issue_summary": f"- 评分 Agent 执行失败：{_format_exception('评估异常', exc)}。该分数只表示评分失败，不代表模型输出质量。",
        "rationale": "evaluation_failure; scorer did not complete successfully.",
        "rule_metrics_json": "{}",
        "risk_level": "medium",
    }


async def _prepare_search_context(
    combination: TestCombination,
    search_plan: dict,
) -> tuple[list[dict], list[dict], int]:
    settings = get_settings()
    search_provider = settings.search_provider.lower()
    provider_name = combination.model_config.provider
    queries = search_plan.get("queries") or []
    if not queries:
        queries = [{"query": f"{combination.batch.task.name} {combination.batch.task.focus_points}".strip(), "intent": "basic_info", "priority": "high"}]

    if search_provider in {"tavily", "serper"} and not provider_uses_builtin_search(provider_name):
        search_client = SearchClient()
        all_sources: list[dict] = []
        logs: list[dict] = []
        total_duration_ms = 0
        per_query_limit = max(1, min(combination.parameter_config.search_limit, 5))
        for item in queries:
            query = item.get("query", "")
            search_result = await search_client.search(query, per_query_limit)
            query_sources = [source.__dict__ for source in search_result.items]
            all_sources.extend(query_sources)
            total_duration_ms += search_result.duration_ms
            logs.append(
                {
                    "query": query,
                    "intent": item.get("intent", ""),
                    "priority": item.get("priority", ""),
                    "provider": query_sources[0]["source"] if query_sources else search_provider,
                    "mode": "external_search",
                    "success": search_result.success,
                    "duration_ms": search_result.duration_ms,
                    "result_count": len(query_sources),
                    "error_message": search_result.error_message,
                }
            )
        sources = normalize_sources(all_sources, default_source=search_provider)
        return (
            sources,
            logs,
            total_duration_ms,
        )

    if provider_uses_builtin_search(provider_name):
        logs = [
            {
                "query": item.get("query", ""),
                "intent": item.get("intent", ""),
                "priority": item.get("priority", ""),
                "provider": provider_name,
                "mode": "builtin_search_planned_query",
                "search_strategy": combination.parameter_config.search_strategy,
                "success": True,
            }
            for item in queries
        ]
        logs.append(
            {
                "mode": "builtin_search_without_auditable_sources",
                "warning": "model output may include citations, but structured source extraction is incomplete",
            }
        )
        return (
            [],
            logs,
            0,
        )

    return (
        [],
        [
            {
                "queries": queries,
                "provider": provider_name,
                "mode": "no_search_provider_configured",
                "success": False,
                "error_message": "当前模型供应商未启用内置搜索，且未配置 Tavily / Serper 外部搜索。",
            }
        ],
        0,
    )


def _build_task_payload(task: TestTask, sources: list[dict], search_plan: dict, user_prompt: str = "") -> str:
    if sources:
        source_block = json.dumps(sources, ensure_ascii=False, indent=2)
    else:
        source_block = "本轮使用模型供应商内置联网搜索工具，请在输出中保留搜索来源、引用标记和无法确认项。"
    lines = [
        f"任务名称：{task.name}",
        f"任务描述：{task.description}",
        f"任务背景：{task.background}",
        f"关注点：{task.focus_points}",
        "搜索计划：",
        json.dumps(search_plan, ensure_ascii=False, indent=2),
    ]
    if user_prompt.strip():
        lines.extend(["用户 Prompt：", user_prompt.strip()])
    lines.extend(
        [
            "搜索来源：",
            source_block,
            "请完成联网搜索型 Agent 测试输出，关键结论必须有来源支撑；无法确认时必须明确说明。",
            "输出必须符合联网搜索标准 JSON 协议，包含 summary、claims、sources、risk_notes、unverified_items、search_queries_used。",
        ]
    )
    return "\n".join(lines)


def _mark_recommendations(batch: TestBatch) -> None:
    evaluated = [combo for combo in batch.combinations if combo.evaluation]
    if not evaluated:
        return
    ranked = sorted(
        evaluated,
        key=recommendation_sort_key,
        reverse=True,
    )
    for combo in evaluated:
        combo.evaluation.is_recommended = combo.id == ranked[0].id


def progress_for_batch(batch: TestBatch) -> dict[str, int]:
    statuses = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
    for combo in batch.combinations:
        statuses[combo.status] = statuses.get(combo.status, 0) + 1
    statuses["total"] = len(batch.combinations)
    return statuses
