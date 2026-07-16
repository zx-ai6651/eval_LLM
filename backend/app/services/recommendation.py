import json

from app.models.entities import TestCombination


def recommendation_score(combo: TestCombination) -> float:
    evaluation = combo.evaluation
    if not evaluation:
        return 0
    metrics = _rule_metrics(evaluation.rule_metrics_json)
    risk_penalty = {"low": 0, "medium": 5, "high": 15}.get(evaluation.risk_level, 8)
    unsupported_claim_penalty = min(15, float(metrics.get("unsupported_claim_count") or 0) * 3)
    search_failure_penalty = min(10, float(metrics.get("search_failure_count") or 0) * 2)
    score = (
        evaluation.truthfulness_score * 0.35
        + evaluation.source_quality_score * 2 * 0.20
        + evaluation.completeness_score * 2.5 * 0.15
        + evaluation.stability_score * 5 * 0.15
        + evaluation.structure_score * 10 * 0.05
        + evaluation.cost_efficiency_score * 10 * 0.05
        - risk_penalty
        - unsupported_claim_penalty
        - search_failure_penalty
    )
    return round(max(0, score), 2)


def recommendation_sort_key(combo: TestCombination) -> tuple:
    evaluation = combo.evaluation
    if not evaluation:
        return (0, 0, 0)
    return (
        recommendation_score(combo),
        evaluation.truthfulness_score,
        evaluation.total_score,
    )


def _rule_metrics(value: str) -> dict:
    try:
        payload = json.loads(value or "{}")
    except Exception:
        return {}
    metrics = payload.get("metrics") if isinstance(payload, dict) else {}
    return metrics if isinstance(metrics, dict) else {}
