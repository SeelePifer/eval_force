from evalforge.gate import evaluate_gate, percentile
from evalforge.models import GateConfig, TargetSummary


def _summary(**overrides: float) -> TargetSummary:
    values = {
        "quality": 0.9,
        "cost_usd": 1.0,
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "latency_p95_ms": 100,
    }
    values.update(overrides)
    return TargetSummary(**values)


def test_percentile_uses_nearest_rank() -> None:
    assert percentile([100, 110, 120, 130, 140, 170], 95) == 170


def test_gate_passes_when_quality_holds_and_cost_is_flat() -> None:
    gate = GateConfig()
    verdict = evaluate_gate(_summary(), _summary(), gate, target_name="support-v1")
    assert verdict.passed


def test_gate_blocks_quality_drop_cost_increase_and_latency() -> None:
    gate = GateConfig(quality_min=0.8, quality_drop_max=0.05, cost_increase_max=0.2, latency_p95_ms=1000)
    current = _summary(quality=0.7, cost_usd=1.5, latency_p95_ms=1500)
    verdict = evaluate_gate(current, _summary(), gate, target_name="support-v1")
    codes = {reason.code for reason in verdict.reasons}
    assert codes == {"quality_below_min", "quality_drop", "cost_increase", "latency_above_max"}
    assert not verdict.passed


def test_gate_fails_when_the_baseline_has_no_matching_target() -> None:
    verdict = evaluate_gate(_summary(), None, GateConfig(), target_name="support-v3", baseline_missing=True)
    assert [reason.code for reason in verdict.reasons] == ["baseline_target_missing"]
    assert not verdict.passed


def test_gate_blocks_cost_when_baseline_was_free() -> None:
    verdict = evaluate_gate(
        _summary(cost_usd=0.01),
        _summary(cost_usd=0),
        GateConfig(),
        target_name="support-v1",
    )
    assert [reason.code for reason in verdict.reasons] == ["cost_increase"]
