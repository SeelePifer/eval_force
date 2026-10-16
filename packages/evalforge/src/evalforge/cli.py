import argparse
import os
import sys
from pathlib import Path

from evalforge.compare import load_run
from evalforge.errors import EvalError
from evalforge.publish import publish_run, resolve_dataset
from evalforge.report import render_report
from evalforge.runner import execute_run, load_config, resolve_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evalforge")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run_parser = subcommands.add_parser("run", help="Evaluate a dataset and write JSON plus HTML")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--baseline", default=None)
    run_parser.add_argument("--out-dir", default="out")

    publish_parser = subcommands.add_parser("publish", help="Store a finished run in the EvalForge API")
    publish_parser.add_argument("--config", required=True)
    publish_parser.add_argument("--results", required=True)
    publish_parser.add_argument("--report", default=None)
    publish_parser.add_argument("--api-url", default=os.environ.get("EVALFORGE_API_URL"))
    publish_parser.add_argument("--api-key", default=os.environ.get("EVALFORGE_API_KEY"))

    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        return _publish(args)
    except EvalError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    config, config_dir = load_config(config_path)
    baseline_value = args.baseline if args.baseline is not None else config.baseline
    baseline_path = resolve_path(config_dir, baseline_value) if baseline_value else None
    run = execute_run(config=config, config_dir=config_dir, baseline_path=baseline_path)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = Path.cwd() / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "evalforge-results.json"
    report_path = out_dir / "evalforge-report.html"
    results_path.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(run), encoding="utf-8")
    print(f"passed={str(run.passed).lower()} results={results_path} report={report_path}")
    return 0 if run.passed else 1


def _publish(args: argparse.Namespace) -> int:
    if not args.api_url or not args.api_key:
        raise EvalError("publish requires --api-url and --api-key, or EVALFORGE_API_URL and EVALFORGE_API_KEY")
    config, config_dir = load_config(Path(args.config))
    results_path = Path(args.results)
    report_path = Path(args.report) if args.report else results_path.with_name("evalforge-report.html")
    if not report_path.is_file():
        raise EvalError(f"report not found: {report_path}")
    run = load_run(results_path)
    run_id = publish_run(
        api_url=args.api_url,
        api_key=args.api_key,
        dataset_path=resolve_dataset(config_dir, config.dataset),
        run=run,
        report_html=report_path.read_text(encoding="utf-8"),
    )
    print(run_id)
    return 0
