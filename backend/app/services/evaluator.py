import asyncio
import json
import re
from typing import Any

from app.agents.evaluation_prompts import EVALUATOR_AGENT_KEY, EVALUATOR_PROMPT_LOCATION, EVALUATOR_SYSTEM_PROMPT
from app.core.config import get_settings
from app.core.model_adapters import get_agent_model
from app.models.entities import TestCombination, TestResult
from app.services.evaluation_rules import apply_rule_caps, evaluate_output_rules, rule_metrics_json
from app.tools.model_client import ModelClient


async def evaluate_result(result: TestResult, combination: TestCombination, cost: float) -> dict:
    rule_report = evaluate_output_rules(result, combination)
    payload = _build_evaluation_payload(result, combination, cost, rule_report)
    verification_strategy = _evaluator_search_strategy(combination)
    timeout_seconds = get_settings().evaluator_call_timeout_seconds
    model_result = None
    parsed = None
    fallback_reason = ""
    for attempt in range(1, 3):
        system_prompt = EVALUATOR_SYSTEM_PROMPT
        if attempt > 1:
            system_prompt = (
                EVALUATOR_SYSTEM_PROMPT
                + "\n\n重要：上一次输出未能解析为严格 JSON。本次只能输出一个 JSON 对象，不要解释、不要 Markdown。"
            )
        try:
            model_result = await asyncio.wait_for(
                ModelClient().complete_for_agent(
                    EVALUATOR_AGENT_KEY,
                    system_prompt,
                    payload,
                    enable_builtin_search=True,
                    search_strategy=verification_strategy,
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            fallback_reason = f"LLM 评估 Agent 调用超时（{timeout_seconds}s），已使用规则兜底评分。"
            break
        except Exception as exc:
            fallback_reason = f"LLM 评估 Agent 调用异常：{exc.__class__.__name__}: {exc}"
            break
        parsed = _parse_json_object(model_result.output) if model_result.success else None
        if parsed:
            return _normalize_scores(
                parsed,
                result,
                combination,
                cost,
                rule_report,
                used_agent=True,
                verification_search_strategy=verification_strategy,
            )
    if fallback_reason:
        return _rule_fallback_scores(result, combination, cost, rule_report, fallback_reason)
    if model_result and model_result.success:
        fallback_reason = f"LLM 评估 Agent 返回内容不是有效 JSON：{model_result.output[:500]}"
    else:
        fallback_reason = f"LLM 评估 Agent 调用失败：{model_result.error_message if model_result else 'no response'}"
    return _rule_fallback_scores(result, combination, cost, rule_report, fallback_reason)


def _build_evaluation_payload(result: TestResult, combination: TestCombination, cost: float, rule_report: dict) -> str:
    task = combination.batch.task if combination.batch else None
    parameter = combination.parameter_config
    targets = []
    if task:
        targets = [
            {
                "name": target.name,
                "description": target.description,
                "weight": target.weight,
            }
            for target in task.evaluation_targets
            if target.is_enabled
        ]
    payload = {
        "task": {
            "name": task.name if task else "",
            "description": task.description if task else "",
            "background": task.background if task else "",
            "focus_points": task.focus_points if task else "",
            "evaluation_targets": targets,
        },
        "prompt": {
            "name": combination.prompt.name if combination.prompt else "",
            "system_prompt": combination.prompt.system_prompt if combination.prompt else "",
            "user_prompt": combination.prompt.user_prompt if combination.prompt else "",
        },
        "model": {
            "provider": combination.model_config.provider if combination.model_config else "",
            "name": combination.model_config.name if combination.model_config else "",
        },
        "parameter": {
            "name": parameter.name,
            "temperature": parameter.temperature,
            "top_p": parameter.top_p,
            "search_strategy": parameter.search_strategy,
            "force_citations": parameter.force_citations,
            "require_structured_output": parameter.require_structured_output,
            "allow_model_memory": parameter.allow_model_memory,
            "enable_secondary_verification": parameter.enable_secondary_verification,
        },
        "evaluator": {
            "verification_search_requested": True,
            "verification_search_strategy": _evaluator_search_strategy(combination),
            "prompt_location": EVALUATOR_PROMPT_LOCATION,
            "rule_metrics": rule_report.get("metrics") or {},
            "rule_failure_types": rule_report.get("failure_types") or [],
            "hard_caps": {
                "total_score": rule_report.get("cap_total"),
                "score_caps": rule_report.get("score_caps") or {},
            },
        },
        "result": {
            "raw_output": (result.raw_output or "")[:8000],
            "error_message": result.error_message,
            "sources": _safe_json(result.sources_json)[:30],
            "search_logs": _safe_json(result.search_logs_json)[:30],
            "structured_output": rule_report.get("structured_output"),
        },
        "cost": cost,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_scores(
    payload: dict[str, Any],
    result: TestResult,
    combination: TestCombination,
    cost: float,
    rule_report: dict,
    used_agent: bool,
    verification_search_strategy: str = "off",
) -> dict:
    scores = {
        "truthfulness_score": _clamp(payload.get("truthfulness_score"), 0, 50),
        "completeness_score": _clamp(payload.get("completeness_score"), 0, 20),
        "source_quality_score": _clamp(payload.get("source_quality_score"), 0, 10),
        "stability_score": _clamp(payload.get("stability_score"), 0, 10),
        "structure_score": _clamp(payload.get("structure_score"), 0, 5),
        "cost_efficiency_score": _clamp(payload.get("cost_efficiency_score"), 0, 5),
    }
    total = _clamp(payload.get("total_score"), 0, 100)
    if total <= 0:
        total = round(sum(scores.values()), 2)
    scores, total = apply_rule_caps(scores, total, rule_report)
    risk_level = str(payload.get("risk_level") or _risk_from_score(total, scores)).lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = _risk_from_score(total, scores)
    if total < 70 and risk_level == "low":
        risk_level = "medium"
    if scores.get("source_quality_score", 0) <= 3 and risk_level == "low":
        risk_level = "medium"
    if scores.get("source_quality_score", 0) <= 2 and scores.get("truthfulness_score", 0) <= 35:
        risk_level = "high"
    if total < 50:
        risk_level = "high"
    if "mock_output" in (rule_report.get("failure_types") or []):
        risk_level = "high"
    if "missing_required_structure" in (rule_report.get("failure_types") or []) and risk_level == "low":
        risk_level = "medium"

    agent_model = get_agent_model(EVALUATOR_AGENT_KEY)
    rationale_prefix = (
        f"LLM evaluator={agent_model.provider}/{agent_model.model}; prompt={EVALUATOR_PROMPT_LOCATION}; "
        f"verification_search={verification_search_strategy}."
        if used_agent
        else f"rule_fallback; prompt={EVALUATOR_PROMPT_LOCATION}."
    )
    rule_issues = rule_report.get("issues") or []
    agent_issue_summary = str(payload.get("issue_summary") or "").strip()
    issue_summary = _merge_issue_summary(rule_issues, agent_issue_summary or "- 未返回明确问题摘要")
    return {
        "total_score": round(total, 2),
        **{key: round(value, 2) for key, value in scores.items()},
        "issue_summary": issue_summary,
        "rationale": f"{rationale_prefix}\n规则指标：{json.dumps(rule_report.get('metrics') or {}, ensure_ascii=False)}\n{payload.get('rationale') or ''}".strip(),
        "rule_metrics_json": rule_metrics_json(rule_report),
        "risk_level": risk_level,
    }


def _evaluator_search_strategy(combination: TestCombination) -> str:
    parameter = combination.parameter_config
    if parameter.search_strategy in {"agent", "agent_max"} or parameter.enable_secondary_verification:
        return "agent"
    if parameter.search_strategy in {"turbo", "max"}:
        return parameter.search_strategy
    return "turbo"


def _rule_fallback_scores(
    result: TestResult,
    combination: TestCombination,
    cost: float,
    rule_report: dict,
    fallback_reason: str = "",
) -> dict:
    parameter_config = combination.parameter_config
    sources = _safe_json(result.sources_json)
    output = result.raw_output or ""
    search_logs = _safe_json(result.search_logs_json)
    metrics = rule_report.get("metrics") or {}
    failure_types = set(rule_report.get("failure_types") or [])
    is_mock = "mock_output" in failure_types
    has_citations = bool(sources) or bool(re.search(r"https?://|\[\d+\]", output))
    has_uncertainty = any(word in output for word in ["无法确认", "待核验", "未确认", "风险提示"])
    has_structure = bool(metrics.get("has_required_structure")) or "###" in output or "##" in output or "- " in output

    truthfulness = 30 if is_mock else 38
    if metrics.get("claim_count") and metrics.get("claim_source_binding_rate", 0) >= 0.8:
        truthfulness += 6
    if has_uncertainty:
        truthfulness += 6
    if parameter_config.allow_model_memory:
        truthfulness -= 8
    if parameter_config.force_citations and not has_citations:
        truthfulness = min(truthfulness, 35)

    completeness = min(20, 6 + len(output) / 350)
    if not output.strip() or result.error_message:
        completeness = 0
    source_quality = 3 if is_mock else min(10, max(len(sources), int(metrics.get("source_count") or 0)) * 1.5)
    if metrics.get("valid_url_count"):
        source_quality = max(source_quality, min(10, float(metrics["valid_url_count"]) * 1.5))
    if parameter_config.force_citations and not has_citations:
        source_quality = min(source_quality, 3)
    stability = 8 if parameter_config.temperature <= 0.4 else 6
    structure = 5 if has_structure else 2.5
    cost_efficiency = 4 if cost <= 0.01 else max(1, 5 - cost * 80)

    scores = {
        "truthfulness_score": round(max(0, min(truthfulness, 50)), 2),
        "completeness_score": round(max(0, min(completeness, 20)), 2),
        "source_quality_score": round(max(0, min(source_quality, 10)), 2),
        "stability_score": round(max(0, min(stability, 10)), 2),
        "structure_score": round(max(0, min(structure, 5)), 2),
        "cost_efficiency_score": round(max(0, min(cost_efficiency, 5)), 2),
    }
    scores, total = apply_rule_caps(scores, round(sum(scores.values()), 2), rule_report)
    issues = []
    if fallback_reason:
        issues.append(fallback_reason)
    issues.extend(rule_report.get("issues") or [])
    if parameter_config.allow_model_memory:
        issues.append("参数允许模型基于记忆补充事实，联网搜索任务存在更高幻觉风险。")
    if parameter_config.force_citations and not has_citations:
        issues.append("强制来源引用已开启，但输出缺少可识别来源。")
    if not issues:
        issues.append("规则兜底评分未发现严重格式问题，仍需结合任务目标人工复核。")
    return {
        "total_score": round(total, 2),
        **scores,
        "issue_summary": "\n".join(f"- {issue}" for issue in issues),
        "rationale": (
            f"rule_fallback; prompt={EVALUATOR_PROMPT_LOCATION}. "
            f"{fallback_reason or 'LLM evaluator unavailable or invalid JSON.'}\n"
            f"规则指标：{json.dumps(metrics, ensure_ascii=False)}"
        ),
        "rule_metrics_json": rule_metrics_json(rule_report),
        "risk_level": _risk_from_score(total, scores),
    }


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


def _safe_json(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _is_mock_result(sources: list, logs: list) -> bool:
    return any(source.get("source", "").startswith("mock") for source in sources) or any(
        log.get("mode") == "mock_model_output" for log in logs
    )


def _merge_issue_summary(rule_issues: list[str], agent_summary: str) -> str:
    lines = [f"- {issue}" for issue in rule_issues]
    if agent_summary:
        if agent_summary.lstrip().startswith("-"):
            lines.append(agent_summary)
        else:
            lines.append(f"- {agent_summary}")
    return "\n".join(lines)


def _clamp(value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0
    return max(low, min(number, high))


def _risk_from_score(total: float, scores: dict[str, float]) -> str:
    if total >= 80 and scores.get("truthfulness_score", 0) >= 40 and scores.get("source_quality_score", 0) >= 6:
        return "low"
    if total < 55 or scores.get("truthfulness_score", 0) < 30:
        return "high"
    return "medium"
