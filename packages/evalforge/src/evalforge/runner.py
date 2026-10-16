import json
import os
from pathlib import Path
from typing import Any

import yaml

from evalforge.compare import load_run
from evalforge.dataset import load_authored_cases, load_corpus
from evalforge.errors import EvalError
from evalforge.gate import evaluate_gate, percentile
from evalforge.hashing import prompt_sha256
from evalforge.judge import parse_judge_score, render_rubric
from evalforge.models import (
    Case,
    CaseResult,
    CaseScore,
    EvalConfig,
    EvalRun,
    Manifest,
    TargetConfig,
    TargetManifest,
    TargetResult,
    TargetSummary,
    ToolCallRecord,
)
from evalforge.pricing import cost_usd, load_pricing
from evalforge.providers import Completion, MockProvider, OpenAIProvider, ToolCall
from evalforge.rag import lexical_retrieve, retrieval_recall
from evalforge.scorers import answer_scores, case_quality
from evalforge.tool_calls import execute_stub, tool_match_score, tool_schemas

MAX_TOOL_ROUNDS = 4


def load_config(path: Path) -> tuple[EvalConfig, Path]:
    if not path.is_file():
        raise EvalError(f"config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        config = EvalConfig.model_validate(raw)
    except ValueError as exc:
        raise EvalError(f"invalid config: {exc}") from exc
    return config, path.parent.resolve()


def resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def execute_run(
    *,
    config: EvalConfig,
    config_dir: Path,
    baseline_path: Path | None = None,
) -> EvalRun:
    dataset_path = resolve_path(config_dir, config.dataset)
    _authored, cases, dataset_hash = load_authored_cases(dataset_path)
    dataset_dir = dataset_path.parent
    pricing = load_pricing(resolve_path(config_dir, config.pricing))
    baseline = load_run(baseline_path) if baseline_path else None
    judge_provider = _build_judge(config, config_dir) if config.judge.enabled else None
    target_results: list[TargetResult] = []
    manifests: list[TargetManifest] = []
    try:
        for target in config.targets:
            prompt_text = _read_prompt(resolve_path(config_dir, target.prompt))
            provider = _build_target_provider(target, config_dir)
            reset = getattr(judge_provider, "reset", None)
            if callable(reset):
                reset()
            try:
                result = _run_target(
                    target=target,
                    cases=cases,
                    provider=provider,
                    prompt_text=prompt_text,
                    prompt_hash=prompt_sha256(prompt_text),
                    dataset_dir=dataset_dir,
                    pricing=pricing,
                    temperature=config.temperature,
                    seed=config.seed,
                    top_k=config.top_k,
                    gate=config.gate,
                    baseline=baseline,
                    judge_provider=judge_provider,
                    judge_model=config.judge.model,
                    judge_rubric=config.judge.rubric_version,
                )
            finally:
                provider.close()
            manifests.append(
                TargetManifest(
                    name=target.name,
                    model=target.model,
                    provider=target.provider,
                    prompt_sha256=result.prompt_sha256,
                    temperature=config.temperature,
                )
            )
            target_results.append(result)
    finally:
        if judge_provider is not None:
            judge_provider.close()
    return EvalRun(
        manifest=Manifest(
            dataset_sha256=dataset_hash,
            pricing_version=pricing.version,
            seed=config.seed,
            temperature=config.temperature,
            judge_rubric_version=config.judge.rubric_version if config.judge.enabled else None,
            targets=manifests,
        ),
        passed=all(target.gate.passed for target in target_results),
        targets=target_results,
    )


def _run_target(
    *,
    target: TargetConfig,
    cases: list[Case],
    provider: MockProvider | OpenAIProvider,
    prompt_text: str,
    prompt_hash: str,
    dataset_dir: Path,
    pricing,
    temperature: float,
    seed: int,
    top_k: int,
    gate,
    baseline: EvalRun | None,
    judge_provider: MockProvider | OpenAIProvider | None,
    judge_model: str,
    judge_rubric: str,
) -> TargetResult:
    case_results = [
        _run_case(
            target=target,
            case=case,
            provider=provider,
            prompt_text=prompt_text,
            dataset_dir=dataset_dir,
            pricing=pricing,
            temperature=temperature,
            seed=seed,
            top_k=top_k,
            judge_provider=judge_provider,
            judge_model=judge_model,
            judge_rubric=judge_rubric,
        )
        for case in cases
    ]
    summary = _summarize(case_results)
    baseline_summary = _baseline_summary(baseline, target.name)
    verdict = evaluate_gate(summary, baseline_summary, gate, target_name=target.name)
    return TargetResult(
        name=target.name,
        model=target.model,
        prompt_sha256=prompt_hash,
        summary=summary,
        gate=verdict,
        cases=case_results,
    )


def _run_case(
    *,
    target: TargetConfig,
    case: Case,
    provider: MockProvider | OpenAIProvider,
    prompt_text: str,
    dataset_dir: Path,
    pricing,
    temperature: float,
    seed: int,
    top_k: int,
    judge_provider: MockProvider | OpenAIProvider | None,
    judge_model: str,
    judge_rubric: str,
) -> CaseResult:
    retrieved_ids: list[str] = []
    context = ""
    recall: float | None = None
    if case.type == "rag":
        chunks = load_corpus(dataset_dir / (case.corpus or ""))
        retrieved = lexical_retrieve(case.input, chunks, top_k)
        retrieved_ids = [chunk.id for chunk in retrieved]
        context = "\n\n".join(f"[{chunk.id}] {chunk.text}" for chunk in retrieved)
        recall = retrieval_recall(case.expected_chunk_ids, retrieved_ids)
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": render_prompt(prompt_text, question=case.input, context=context)}
    ]
    schemas = tool_schemas(case) if case.type == "tools" else None
    actual_calls: list[ToolCall] = []
    prompt_tokens = 0
    completion_tokens = 0
    latency_ms = 0.0
    output = ""
    for _ in range(MAX_TOOL_ROUNDS):
        completion = provider.complete(
            case_id=case.id,
            messages=messages,
            tools=schemas,
            model=target.model,
            temperature=temperature,
            seed=seed,
        )
        prompt_tokens += completion.prompt_tokens
        completion_tokens += completion.completion_tokens
        latency_ms += completion.latency_ms
        if not completion.tool_calls:
            output = completion.text
            break
        actual_calls.extend(completion.tool_calls)
        messages.append(_assistant_message(completion))
        for call in completion.tool_calls:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": execute_stub(case, call.name, call.arguments),
                }
            )
    scores = answer_scores(case.expected, output)
    tool_score: float | None = None
    if case.type == "tools":
        tool_score = tool_match_score(
            case.expected_calls,
            [(call.name, call.arguments) for call in actual_calls],
        )
        scores["tool_match"] = tool_score
    if recall is not None:
        scores["retrieval_recall"] = recall
    scores["quality"] = case_quality(scores["answer_quality"], recall, tool_score)
    judge_score = _judge_case(
        provider=judge_provider,
        case=case,
        output=output,
        model=judge_model,
        rubric_version=judge_rubric,
        seed=seed,
    )
    return CaseResult(
        case_id=case.id,
        case_type=case.type,
        output=output,
        expected=case.expected,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd(pricing, target.model, prompt_tokens, completion_tokens),
        scores=CaseScore.model_validate(scores),
        retrieved_chunk_ids=retrieved_ids,
        tool_calls=[ToolCallRecord(name=call.name, arguments=call.arguments) for call in actual_calls],
        judge_score=judge_score,
    )


def render_prompt(template: str, *, question: str, context: str) -> str:
    return template.replace("{{input}}", question).replace("{{context}}", context)


def _judge_case(
    *,
    provider: MockProvider | OpenAIProvider | None,
    case: Case,
    output: str,
    model: str,
    rubric_version: str,
    seed: int,
) -> float | None:
    if provider is None:
        return None
    completion = provider.complete(
        case_id=case.id,
        messages=[
            {
                "role": "user",
                "content": render_rubric(
                    version=rubric_version,
                    question=case.input,
                    expected=case.expected,
                    answer=output,
                ),
            }
        ],
        tools=None,
        model=model,
        temperature=0,
        seed=seed,
    )
    return parse_judge_score(completion.text)


def _summarize(cases: list[CaseResult]) -> TargetSummary:
    quality_values = [case.scores.quality for case in cases]
    recall_values = [case.scores.retrieval_recall for case in cases if case.scores.retrieval_recall is not None]
    tool_values = [case.scores.tool_match for case in cases if case.scores.tool_match is not None]
    return TargetSummary(
        quality=sum(quality_values) / len(quality_values) if quality_values else 0.0,
        cost_usd=sum(case.cost_usd for case in cases),
        prompt_tokens=sum(case.prompt_tokens for case in cases),
        completion_tokens=sum(case.completion_tokens for case in cases),
        latency_p95_ms=percentile([case.latency_ms for case in cases], 95),
        retrieval_recall=(sum(recall_values) / len(recall_values)) if recall_values else None,
        tool_match=(sum(tool_values) / len(tool_values)) if tool_values else None,
    )


def _baseline_summary(baseline: EvalRun | None, target_name: str) -> TargetSummary | None:
    if baseline is None:
        return None
    for target in baseline.targets:
        if target.name == target_name:
            return target.summary
    return None


def _assistant_message(completion: Completion) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": completion.text or None,
        "tool_calls": [
            {
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, sort_keys=True),
                },
            }
            for call in completion.tool_calls
        ],
    }


def _read_prompt(path: Path) -> str:
    if not path.is_file():
        raise EvalError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def _build_target_provider(target: TargetConfig, config_dir: Path) -> MockProvider | OpenAIProvider:
    if target.provider == "mock":
        return MockProvider(_load_fixtures(target.fixtures, config_dir, target.name), target.name)
    return _openai_provider(target.api_key_env, target.base_url)


def _build_judge(config: EvalConfig, config_dir: Path) -> MockProvider | OpenAIProvider:
    judge = config.judge
    if judge.rubric_version not in {"v1"}:
        raise EvalError(f"unknown judge rubric {judge.rubric_version}")
    if judge.provider == "mock":
        return MockProvider(_load_fixtures(judge.fixtures, config_dir, judge.fixture_target), judge.fixture_target)
    return _openai_provider(judge.api_key_env, judge.base_url)


def _load_fixtures(relative: str | None, config_dir: Path, label: str) -> dict[str, Any]:
    if not relative:
        raise EvalError(f"{label} mock provider requires fixtures")
    path = resolve_path(config_dir, relative)
    if not path.is_file():
        raise EvalError(f"fixtures not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalError(f"fixtures are not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise EvalError(f"fixtures must be a JSON object: {path}")
    return payload


def _openai_provider(api_key_env: str, base_url: str | None) -> OpenAIProvider:
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise EvalError(f"missing API key in {api_key_env}")
    return OpenAIProvider(api_key=api_key, base_url=base_url or "https://api.openai.com/v1")
