import json

from app.models.entities import Report, TestBatch
from app.services.recommendation import recommendation_score, recommendation_sort_key


def build_report(batch: TestBatch) -> tuple[str, int | None]:
    completed = [combo for combo in batch.combinations if combo.evaluation]
    ranked = sorted(
        completed,
        key=recommendation_sort_key,
        reverse=True,
    )
    recommended = ranked[0] if ranked else None
    lines = [
        f"# {batch.name} 测试报告",
        "",
        f"- 批次状态：{batch.status}",
        f"- 测试组合数：{len(batch.combinations)}",
        f"- 总耗时：{batch.duration_ms} ms",
        f"- 总成本估算：{batch.total_cost:.6f}",
        "",
        "## 推荐配置",
    ]
    if recommended:
        lines.extend(
            [
                f"- 组合 ID：{recommended.id}",
                f"- Prompt：{recommended.prompt.name}",
                f"- 模型：{recommended.model_config.name}",
                f"- 参数：{recommended.parameter_config.name}",
                f"- 总分：{recommended.evaluation.total_score}",
                f"- 综合推荐分：{recommendation_score(recommended)}",
                f"- 风险等级：{recommended.evaluation.risk_level}",
                f"- 推荐理由：真实性 {recommended.evaluation.truthfulness_score}，来源质量 {recommended.evaluation.source_quality_score}，规则失败类型 {_failure_types_text(recommended.evaluation.rule_metrics_json)}。",
            ]
        )
    else:
        lines.append("- 暂无可推荐配置。")

    lines.extend(["", "## 评分明细", ""])
    for combo in ranked:
        evaluation = combo.evaluation
        lines.extend(
            [
                f"### 组合 {combo.id}",
                f"- Prompt / 模型 / 参数：{combo.prompt.name} / {combo.model_config.name} / {combo.parameter_config.name}",
                f"- 总分：{evaluation.total_score}",
                f"- 综合推荐分：{recommendation_score(combo)}",
                f"- 真实性：{evaluation.truthfulness_score}",
                f"- 来源质量：{evaluation.source_quality_score}",
                f"- 风险等级：{evaluation.risk_level}",
                f"- 规则指标：{_metrics_summary(evaluation.rule_metrics_json)}",
                "- 问题摘要：",
                evaluation.issue_summary,
                "",
            ]
        )

    lines.extend(
        [
            "## 后续建议",
            "",
            "1. 为真实测试配置可用的模型 API Key 和搜索 API。",
            "2. 优先保留真实性与来源质量较高的配置。",
            "3. 对高风险配置补充来源约束、时间线要求和无法确认时的输出规则。",
            "4. 若规则指标显示 search_failure_count 较高，应优先检查搜索策略或 API 配置，不要直接归因到 Prompt。",
        ]
    )
    return "\n".join(lines), recommended.id if recommended else None


def upsert_report(batch: TestBatch) -> Report:
    content, recommended_id = build_report(batch)
    if batch.reports:
        report = batch.reports[0]
        report.title = f"{batch.name} 测试报告"
        report.content = content
        report.recommended_combination_id = recommended_id
        return report
    return Report(
        batch_id=batch.id,
        title=f"{batch.name} 测试报告",
        content=content,
        recommended_combination_id=recommended_id,
    )


def _metrics_summary(value: str) -> str:
    metrics = _metrics(value)
    if not metrics:
        return "暂无规则指标"
    return (
        f"claims {metrics.get('supported_claim_count', 0)}/{metrics.get('claim_count', 0)} 有来源绑定，"
        f"sources {metrics.get('source_count', 0)}，valid_urls {metrics.get('valid_url_count', 0)}，"
        f"结构化输出 {'是' if metrics.get('has_required_structure') else '否'}，"
        f"search_failures {metrics.get('search_failure_count', 0)}"
    )


def _failure_types_text(value: str) -> str:
    try:
        payload = json.loads(value or "{}")
    except Exception:
        return "无"
    failure_types = payload.get("failure_types") if isinstance(payload, dict) else []
    return "、".join(failure_types) if failure_types else "无"


def _metrics(value: str) -> dict:
    try:
        payload = json.loads(value or "{}")
    except Exception:
        return {}
    metrics = payload.get("metrics") if isinstance(payload, dict) else {}
    return metrics if isinstance(metrics, dict) else {}
