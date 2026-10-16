import json
from pathlib import Path

import pytest

from evalforge.errors import EvalError
from evalforge.models import EvalConfig
from evalforge.runner import execute_run, load_config

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "examples" / "ci" / "evalforge.yaml"


def test_mock_run_scores_retrieval_and_tools() -> None:
    config, config_dir = load_config(CONFIG)
    run = execute_run(config=config, config_dir=config_dir, baseline_path=None)
    assert run.passed
    assert run.manifest.pricing_version == "2026-01"
    assert run.manifest.seed == 0
    assert run.manifest.temperature == 0
    first = run.targets[0]
    by_id = {case.case_id: case for case in first.cases}
    assert by_id["rag-refund"].retrieved_chunk_ids[0] == "refund-window"
    assert by_id["rag-refund"].scores.retrieval_recall == 1
    assert by_id["rag-shipping"].retrieved_chunk_ids[0] == "shipping-sla"
    tool_case = by_id["tool-refund-policy"]
    assert tool_case.scores.tool_match == 1
    assert tool_case.tool_calls[0].arguments == {"topic": "refund"}
    assert tool_case.scores.quality == 1
    assert first.summary.quality == 1
    assert {target.name for target in run.targets} == {"support-v1", "support-v2"}
    assert run.targets[0].summary.cost_usd < run.targets[1].summary.cost_usd


def test_optional_judge_is_stored_apart_from_quality(tmp_path: Path) -> None:
    config, config_dir = load_config(CONFIG)
    fixtures = {
        "judge": {
            case_id: {"text": '{"score": 0.25}', "prompt_tokens": 4, "completion_tokens": 4, "latency_ms": 5}
            for case_id in [
                "qa-refund-window",
                "qa-shipping-sla",
                "qa-support-email",
                "rag-refund",
                "rag-shipping",
                "tool-refund-policy",
            ]
        }
    }
    fixture_path = tmp_path / "judge.json"
    fixture_path.write_text(__import__("json").dumps(fixtures), encoding="utf-8")
    judged = config.model_copy(
        update={
            "judge": config.judge.model_copy(
                update={"enabled": True, "provider": "mock", "fixtures": str(fixture_path), "rubric_version": "v1"}
            )
        }
    )
    run = execute_run(config=judged, config_dir=config_dir, baseline_path=None)
    assert isinstance(judged, EvalConfig)
    sample = run.targets[0].cases[0]
    assert sample.judge_score == 0.25
    assert sample.scores.quality == 1
    assert run.manifest.judge_rubric_version == "v1"


def test_baseline_must_use_the_same_dataset(tmp_path: Path) -> None:
    config, config_dir = load_config(CONFIG)
    run = execute_run(config=config, config_dir=config_dir, baseline_path=None)
    payload = run.model_dump()
    payload["manifest"]["dataset_sha256"] = "0" * 64
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EvalError, match="baseline dataset hash"):
        execute_run(config=config, config_dir=config_dir, baseline_path=baseline)


def test_renamed_target_fails_the_baseline_gate(tmp_path: Path) -> None:
    config, config_dir = load_config(CONFIG)
    run = execute_run(config=config, config_dir=config_dir, baseline_path=None)
    payload = run.model_dump()
    payload["targets"] = [target for target in payload["targets"] if target["name"] != "support-v1"]
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(payload), encoding="utf-8")
    gated = execute_run(config=config, config_dir=config_dir, baseline_path=baseline)
    missing = next(target for target in gated.targets if target.name == "support-v1")
    assert not gated.passed
    assert any(reason.code == "baseline_target_missing" for reason in missing.gate.reasons)
