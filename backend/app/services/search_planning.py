from app.models.entities import TestTask


ENTERPRISE_KEYWORDS = ("公司", "企业", "背调", "主营", "经营", "融资", "股权", "处罚", "监管", "诉讼", "招投标", "采购", "风险", "舆情")


def build_search_plan(task: TestTask) -> dict:
    text = " ".join([task.name or "", task.description or "", task.background or "", task.focus_points or ""]).strip()
    subject = _subject(task)
    if _looks_like_enterprise_research(text):
        queries = [
            _query(subject, "主体基础信息 主营业务 官网 工商 信息", "basic_info", "high"),
            _query(subject, "近期 新闻 公告 动态", "recent_news", "high"),
            _query(subject, "经营 状态 财务 融资 资本 动态", "operation", "medium"),
            _query(subject, "行政处罚 监管 处罚 风险", "regulatory", "high"),
            _query(subject, "司法 诉讼 被执行 裁判文书", "risk", "high"),
            _query(subject, "招投标 采购 中标 公告", "tender", "medium"),
        ]
    else:
        queries = [
            _query(subject, task.focus_points or task.description or "公开信息", "basic_info", "high"),
            _query(subject, "最新 动态 新闻 公告", "recent_news", "medium"),
            _query(subject, "风险 争议 监管 核验", "risk", "medium"),
        ]
    return {"queries": _dedupe_queries(queries)}


def _subject(task: TestTask) -> str:
    for value in [task.name, task.background, task.description]:
        value = (value or "").strip()
        if value:
            return value[:80]
    return "公开信息核验"


def _query(subject: str, suffix: str, intent: str, priority: str) -> dict:
    return {"query": f"{subject} {suffix}".strip(), "intent": intent, "priority": priority}


def _dedupe_queries(queries: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for item in queries:
        query = item["query"]
        if query in seen:
            continue
        seen.add(query)
        deduped.append(item)
    return deduped


def _looks_like_enterprise_research(text: str) -> bool:
    return any(keyword in text for keyword in ENTERPRISE_KEYWORDS)
