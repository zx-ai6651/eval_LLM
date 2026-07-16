import asyncio
import json
import re
import time
from dataclasses import dataclass

import httpx

from app.core.model_adapters import chat_completions_search_extra, get_agent_model, get_provider, resolve_api_key
from app.core.pricing import combine_costs, estimate_model_cost, estimate_tool_cost
from app.models.entities import ModelConfig, ParameterConfig


@dataclass
class ModelCallResult:
    success: bool
    output: str
    duration_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0
    error_message: str = ""
    sources: list[dict] | None = None
    search_logs: list[dict] | None = None
    cost_breakdown: dict | None = None


class ModelClient:
    max_attempts = 3

    async def complete(
        self,
        model_config: ModelConfig,
        parameter_config: ParameterConfig,
        system_prompt: str,
        task_payload: str,
        agent_key: str = "task_executor",
    ) -> ModelCallResult:
        provider = get_provider(model_config.provider)
        api_key = resolve_api_key(provider, model_config.api_key_ref)
        base_url = (model_config.base_url or provider.base_url).rstrip("/")
        model_name = model_config.name or provider.default_model
        if not api_key:
            return self._mock_result(model_name, provider.label, task_payload)

        return await self._chat_completion(
            base_url=base_url,
            api_key=api_key,
            model=model_name,
            temperature=parameter_config.temperature,
            top_p=parameter_config.top_p,
            max_tokens=parameter_config.max_tokens,
            system_prompt=system_prompt,
            task_payload=task_payload,
            extra_body=chat_completions_search_extra(provider, parameter_config.search_strategy),
            provider_name=model_config.provider,
            provider_label=provider.label,
        )

    async def complete_for_agent(
        self,
        agent_key: str,
        system_prompt: str,
        task_payload: str,
        enable_builtin_search: bool = False,
        search_strategy: str | None = None,
    ) -> ModelCallResult:
        agent_model = get_agent_model(agent_key)
        provider = get_provider(agent_model.provider)
        api_key = resolve_api_key(provider)
        base_url = provider.base_url.rstrip("/")
        if not api_key:
            return self._mock_result(agent_model.model, provider.label, task_payload)

        return await self._chat_completion(
            base_url=base_url,
            api_key=api_key,
            model=agent_model.model,
            temperature=agent_model.temperature,
            top_p=agent_model.top_p,
            max_tokens=agent_model.max_tokens,
            system_prompt=system_prompt,
            task_payload=task_payload,
            extra_body=chat_completions_search_extra(provider, search_strategy) if enable_builtin_search else {},
            provider_name=agent_model.provider,
            provider_label=provider.label,
        )

    async def _chat_completion(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        system_prompt: str,
        task_payload: str,
        extra_body: dict | None = None,
        provider_name: str = "",
        provider_label: str = "",
    ) -> ModelCallResult:
        started = time.perf_counter()
        payload = {
            "model": model,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_payload},
            ],
        }
        if extra_body:
            payload.update(extra_body)
        uses_builtin_search = bool(extra_body and extra_body.get("enable_search"))
        data: dict = {}
        streamed_sources: list[dict] = []
        stream_event_count = 0
        retry_logs: list[dict] = []
        try:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    async with httpx.AsyncClient(timeout=220 if uses_builtin_search else 90) as client:
                        data, streamed_sources, stream_event_count = await self._send_chat_request(
                            client=client,
                            base_url=base_url,
                            api_key=api_key,
                            payload=dict(payload),
                            uses_builtin_search=uses_builtin_search,
                        )
                    if attempt > 1:
                        retry_logs.append({"attempt": attempt, "mode": "retry_success"})
                    break
                except httpx.HTTPStatusError as exc:
                    response_text = exc.response.text[:2000]
                    retry_logs.append(
                        {
                            "attempt": attempt,
                            "mode": "http_error",
                            "status_code": exc.response.status_code,
                            "response": response_text,
                        }
                    )
                    if attempt >= self.max_attempts or not self._is_retryable_status(exc.response.status_code):
                        duration_ms = int((time.perf_counter() - started) * 1000)
                        message = f"{exc.response.status_code} {exc.response.reason_phrase}: {response_text}"
                        return self._failure_result(
                            duration_ms,
                            message,
                            provider_label or provider_name,
                            extra_body,
                            retry_logs,
                        )
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    retry_logs.append(
                        {
                            "attempt": attempt,
                            "mode": "transport_error",
                            "error_type": exc.__class__.__name__,
                            "error_message": str(exc),
                        }
                    )
                    if attempt >= self.max_attempts:
                        duration_ms = int((time.perf_counter() - started) * 1000)
                        message = self._format_exception(exc)
                        return self._failure_result(
                            duration_ms,
                            message,
                            provider_label or provider_name,
                            extra_body,
                            retry_logs,
                        )
                except Exception as exc:
                    retry_logs.append(
                        {
                            "attempt": attempt,
                            "mode": "unexpected_error",
                            "error_type": exc.__class__.__name__,
                            "error_message": str(exc),
                        }
                    )
                    if attempt >= self.max_attempts:
                        duration_ms = int((time.perf_counter() - started) * 1000)
                        message = self._format_exception(exc)
                        return self._failure_result(
                            duration_ms,
                            message,
                            provider_label or provider_name,
                            extra_body,
                            retry_logs,
                        )
                await asyncio.sleep(min(8, 0.8 * 2 ** (attempt - 1)))
            else:
                duration_ms = int((time.perf_counter() - started) * 1000)
                return self._failure_result(duration_ms, "RetryExhausted: no response", provider_label or provider_name, extra_body, retry_logs)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return self._failure_result(
                duration_ms,
                self._format_exception(exc),
                provider_label or provider_name,
                extra_body,
                retry_logs,
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        usage = data.get("usage", {})
        output = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        total_tokens = int(usage.get("total_tokens", 0) or 0)
        sources = self._dedupe_sources(streamed_sources or self._extract_sources(data) or self._extract_sources_from_text(output))
        search_logs = []
        tool_calls = {}
        if extra_body and extra_body.get("enable_search"):
            tool_calls = {"web_search": 1, "web_extractor": 1}
            search_logs.append(
                {
                    "provider": provider_label or "bailian",
                    "mode": "chat_completions_builtin_search",
                    "tool_pair": ["web_search", "web_extractor"],
                    "request": extra_body,
                    "stream": True,
                    "stream_event_count": stream_event_count,
                    "sources_returned": len(sources),
                }
            )
        if retry_logs:
            search_logs.append({"mode": "retry_log", "attempts": retry_logs})
        model_cost = estimate_model_cost(provider_name, model, usage)
        tool_cost = estimate_tool_cost(provider_name, tool_calls)
        cost_breakdown = combine_costs(model_cost, tool_cost)
        return ModelCallResult(
            success=bool(output),
            output=output,
            duration_ms=duration_ms,
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            total_tokens=total_tokens,
            estimated_cost=cost_breakdown["total_cost"],
            error_message="" if output else "empty model output",
            sources=sources,
            search_logs=search_logs,
            cost_breakdown=cost_breakdown,
        )

    async def _send_chat_request(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        payload: dict,
        uses_builtin_search: bool,
    ) -> tuple[dict, list[dict], int]:
        if uses_builtin_search:
            payload["stream"] = True
            output_parts: list[str] = []
            usage: dict = {}
            streamed_sources: list[dict] = []
            stream_event_count = 0
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            ) as response:
                if response.is_error:
                    await response.aread()
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line.removeprefix("data:").strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        event = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    stream_event_count += 1
                    usage = event.get("usage") or usage
                    streamed_sources.extend(self._extract_sources(event))
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    content = self._extract_stream_content(choices[0])
                    if content:
                        output_parts.append(content)
            data = {"choices": [{"message": {"content": "".join(output_parts)}}], "usage": usage}
            return data, streamed_sources, stream_event_count

        response = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
        return response.json(), [], 0

    def _failure_result(
        self,
        duration_ms: int,
        message: str,
        provider: str,
        extra_body: dict | None,
        retry_logs: list[dict],
    ) -> ModelCallResult:
        return ModelCallResult(
            False,
            "",
            duration_ms,
            error_message=message,
            search_logs=[
                {
                    "provider": provider,
                    "mode": "chat_completions_error",
                    "error_message": message,
                    "request_extra_body": extra_body or {},
                    "attempts": retry_logs,
                }
            ],
        )

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code in {408, 409, 425, 429, 500, 502, 503, 504}

    def _format_exception(self, exc: Exception) -> str:
        text = str(exc)
        return f"{exc.__class__.__name__}: {text}" if text else exc.__class__.__name__

    def _extract_stream_content(self, choice: dict) -> str:
        delta = choice.get("delta") or {}
        message = choice.get("message") or {}
        content = delta.get("content") or message.get("content") or ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
            return "".join(parts)
        return str(content) if content else ""

    def _extract_sources(self, data: dict) -> list[dict]:
        choices = data.get("choices") or [{}]
        first_choice = choices[0] if choices else {}
        message = first_choice.get("message") or {}
        delta = first_choice.get("delta") or {}
        possible_containers = [
            data.get("search_info"),
            data.get("output", {}).get("search_info") if isinstance(data.get("output"), dict) else None,
            message.get("search_info"),
            delta.get("search_info"),
            message.get("extra", {}).get("search_info") if isinstance(message.get("extra"), dict) else None,
            delta.get("extra", {}).get("search_info") if isinstance(delta.get("extra"), dict) else None,
        ]
        sources: list[dict] = []
        for container in possible_containers:
            if not container:
                continue
            if isinstance(container, dict):
                candidates = container.get("results") or container.get("search_results") or container.get("sources") or []
            elif isinstance(container, list):
                candidates = container
            else:
                candidates = []
            for index, item in enumerate(candidates):
                if not isinstance(item, dict):
                    continue
                sources.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url") or item.get("link", ""),
                        "snippet": item.get("snippet") or item.get("content", ""),
                        "published_date": item.get("published_date") or item.get("date", ""),
                        "source": "bailian_builtin",
                        "rank": item.get("rank", index + 1),
                    }
                )
        sources.extend(self._extract_sources_recursive(data))
        return sources

    def _extract_sources_recursive(self, value: object) -> list[dict]:
        sources: list[dict] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"results", "search_results", "sources", "docs"} and isinstance(item, list):
                    for index, candidate in enumerate(item):
                        if isinstance(candidate, dict):
                            url = candidate.get("url") or candidate.get("link") or candidate.get("href") or ""
                            title = candidate.get("title") or candidate.get("name") or candidate.get("site_name") or ""
                            snippet = candidate.get("snippet") or candidate.get("content") or candidate.get("text") or ""
                            if url or title or snippet:
                                sources.append(
                                    {
                                        "title": title,
                                        "url": url,
                                        "snippet": snippet,
                                        "published_date": candidate.get("published_date") or candidate.get("date") or "",
                                        "source": "bailian_builtin",
                                        "rank": candidate.get("rank", index + 1),
                                    }
                                )
                sources.extend(self._extract_sources_recursive(item))
        elif isinstance(value, list):
            for item in value:
                sources.extend(self._extract_sources_recursive(item))
        return sources

    def _extract_sources_from_text(self, text: str) -> list[dict]:
        sources: list[dict] = []
        for index, match in enumerate(re.finditer(r"https?://[^\s\]\)）>\"']+", text or ""), start=1):
            url = match.group(0).rstrip(".,;，。；、")
            sources.append(
                {
                    "title": url,
                    "url": url,
                    "snippet": "",
                    "published_date": "",
                    "source": "output_url",
                    "rank": index,
                }
            )
        return sources

    def _dedupe_sources(self, sources: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for source in sources:
            key = (source.get("url", ""), source.get("title", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(source)
        return deduped

    def _mock_result(self, model_name: str, provider_label: str, task_payload: str) -> ModelCallResult:
        started = time.perf_counter()
        output = (
            "## 联网搜索任务结果\n\n"
            f"模型 `{provider_label} / {model_name}` 当前未配置 API Key，系统使用演示模式生成结果。\n\n"
            "### 已核验信息\n"
            "1. 已根据搜索结果整理任务相关公开信息。\n"
            "2. 关键结论保留来源引用，未确认内容标记为待核验。\n\n"
            "### 风险提示\n"
            "- 这是演示输出，真实生产测试需要配置 DeepSeek 或阿里百炼 API Key。\n"
            "- 后续评估会降低真实性和来源质量评分，避免把演示内容当作真实结论。\n\n"
            f"### 原始任务摘要\n{task_payload[:800]}"
        )
        return ModelCallResult(
            True,
            output,
            int((time.perf_counter() - started) * 1000),
            estimated_cost=0,
            sources=[],
            search_logs=[
                {
                    "provider": provider_label,
                    "mode": "mock_model_output",
                    "tool_pair": ["web_search", "web_extractor"] if "百炼" in provider_label else [],
                }
            ],
            cost_breakdown={"currency": "CNY", "total_cost": 0, "parts": []},
        )
