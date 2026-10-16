import json

import httpx

from evalforge.providers import OpenAIProvider


def test_openai_provider_reads_text_usage_and_tool_calls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert body["seed"] == 7
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "lookup_policy", "arguments": "{\"topic\":\"refund\"}"},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4},
            },
        )

    provider = OpenAIProvider(
        api_key="test",
        base_url="https://example.test/v1",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test/v1"),
    )
    completion = provider.complete(
        case_id="tool-refund-policy",
        messages=[{"role": "user", "content": "Look up the refund policy."}],
        tools=[{"type": "function", "function": {"name": "lookup_policy"}}],
        model="gpt-4o-mini",
        temperature=0,
        seed=7,
    )
    assert completion.tool_calls[0].name == "lookup_policy"
    assert completion.tool_calls[0].arguments == {"topic": "refund"}
    assert completion.prompt_tokens == 11
    assert completion.latency_ms >= 0
