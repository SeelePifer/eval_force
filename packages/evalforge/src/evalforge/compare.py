import json
from pathlib import Path

from evalforge.errors import EvalError
from evalforge.models import EvalRun, TargetResult


def compare_targets(run: EvalRun, target_a: str, target_b: str) -> dict:
    left = _find_target(run, target_a)
    right = _find_target(run, target_b)
    right_by_id = {case.case_id: case for case in right.cases}
    cases = []
    for case in left.cases:
        other = right_by_id.get(case.case_id)
        if other is None:
            raise EvalError(f"case {case.case_id} is missing from target {target_b}")
        cases.append(
            {
                "case_id": case.case_id,
                "quality_a": case.scores.quality,
                "quality_b": other.scores.quality,
                "quality_delta": other.scores.quality - case.scores.quality,
                "cost_a": case.cost_usd,
                "cost_b": other.cost_usd,
                "output_a": case.output,
                "output_b": other.output,
            }
        )
    return {
        "target_a": {"name": left.name, **left.summary.model_dump()},
        "target_b": {"name": right.name, **right.summary.model_dump()},
        "quality_delta": right.summary.quality - left.summary.quality,
        "cost_delta": right.summary.cost_usd - left.summary.cost_usd,
        "latency_p95_delta_ms": right.summary.latency_p95_ms - left.summary.latency_p95_ms,
        "cases": cases,
    }


def load_run(path: Path) -> EvalRun:
    if not path.is_file():
        raise EvalError(f"results not found: {path}")
    try:
        return EvalRun.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValueError) as exc:
        raise EvalError(f"invalid results file {path}: {exc}") from exc


def _find_target(run: EvalRun, name: str) -> TargetResult:
    for target in run.targets:
        if target.name == name:
            return target
    known = ", ".join(target.name for target in run.targets)
    raise EvalError(f"target {name} was not found. Known targets: {known}")
