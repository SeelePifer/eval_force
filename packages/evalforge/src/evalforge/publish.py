from pathlib import Path

import httpx

from evalforge.dataset import load_authored_cases
from evalforge.errors import EvalError
from evalforge.models import EvalRun
from evalforge.runner import resolve_path


def dataset_name_from_path(path: Path) -> str:
    if path.name == "cases.jsonl":
        return path.parent.name
    return path.stem


def publish_run(
    *,
    api_url: str,
    api_key: str,
    dataset_path: Path,
    run: EvalRun,
    report_html: str,
) -> str:
    authored, _cases, digest = load_authored_cases(dataset_path)
    if digest != run.manifest.dataset_sha256:
        raise EvalError("results dataset hash does not match the dataset file")
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(base_url=api_url.rstrip("/"), headers=headers, timeout=30) as client:
        dataset_response = client.post(
            "/v1/datasets",
            json={"name": dataset_name_from_path(dataset_path), "cases": authored},
        )
        _raise_for_status(dataset_response, "dataset publish failed")
        run_response = client.post(
            "/v1/runs",
            json={
                "dataset_sha256": run.manifest.dataset_sha256,
                "manifest": run.manifest.model_dump(),
                "results": run.model_dump(),
                "report_html": report_html,
                "passed": run.passed,
            },
        )
        _raise_for_status(run_response, "run publish failed")
        payload = run_response.json()
    run_id = payload.get("id")
    if not isinstance(run_id, str):
        raise EvalError("publish response did not include a run id")
    return run_id


def resolve_dataset(config_dir: Path, dataset: str) -> Path:
    return resolve_path(config_dir, dataset)


def _raise_for_status(response: httpx.Response, label: str) -> None:
    if response.status_code < 400:
        return
    detail = response.text.strip().replace("\n", " ")[:300]
    raise EvalError(f"{label}: HTTP {response.status_code} {detail}")
