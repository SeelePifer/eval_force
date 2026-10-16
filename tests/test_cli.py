from pathlib import Path

from evalforge.cli import main
from evalforge.report import render_report
from evalforge.runner import execute_run, load_config

ROOT = Path(__file__).parents[1]


def test_report_states_the_gate_verdict() -> None:
    config, config_dir = load_config(ROOT / "examples" / "ci" / "evalforge.yaml")
    run = execute_run(config=config, config_dir=config_dir, baseline_path=None)
    html = render_report(run)
    assert "Gate passed" in html
    assert "support-v1" in html
    assert run.manifest.dataset_sha256 in html


def test_cli_fails_when_quality_cannot_clear_the_floor(tmp_path: Path) -> None:
    config = f"""
dataset: {(ROOT / "datasets" / "evalforge-qa-v1" / "cases.jsonl").as_posix()}
pricing: {(ROOT / "examples" / "ci" / "pricing.yaml").as_posix()}
seed: 0
temperature: 0
top_k: 2
gate:
  quality_min: 1.1
  quality_drop_max: 0.05
  cost_increase_max: 0.2
  latency_p95_ms: 4000
targets:
  - name: support-v1
    provider: mock
    model: mock-small
    prompt: {(ROOT / "examples" / "ci" / "prompts" / "v1.txt").as_posix()}
    fixtures: {(ROOT / "examples" / "ci" / "fixtures.json").as_posix()}
"""
    path = tmp_path / "evalforge.yaml"
    path.write_text(config, encoding="utf-8")
    out_dir = tmp_path / "out"
    code = main(["run", "--config", str(path), "--out-dir", str(out_dir)])
    assert code == 1
    assert "Gate failed" in (out_dir / "evalforge-report.html").read_text(encoding="utf-8")


def test_example_cli_matches_the_published_baseline(tmp_path: Path) -> None:
    code = main(
        [
            "run",
            "--config",
            str(ROOT / "examples" / "ci" / "evalforge.yaml"),
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert code == 0
    assert (tmp_path / "evalforge-results.json").is_file()
