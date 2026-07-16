import json
import re
from typing import Any

from app.models.entities import TestCombination, TestResult
from app.services.output_contracts import has_required_output_structure, parse_structured_output
from app.services.source_normalization import normalize_sources, valid_url_count


DATE_RE = re.compile(r"\b(?:20\d{2}|19\d{2})[-年/.](?:0?[1-9]|1[0-2])(?:[-月/.](?:0?[1-9]|[12]\d|3[01])日?)?")
URL_OR_CITATION_RE = re.compile(r"https?://|\[[A-Za-z]?\d+\]|来源|source_id", flags=re.I)
MOCK_RE = re.compile(r"演示|demo|mock|未配置 API Key|示例输出|example\.com", flags=re.I)


def evaluate_output_rules(result: TestResult, combination: TestCombination) -> dict[str, Any]:
    raw_output = result.raw_output or ""
    structured = parse_structured_output(result.structured_output or raw_output)
    has_structure = has_required_output_structure(structured)
    output_sources = structured.get("sources", []) if isinstance(structured, dict) else []
    persisted_sources = _safe_json(result.sources_json)
    sources = normalize_sources([*output_sources, *persisted_sources], preserve_source_ids=True)
    claims = _claims_from_structured_output(structured)
    source_ids = {str(source.get("source_id")) for source in sources}
    supported_claims = [claim for claim in claims if _claim_has_source_binding(claim, source_ids)]
    fact_claims = [claim for claim in claims if _claim_type(claim) == "fact"]
    unsupported_fact_claims = [claim for claim in fact_claims if not _claim_has_source_binding(claim, source_ids)]
    unknown_claims = [claim for claim in claims if _claim_type(claim) == "unknown"]
    search_logs = _safe_json(result.search_logs_json)
    search_failure_count = sum(1 for log in search_logs if isinstance(log, dict) and log.get("success") is False)
    is_mock = _is_mock_output(raw_output, sources, search_logs)
    has_citations = bool(sources) or bool(URL_OR_CITATION_RE.search(raw_output))

    metrics = {
        "claim_count": len(claims),
        "supported_claim_count": len(supported_claims),
        "unsupported_claim_count": max(0, len(claims) - len(supported_claims)),
        "unsupported_fact_claim_count": len(unsupported_fact_claims),
        "claim_source_binding_rate": _ratio(len(supported_claims), len(claims)),
        "source_count": len(sources),
        "valid_url_count": valid_url_count(sources),
        "unknown_claim_count": len(unknown_claims),
        "has_required_structure": has_structure,
        "has_time_sensitive_claims": _has_time_sensitive_claims(raw_output, claims),
        "citation_coverage": _ratio(len([claim for claim in fact_claims if _claim_has_source_binding(claim, source_ids)]), len(fact_claims)),
        "search_failure_count": search_failure_count,
        "has_mock_output": is_mock,
        "has_citations": has_citations,
    }
    cap_total = 100.0
    score_caps: dict[str, float] = {}
    failure_types: list[str] = []
    issues: list[str] = []

    if result.error_message or not raw_output.strip():
        cap_total = min(cap_total, 45)
        failure_types.append("model_output_failure")
        issues.append("模型输出为空或执行失败，规则评估将总分封顶。")
    if is_mock:
        cap_total = min(cap_total, 45)
        score_caps["truthfulness_score"] = min(score_caps.get("truthfulness_score", 50), 25)
        failure_types.append("mock_output")
        issues.append("检测到 mock/demo/演示输出，不能作为真实联网搜索结果。")
    if combination.parameter_config.require_structured_output and not has_structure:
        cap_total = min(cap_total, 68)
        score_caps["structure_score"] = min(score_caps.get("structure_score", 5), 1.5)
        failure_types.append("missing_required_structure")
        issues.append("输出不符合联网搜索标准 JSON 协议，结构分被大幅扣减。")
    if combination.parameter_config.force_citations and not sources:
        cap_total = min(cap_total, 65)
        score_caps["source_quality_score"] = min(score_caps.get("source_quality_score", 10), 2.5)
        failure_types.append("missing_sources")
        issues.append("强制来源引用已开启，但未发现可机读来源。")
    if unsupported_fact_claims:
        cap_total = min(cap_total, 72)
        score_caps["truthfulness_score"] = min(score_caps.get("truthfulness_score", 50), 35)
        score_caps["source_quality_score"] = min(score_caps.get("source_quality_score", 10), 6)
        failure_types.append("unsupported_fact_claims")
        issues.append(f"存在 {len(unsupported_fact_claims)} 条 fact 结论未绑定来源。")
    if fact_claims and not sources:
        cap_total = min(cap_total, 60)
        failure_types.append("factual_claims_without_sources")
        issues.append("输出包含事实型结论，但没有来源集合可追溯。")
    if sources and valid_url_count(sources) == 0:
        cap_total = min(cap_total, 76)
        score_caps["source_quality_score"] = min(score_caps.get("source_quality_score", 10), 4)
        failure_types.append("invalid_source_urls")
        issues.append("来源集合中缺少有效 URL，来源质量分封顶。")
    if sources and len(sources) < 2 and combination.parameter_config.force_citations:
        score_caps["source_quality_score"] = min(score_caps.get("source_quality_score", 10), 5)
        failure_types.append("insufficient_sources")
        issues.append("来源数量不足，难以支撑联网搜索任务的关键结论。")

    return {
        "metrics": metrics,
        "score_caps": score_caps,
        "cap_total": cap_total,
        "failure_types": sorted(set(failure_types)),
        "issues": issues,
        "structured_output": structured if has_structure else None,
    }


def apply_rule_caps(scores: dict[str, float], total: float, rule_report: dict[str, Any]) -> tuple[dict[str, float], float]:
    adjusted = dict(scores)
    for score_name, cap in (rule_report.get("score_caps") or {}).items():
        if score_name in adjusted:
            adjusted[score_name] = min(adjusted[score_name], float(cap))
    recalculated = round(sum(adjusted.values()), 2)
    capped_total = min(float(total), float(rule_report.get("cap_total") or 100), recalculated)
    return adjusted, max(0, min(capped_total, 100))


def rule_metrics_json(rule_report: dict[str, Any]) -> str:
    payload = {
        "metrics": rule_report.get("metrics") or {},
        "failure_types": rule_report.get("failure_types") or [],
        "issues": rule_report.get("issues") or [],
        "score_caps": rule_report.get("score_caps") or {},
        "cap_total": rule_report.get("cap_total", 100),
    }
    return json.dumps(payload, ensure_ascii=False)


def _claims_from_structured_output(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        return []
    return [claim for claim in payload["claims"] if isinstance(claim, dict) and str(claim.get("claim_text") or "").strip()]


def _claim_type(claim: dict[str, Any]) -> str:
    value = str(claim.get("claim_type") or "").lower()
    return value if value in {"fact", "inference", "unknown"} else "fact"


def _claim_has_source_binding(claim: dict[str, Any], source_ids: set[str]) -> bool:
    source_refs = claim.get("source_ids") or []
    if isinstance(source_refs, str):
        source_refs = [source_refs]
    if not isinstance(source_refs, list):
        return False
    return any(str(source_id) in source_ids for source_id in source_refs)


def _has_time_sensitive_claims(raw_output: str, claims: list[dict[str, Any]]) -> bool:
    if DATE_RE.search(raw_output):
        return True
    return any(str(claim.get("event_date") or "").strip() for claim in claims)


def _is_mock_output(raw_output: str, sources: list[dict[str, Any]], search_logs: list[Any]) -> bool:
    if MOCK_RE.search(raw_output or ""):
        return True
    if any(str(source.get("source", "")).startswith("mock") or "example.com" in str(source.get("url", "")) for source in sources):
        return True
    return any(isinstance(log, dict) and log.get("mode") == "mock_model_output" for log in search_logs)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _safe_json(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []
