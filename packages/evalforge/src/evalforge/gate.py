import math

from evalforge.models import GateConfig, GateReason, GateVerdict, TargetSummary

_EPSILON = 1e-12


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil((pct / 100) * len(ordered))
    index = min(max(rank, 1), len(ordered)) - 1
    return ordered[index]


def evaluate_gate(
    summary: TargetSummary,
    baseline: TargetSummary | None,
    gate: GateConfig,
    *,
    target_name: str,
    baseline_missing: bool = False,
) -> GateVerdict:
    reasons: list[GateReason] = []
    if baseline_missing:
        reasons.append(
            GateReason(
                code="baseline_target_missing",
                message=f"{target_name} has no matching target in the baseline",
            )
        )
    if summary.quality + _EPSILON < gate.quality_min:
        reasons.append(
            GateReason(
                code="quality_below_min",
                message=(
                    f"{target_name} quality {summary.quality:.3f} is below the minimum {gate.quality_min:.3f}"
                ),
            )
        )
    if summary.latency_p95_ms > gate.latency_p95_ms + _EPSILON:
        reasons.append(
            GateReason(
                code="latency_above_max",
                message=(
                    f"{target_name} p95 latency {summary.latency_p95_ms:.1f} ms "
                    f"exceeds {gate.latency_p95_ms:.1f} ms"
                ),
            )
        )
    if baseline is not None and not baseline_missing:
        drop = baseline.quality - summary.quality
        if drop > gate.quality_drop_max + _EPSILON:
            reasons.append(
                GateReason(
                    code="quality_drop",
                    message=(
                        f"{target_name} quality dropped by {drop:.3f}, "
                        f"above the allowed {gate.quality_drop_max:.3f}"
                    ),
                )
            )
        if _cost_increased(summary.cost_usd, baseline.cost_usd, gate.cost_increase_max):
            reasons.append(
                GateReason(
                    code="cost_increase",
                    message=(
                        f"{target_name} cost rose from {baseline.cost_usd:.6f} to {summary.cost_usd:.6f}, "
                        f"above the allowed increase of {gate.cost_increase_max:.0%}"
                    ),
                )
            )
    return GateVerdict(passed=not reasons, reasons=reasons)


def _cost_increased(current: float, baseline: float, limit: float) -> bool:
    if baseline == 0:
        return current > 0
    return (current - baseline) / baseline > limit + _EPSILON
