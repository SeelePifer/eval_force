import asyncio
import json
import os
from pathlib import Path

import asyncpg
import pytest
from fastapi.testclient import TestClient

from evalforge.dataset import load_authored_cases

ROOT = Path(__file__).parents[1]


@pytest.fixture
def client() -> TestClient:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL is not set")
    os.environ["EVALFORGE_API_KEY"] = "test-key"
    from evalforge_api.main import app

    with TestClient(app) as test_client:
        asyncio.run(_truncate())
        yield test_client


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_publish_list_report_and_compare(client: TestClient) -> None:
    denied = client.get("/v1/runs")
    assert denied.status_code == 401
    headers = {"Authorization": "Bearer test-key"}
    cases, _parsed, corpora, _digest = load_authored_cases(ROOT / "datasets" / "evalforge-qa-v1" / "cases.jsonl")
    created = client.post(
        "/v1/datasets",
        headers=headers,
        json={"name": "evalforge-qa-v1", "cases": cases, "corpora": corpora},
    )
    assert created.status_code == 200
    digest = created.json()["sha256"]
    again = client.post(
        "/v1/datasets",
        headers=headers,
        json={"name": "evalforge-qa-v1", "cases": cases, "corpora": corpora},
    )
    assert again.json()["sha256"] == digest

    from evalforge.cli import main

    out_dir = ROOT / "out" / "api-test"
    code = main(
        ["run", "--config", str(ROOT / "examples" / "ci" / "evalforge.yaml"), "--out-dir", str(out_dir)]
    )
    assert code == 0
    results = json.loads((out_dir / "evalforge-results.json").read_text(encoding="utf-8"))
    report = (out_dir / "evalforge-report.html").read_text(encoding="utf-8")
    stored = client.post(
        "/v1/runs",
        headers=headers,
        json={
            "dataset_sha256": digest,
            "manifest": results["manifest"],
            "results": results,
            "report_html": report,
            "passed": results["passed"],
        },
    )
    assert stored.status_code == 200
    run_id = stored.json()["id"]

    listing = client.get("/v1/runs", headers=headers)
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == run_id
    assert listing.json()[0]["targets"][0]["quality"] == 1

    detail = client.get(f"/v1/runs/{run_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["results"]["passed"] is True

    html = client.get(f"/v1/runs/{run_id}/report.html", headers=headers)
    assert html.status_code == 200
    assert "Gate passed" in html.text

    compared = client.post(
        "/v1/compare",
        headers=headers,
        json={"run_id": run_id, "target_a": "support-v1", "target_b": "support-v2"},
    )
    assert compared.status_code == 200
    body = compared.json()
    assert body["cost_delta"] > 0
    assert body["quality_delta"] == 0
    assert len(body["cases"]) == 6

    lied = client.post(
        "/v1/runs",
        headers=headers,
        json={
            "dataset_sha256": digest,
            "manifest": results["manifest"],
            "results": results,
            "report_html": report,
            "passed": not results["passed"],
        },
    )
    assert lied.status_code == 422


async def _truncate() -> None:
    connection = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        await connection.execute("TRUNCATE runs, datasets")
    finally:
        await connection.close()
