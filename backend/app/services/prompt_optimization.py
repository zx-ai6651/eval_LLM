import asyncio
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agents.prompt_optimization_prompts import (
    DIAGNOSE_SYSTEM_PROMPT,
    OPTIMIZE_SYSTEM_PROMPT,
    PROMPT_OPTIMIZER_AGENT_KEY,
    PROMPT_OPTIMIZER_PROMPT_LOCATION,
)
from app.core.config import get_settings
from app.core.model_adapters import get_agent_model
from app.models.entities import Prompt, PromptOptimization, TestBatch, TestCombination
from app.schemas.dto import (
    PromptCompareRead,
    PromptDiagnosisRead,
    PromptIssue,
    PromptOptimizeRead,
)
from app.services.crud import get_or_404
from app.services.output_contracts import STRUCTURED_OUTPUT_INSTRUCTIONS
from app.tools.model_client import ModelCallResult, ModelClient


async def diagnose_prompt(
    db: Session,
    prompt_id: int,
    batch_id: int | None = None,
    combination_id: int | None = None,
) -> PromptDiagnosisRead:
    prompt = get_or_404(db, Prompt, prompt_id)
    combo = _select_reference_combination(db, prompt_id, batch_id, combination_id)
    output = combo.result.raw_output if combo and combo.result else ""
    issue_summary = combo.evaluation.issue_summary if combo and combo.evaluation else ""
    sources = _safe_json(combo.result.sources_json if combo and combo.result else "[]")
    rule_metrics = _safe_json_object(combo.evaluation.rule_metrics_json if combo and combo.evaluation else "{}")

    agent_model = _prompt_optimizer_model_label()
    payload = _build_prompt_context(prompt, combo, output, issue_summary, sources)
    model_result, agent_error = await _call_prompt_optimizer_agent(DIAGNOSE_SYSTEM_PROMPT, payload)
    parsed = _parse_json_object(model_result.output) if model_result.success else None
    if parsed:
        issues = _issues_from_payload(parsed.get("issues", []))
        directions = _string_list(parsed.get("optimization_directions")) or _directions_from_issues(issues)
        summary = str(parsed.get("summary") or ("发现 Prompt 存在可优化空间。" if issues else "未发现明显 Prompt 问题。"))
        agent_name = PROMPT_OPTIMIZER_AGENT_KEY
    else:
        issues = _infer_prompt_issues(prompt, output, issue_summary, sources, rule_metrics)
        directions = _directions_from_issues(issues)
        summary = (
            f"Prompt 诊断 Agent 未完成：{agent_error}，已使用规则诊断。"
            if agent_error
            else ("发现 Prompt 存在可优化空间。" if issues else "未发现明显 Prompt 问题，可保留当前版本继续测试。")
        )
        agent_name = "rule_fallback"
        agent_model = "rule_fallback"

    return PromptDiagnosisRead(
        prompt_id=prompt.id,
        batch_id=batch_id or (combo.batch_id if combo else None),
        combination_id=combination_id or (combo.id if combo else None),
        summary=summary,
        issues=issues,
        optimization_directions=directions,
        agent_name=agent_name,
        agent_model=agent_model,
        prompt_location=PROMPT_OPTIMIZER_PROMPT_LOCATION,
    )


async def optimize_prompt(
    db: Session,
    prompt_id: int,
    diagnosis: PromptDiagnosisRead | None = None,
    optimization_goal: str = "",
    batch_id: int | None = None,
    combination_id: int | None = None,
) -> PromptOptimizeRead:
    prompt = get_or_404(db, Prompt, prompt_id)
    diagnosis = diagnosis or await diagnose_prompt(db, prompt_id, batch_id, combination_id)
    goal = optimization_goal.strip() or "提升联网搜索结果的真实性、来源支撑和可复测性"
    combo = _select_reference_combination(db, prompt_id, batch_id, combination_id)
    output = combo.result.raw_output if combo and combo.result else ""
    issue_summary = combo.evaluation.issue_summary if combo and combo.evaluation else ""
    sources = _safe_json(combo.result.sources_json if combo and combo.result else "[]")
    payload = _build_prompt_context(prompt, combo, output, issue_summary, sources, diagnosis, goal)
    agent_model = _prompt_optimizer_model_label()
    model_result, agent_error = await _call_prompt_optimizer_agent(OPTIMIZE_SYSTEM_PROMPT, payload)
    parsed = _parse_json_object(model_result.output) if model_result.success else None
    if parsed and parsed.get("optimized_system_prompt"):
        optimized_system = str(parsed.get("optimized_system_prompt") or "").strip()
        optimized_user = str(parsed.get("optimized_user_prompt") or prompt.user_prompt or "")
        solved = _string_list(parsed.get("solved_issues")) or [issue.type for issue in diagnosis.issues]
        change_summary = str(parsed.get("change_summary") or _change_summary(diagnosis))
        side_effects = _string_list(parsed.get("possible_side_effects")) or [
            "Prompt 约束增加后，模型输出可能更保守。"
        ]
        recommendation = str(parsed.get("recommendation") or "建议保存为新 Prompt，并创建新批次复测。")
        agent_name = PROMPT_OPTIMIZER_AGENT_KEY
    else:
        optimized_system = _build_optimized_system_prompt(prompt.system_prompt or prompt.content, diagnosis)
        optimized_user = prompt.user_prompt or ""
        solved = [issue.type for issue in diagnosis.issues]
        change_summary = _change_summary(diagnosis)
        side_effects = [
            "Prompt 约束增加后，模型输出可能更保守。",
            "来源和时间线要求更严格时，部分无法确认的信息会被明确标记而不是强行总结。",
        ]
        recommendation = "建议保存为新 Prompt，并复用第一阶段批次流程进行复测。"
        if agent_error:
            recommendation = f"Prompt 优化 Agent 未完成：{agent_error}，已生成规则兜底优化稿；建议人工审核后再保存。"
        agent_name = "rule_fallback"
        agent_model = "rule_fallback"

    return PromptOptimizeRead(
        prompt_id=prompt.id,
        optimized_system_prompt=optimized_system,
        optimized_user_prompt=optimized_user,
        optimization_goal=goal,
        change_summary=change_summary,
        solved_issues=solved,
        possible_side_effects=side_effects,
        recommend_retest=True,
        recommendation=recommendation,
        diagnosis=diagnosis,
        agent_name=agent_name,
        agent_model=agent_model,
        prompt_location=PROMPT_OPTIMIZER_PROMPT_LOCATION,
    )


def save_optimized_prompt(
    db: Session,
    prompt_id: int,
    name: str,
    system_prompt: str,
    user_prompt: str,
    optimization_note: str,
    version: str,
) -> Prompt:
    original = get_or_404(db, Prompt, prompt_id)
    optimized = Prompt(
        task_id=original.task_id,
        name=name,
        content=system_prompt,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        version=version,
        is_enabled=True,
        is_default=False,
        parent_prompt_id=original.id,
        source_type="optimized",
        optimization_note=optimization_note,
    )
    db.add(optimized)
    db.flush()
    db.add(
        PromptOptimization(
            task_id=original.task_id,
            original_prompt_id=original.id,
            optimized_prompt_id=optimized.id,
            diagnosis_json="{}",
            optimized_system_prompt=system_prompt,
            optimized_user_prompt=user_prompt,
            optimization_note=optimization_note,
            recommendation="已保存为新 Prompt，建议创建新批次复测。",
        )
    )
    db.commit()
    db.refresh(optimized)
    return optimized


def compare_prompts(
    db: Session,
    original_prompt_id: int,
    optimized_prompt_id: int,
    original_batch_id: int | None = None,
    optimized_batch_id: int | None = None,
) -> PromptCompareRead:
    original_combo = _select_reference_combination(db, original_prompt_id, original_batch_id, None)
    optimized_combo = _select_reference_combination(db, optimized_prompt_id, optimized_batch_id, None)
    original_eval = original_combo.evaluation if original_combo else None
    optimized_eval = optimized_combo.evaluation if optimized_combo else None

    if not original_eval or not optimized_eval:
        return PromptCompareRead(
            original_prompt_id=original_prompt_id,
            optimized_prompt_id=optimized_prompt_id,
            original_batch_id=original_batch_id,
            optimized_batch_id=optimized_batch_id,
            original_score=original_eval.total_score if original_eval else None,
            optimized_score=optimized_eval.total_score if optimized_eval else None,
            recommendation="需要完成原 Prompt 和优化 Prompt 的测试后才能对比。",
        )

    total_delta = round(optimized_eval.total_score - original_eval.total_score, 2)
    truth_delta = round(optimized_eval.truthfulness_score - original_eval.truthfulness_score, 2)
    source_delta = round(optimized_eval.source_quality_score - original_eval.source_quality_score, 2)
    completeness_delta = round(optimized_eval.completeness_score - original_eval.completeness_score, 2)
    cost_delta = round((optimized_combo.cost or 0) - (original_combo.cost or 0), 6)

    recommendation = "无明显提升。"
    if total_delta >= 3 and truth_delta >= 0 and source_delta >= 0:
        recommendation = "建议采用优化 Prompt。"
    elif total_delta > 0:
        recommendation = "有提升，但建议继续观察。"
    elif total_delta < 0:
        recommendation = "出现退化，不建议采用。"

    return PromptCompareRead(
        original_prompt_id=original_prompt_id,
        optimized_prompt_id=optimized_prompt_id,
        original_batch_id=original_batch_id or (original_combo.batch_id if original_combo else None),
        optimized_batch_id=optimized_batch_id or (optimized_combo.batch_id if optimized_combo else None),
        original_score=original_eval.total_score,
        optimized_score=optimized_eval.total_score,
        total_delta=total_delta,
        truthfulness_delta=truth_delta,
        source_quality_delta=source_delta,
        completeness_delta=completeness_delta,
        original_risk_level=original_eval.risk_level,
        optimized_risk_level=optimized_eval.risk_level,
        cost_delta=cost_delta,
        recommendation=recommendation,
    )


def _prompt_optimizer_model_label() -> str:
    agent_model = get_agent_model(PROMPT_OPTIMIZER_AGENT_KEY)
    return f"{agent_model.provider}/{agent_model.model}"


async def _call_prompt_optimizer_agent(system_prompt: str, payload: str) -> tuple[ModelCallResult, str]:
    timeout_seconds = get_settings().prompt_optimizer_timeout_seconds
    try:
        result = await asyncio.wait_for(
            ModelClient().complete_for_agent(
                PROMPT_OPTIMIZER_AGENT_KEY,
                system_prompt,
                payload,
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        message = f"调用超时（{timeout_seconds}s）"
        return ModelCallResult(False, "", timeout_seconds * 1000, error_message=message), message
    except Exception as exc:
        message = f"{exc.__class__.__name__}: {exc}" if str(exc) else exc.__class__.__name__
        return ModelCallResult(False, "", 0, error_message=message), message
    if result.success:
        return result, ""
    return result, result.error_message or "模型未返回有效内容"


def _build_prompt_context(
    prompt: Prompt,
    combo: TestCombination | None,
    output: str,
    issue_summary: str,
    sources: list,
    diagnosis: PromptDiagnosisRead | None = None,
    optimization_goal: str = "",
) -> str:
    evaluation = combo.evaluation if combo and combo.evaluation else None
    search_logs = _safe_json(combo.result.search_logs_json if combo and combo.result else "[]")
    context = {
        "task": {
            "name": combo.batch.task.name if combo and combo.batch and combo.batch.task else "",
            "description": combo.batch.task.description if combo and combo.batch and combo.batch.task else "",
            "background": combo.batch.task.background if combo and combo.batch and combo.batch.task else "",
            "focus_points": combo.batch.task.focus_points if combo and combo.batch and combo.batch.task else "",
        },
        "prompt": {
            "id": prompt.id,
            "name": prompt.name,
            "version": prompt.version,
            "system_prompt": prompt.system_prompt or prompt.content,
            "user_prompt": prompt.user_prompt,
        },
        "latest_test": {
            "batch_id": combo.batch_id if combo else None,
            "combination_id": combo.id if combo else None,
            "model": combo.model_config.name if combo and combo.model_config else "",
            "parameter": combo.parameter_config.name if combo and combo.parameter_config else "",
            "output": output[:6000],
            "issue_summary": issue_summary,
            "sources": sources[:20],
            "search_logs": search_logs[:20],
        },
        "evaluation": {
            "total_score": evaluation.total_score if evaluation else None,
            "truthfulness_score": evaluation.truthfulness_score if evaluation else None,
            "source_quality_score": evaluation.source_quality_score if evaluation else None,
            "risk_level": evaluation.risk_level if evaluation else None,
            "rationale": evaluation.rationale if evaluation else "",
            "rule_metrics": _safe_json_object(evaluation.rule_metrics_json if evaluation else "{}"),
        },
        "diagnosis": diagnosis.model_dump() if diagnosis else None,
        "optimization_goal": optimization_goal,
    }
    return json.dumps(context, ensure_ascii=False, indent=2)


def _parse_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    candidates = [text.strip()]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates.extend(item.strip() for item in fenced)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _issues_from_payload(items: Any) -> list[PromptIssue]:
    if not isinstance(items, list):
        return []
    issues: list[PromptIssue] = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "medium").lower()
        if severity not in {"high", "medium", "low"}:
            severity = "medium"
        issues.append(
            PromptIssue(
                type=str(item.get("type") or "未命名问题"),
                severity=severity,
                evidence=str(item.get("evidence") or ""),
                impact=str(item.get("impact") or ""),
                suggestion=str(item.get("suggestion") or ""),
            )
        )
    return issues


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _select_reference_combination(
    db: Session,
    prompt_id: int,
    batch_id: int | None,
    combination_id: int | None,
) -> TestCombination | None:
    if combination_id:
        stmt = _combo_stmt().where(TestCombination.id == combination_id, TestCombination.prompt_id == prompt_id)
        return db.scalar(stmt)

    stmt = _combo_stmt().where(TestCombination.prompt_id == prompt_id)
    if batch_id:
        stmt = stmt.where(TestCombination.batch_id == batch_id)
    stmt = stmt.order_by(TestCombination.id.desc())
    return db.scalar(stmt)


def _combo_stmt():
    return select(TestCombination).options(
        selectinload(TestCombination.batch).selectinload(TestBatch.task),
        selectinload(TestCombination.prompt),
        selectinload(TestCombination.result),
        selectinload(TestCombination.evaluation),
    )


def _infer_prompt_issues(
    prompt: Prompt,
    output: str,
    issue_summary: str,
    sources: list,
    rule_metrics_payload: dict | None = None,
) -> list[PromptIssue]:
    text = "\n".join([prompt.system_prompt or prompt.content, prompt.user_prompt or ""]).lower()
    evidence_text = "\n".join([output, issue_summary]).lower()
    rule_metrics_payload = rule_metrics_payload or {}
    metrics = rule_metrics_payload.get("metrics") if isinstance(rule_metrics_payload.get("metrics"), dict) else {}
    failure_types = set(rule_metrics_payload.get("failure_types") or [])
    issues: list[PromptIssue] = []

    if metrics.get("search_failure_count"):
        issues.append(
            PromptIssue(
                type="搜索策略或搜索供应商问题",
                severity="high",
                evidence=f"规则指标显示 search_failure_count={metrics.get('search_failure_count')}，该问题不应直接归因到 Prompt。",
                impact="搜索证据不足会导致来源覆盖和真实性评分下降。",
                suggestion="优先检查搜索 API、搜索策略和 query 规划；Prompt 只需保留无法确认时的输出规则。",
            )
        )
    if "model_output_failure" in failure_types:
        issues.append(
            PromptIssue(
                type="模型调用或输出失败",
                severity="high",
                evidence="规则评估标记 model_output_failure。",
                impact="当前结果不能证明 Prompt 本身失败。",
                suggestion="优先检查模型 API Key、超时、max_tokens 和供应商配置；暂不应只改 Prompt。",
            )
        )
    if "missing_required_structure" in failure_types and not all(
        keyword in text for keyword in ["claims", "sources", "unverified_items", "search_queries_used"]
    ):
        issues.append(
            PromptIssue(
                type="结构化输出协议缺失",
                severity="high",
                evidence="规则评估标记 missing_required_structure，且 Prompt 未完整声明标准 JSON 字段。",
                impact="评估器无法稳定解析 claims 与 sources，后续优化缺少可复核证据。",
                suggestion="在 Prompt 中强制输出标准 JSON：summary、claims、sources、risk_notes、unverified_items、search_queries_used。",
            )
        )
    if metrics.get("unsupported_fact_claim_count"):
        issues.append(
            PromptIssue(
                type="事实结论未绑定来源",
                severity="high",
                evidence=f"规则指标显示 unsupported_fact_claim_count={metrics.get('unsupported_fact_claim_count')}。",
                impact="事实结论无法追溯来源，真实性评分会被封顶。",
                suggestion="要求 claim_type=fact 的每条 claims 必须绑定 source_ids，无法绑定时改为 unknown 并写入 unverified_items。",
            )
        )

    if not any(word in text for word in ["来源", "引用", "链接", "source", "citation"]):
        issues.append(
            PromptIssue(
                type="来源引用要求不足",
                severity="high",
                evidence="Prompt 中缺少明确的来源引用要求。",
                impact="模型可能输出没有来源支撑的关键结论。",
                suggestion="要求每个关键结论必须绑定来源链接或明确标记无法确认。",
            )
        )
    if not any(word in text for word in ["无法确认", "待核验", "不确定", "未确认"]):
        issues.append(
            PromptIssue(
                type="无法确认时的处理规则不足",
                severity="medium",
                evidence="Prompt 没有规定信息不足时如何回答。",
                impact="模型可能为了完成任务而补全事实。",
                suggestion="要求来源不足时必须写明无法确认，并列出待核验问题。",
            )
        )
    if not any(word in text for word in ["时间", "日期", "当前", "最新", "发布"]):
        issues.append(
            PromptIssue(
                type="时间线约束不足",
                severity="medium",
                evidence="Prompt 缺少发布时间、当前状态和历史事件的区分要求。",
                impact="模型可能把旧信息写成最新状态，或把计划写成事实。",
                suggestion="要求标注信息发布时间，并区分历史、当前状态和未来计划。",
            )
        )
    if not any(word in text for word in ["事实", "推测", "判断"]):
        issues.append(
            PromptIssue(
                type="真实性约束不足",
                severity="high",
                evidence="Prompt 没有明确要求区分事实、推测和判断。",
                impact="输出中的推断可能被误读为事实。",
                suggestion="要求分栏输出已确认事实、合理推测和无法确认内容。",
            )
        )
    if not any(word in text for word in ["结构", "摘要", "列表", "表格", "json", "claims", "sources"]):
        issues.append(
            PromptIssue(
                type="输出结构不清晰",
                severity="low",
                evidence="Prompt 对输出结构约束较弱。",
                impact="结果不利于后续评估、对比和复用。",
                suggestion="固定输出结构，例如摘要、已确认事实、来源列表、风险提示、待核验问题。",
            )
        )
    if "记忆" not in text and ("mock_model_output" in evidence_text or not sources):
        issues.append(
            PromptIssue(
                type="过度依赖模型记忆",
                severity="medium",
                evidence="当前测试结果缺少可用来源，Prompt 也未明确禁止模型记忆补全。",
                impact="模型可能基于训练记忆生成无法核验的信息。",
                suggestion="要求只基于搜索结果回答，禁止用模型记忆补全事实。",
            )
        )

    return issues[:6]


def _directions_from_issues(issues: list[PromptIssue]) -> list[str]:
    if not issues:
        return ["保留当前 Prompt，必要时仅微调输出结构。"]
    return [issue.suggestion for issue in issues]


def _build_optimized_system_prompt(original: str, diagnosis: PromptDiagnosisRead) -> str:
    base = original.strip() or "你是一个联网搜索型信息核验 Agent。"
    additions = [
        "请严格只基于搜索结果和可验证来源回答，不要使用模型记忆补全事实。",
        "请区分 fact、inference、unknown，不要把预测或计划写成已经发生的事实。",
        "涉及“最新、近期、当前状态”等表述时，必须核对并标注信息发布时间。",
        STRUCTURED_OUTPUT_INSTRUCTIONS,
    ]
    return "\n\n".join(
        [
            base,
            "## 优化补充约束",
            "\n".join(f"{index + 1}. {item}" for index, item in enumerate(additions)),
        ]
    )


def _change_summary(diagnosis: PromptDiagnosisRead) -> str:
    if not diagnosis.issues:
        return "保留原 Prompt 主体，仅补充更明确的来源、时间线和无法确认处理规则。"
    issue_names = "、".join(issue.type for issue in diagnosis.issues)
    return f"针对 {issue_names} 补充约束，强化来源支撑、事实边界和输出结构。"


def _safe_json(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _safe_json_object(value: str) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}
