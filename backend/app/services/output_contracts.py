import json
import re
from typing import Any


WEB_SEARCH_OUTPUT_SCHEMA: dict[str, Any] = {
    "summary": "",
    "claims": [
        {
            "claim_text": "",
            "claim_type": "fact|inference|unknown",
            "source_ids": [],
            "event_date": "",
            "confidence": "high|medium|low",
        }
    ],
    "sources": [
        {
            "source_id": "S1",
            "title": "",
            "url": "",
            "published_date": "",
            "source_type": "official|media|database|other",
        }
    ],
    "risk_notes": [],
    "unverified_items": [],
    "search_queries_used": [],
}


STRUCTURED_OUTPUT_INSTRUCTIONS = """输出必须是一个严格 JSON 对象，不要 Markdown，不要代码块，并符合以下协议：
{
  "summary": "一句话摘要",
  "claims": [
    {
      "claim_text": "关键结论",
      "claim_type": "fact|inference|unknown",
      "source_ids": ["S1"],
      "event_date": "事件日期或当前状态日期，未知则为空",
      "confidence": "high|medium|low"
    }
  ],
  "sources": [
    {
      "source_id": "S1",
      "title": "来源标题",
      "url": "https://...",
      "published_date": "来源发布日期，未知则为空",
      "source_type": "official|media|database|other"
    }
  ],
  "risk_notes": ["风险提示"],
  "unverified_items": ["无法确认的内容"],
  "search_queries_used": ["实际使用或建议使用的搜索 query"]
}

规则：
1. 只能基于搜索结果和可验证来源回答，禁止用模型记忆补全事实。
2. 每条关键结论都必须进入 claims。
3. claim_type=fact 的结论必须绑定 source_ids。
4. 无法确认的信息必须写入 unverified_items，不能写成事实。
5. 涉及时间、金额、主体、状态、处罚、招投标、舆情等内容时，必须填写 event_date 或在 claim_text 中说明时间语境。
"""


REQUIRED_OUTPUT_KEYS = {
    "summary",
    "claims",
    "sources",
    "risk_notes",
    "unverified_items",
    "search_queries_used",
}


def parse_structured_output(text: str) -> dict[str, Any] | None:
    """Parse the first JSON object that looks like the web-search output contract."""
    if not text:
        return None
    for candidate in _json_candidates(text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def has_required_output_structure(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if not REQUIRED_OUTPUT_KEYS.issubset(payload.keys()):
        return False
    return isinstance(payload.get("claims"), list) and isinstance(payload.get("sources"), list)


def _json_candidates(text: str) -> list[str]:
    candidates = [text.strip()]
    candidates.extend(item.strip() for item in re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S))
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        candidates.append(match.group(0))
    return candidates
