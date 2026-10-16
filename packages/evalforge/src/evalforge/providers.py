import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from evalforge.errors import EvalError


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str


@dataclass(frozen=True)
class Completion:
    text: str
    tool_calls: list[ToolCall]
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float


@dataclass
class MockProvider:
    fixtures: dict[str, Any]
    target_name: str
    _cursors: dict[str, int] = field(default_factory=dict)

    def complete(
        self,
        *,
        case_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        temperature: float,
        seed: int,
    ) -> Completion:
        del messages, tools, model, temperature, seed
        steps = self._steps(case_id)
        index = self._cursors.get(case_id, 0)
        if index >= len(steps):
            raise EvalError(f"mock fixture exhausted for {self.target_name}/{case_id}")
        self._cursors[case_id] = index + 1
        return _completion_from_step(steps[index], fallback_id=f"call-{index + 1}")

    def close(self) -> None:
        return None

    def reset(self) -> None:
        self._cursors.clear()

    def _steps(self, case_id: str) -> list[dict[str, Any]]:
        target_cases = self.fixtures.get(self.target_name)
        if not isinstance(target_cases, dict) or case_id not in target_cases:
            raise EvalError(f"mock fixture missing for {self.target_name}/{case_id}")
        spec = target_cases[case_id]
        if not isinstance(spec, dict):
            raise EvalError(f"mock fixture for {self.target_name}/{case_id} must be an object")
        if "steps" in spec:
            steps = spec["steps"]
            if not isinstance(steps, list) or not steps:
                raise EvalError(f"mock steps for {self.target_name}/{case_id} must be a non-empty list")
            return steps
        return [spec]


class OpenAIProvider:
    def __init__(self, *, api_key: str, base_url: str, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=60,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def complete(
        self,
        *,
        case_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        temperature: float,
        seed: int,
    ) -> Completion:
        del case_id
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "seed": seed,
        }
        if tools:
            body["tools"] = tools
        started = time.perf_counter()
        try:
            response = self._client.post("/chat/completions", json=body)
        except httpx.HTTPError as exc:
            raise EvalError(f"provider request failed: {exc.__class__.__name__}") from exc
        latency_ms = (time.perf_counter() - started) * 1000
        if response.status_code >= 400:
            raise EvalError(f"provider returned HTTP {response.status_code}")
        try:
            payload = response.json()
            message = payload["choices"][0]["message"]
            usage = payload.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise EvalError("provider returned an unexpected completion payload") from exc
        return Completion(
            text=message.get("content") or "",
            tool_calls=_parse_tool_calls(message.get("tool_calls") or []),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=latency_ms,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def _completion_from_step(step: dict[str, Any], *, fallback_id: str) -> Completion:
    tool_calls = [
        ToolCall(
            name=call["name"],
            arguments=dict(call.get("arguments") or {}),
            call_id=str(call.get("id") or f"{fallback_id}-{offset}"),
        )
        for offset, call in enumerate(step.get("tool_calls") or [], start=1)
    ]
    return Completion(
        text=str(step.get("text") or ""),
        tool_calls=tool_calls,
        prompt_tokens=int(step.get("prompt_tokens") or 0),
        completion_tokens=int(step.get("completion_tokens") or 0),
        latency_ms=float(step.get("latency_ms") or 0),
    )


def _parse_tool_calls(raw_calls: list[dict[str, Any]]) -> list[ToolCall]:
    parsed: list[ToolCall] = []
    for call in raw_calls:
        function = call.get("function") or {}
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise EvalError("provider returned tool arguments that are not JSON") from exc
        if not isinstance(arguments, dict):
            raise EvalError("provider tool arguments must be a JSON object")
        parsed.append(
            ToolCall(
                name=function.get("name") or "",
                arguments=arguments,
                call_id=str(call.get("id") or ""),
            )
        )
    return parsed
