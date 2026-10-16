import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from evalforge.compare import compare_targets
from evalforge.errors import EvalError
from evalforge.hashing import dataset_sha256
from evalforge.models import Case, EvalRun
from evalforge_api.auth import require_bearer
from evalforge_api.schemas import CompareIn, DatasetIn, RunIn

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/v1/datasets", dependencies=[Depends(require_bearer)])
async def create_dataset(payload: DatasetIn, request: Request) -> dict[str, str]:
    try:
        for case in payload.cases:
            Case.model_validate(case)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    digest = dataset_sha256(payload.cases)
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            INSERT INTO datasets (id, name, sha256, cases)
            VALUES ($1, $2, $3, $4::jsonb)
            ON CONFLICT (sha256) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            uuid4(),
            payload.name,
            digest,
            json.dumps(payload.cases),
        )
    return {"id": str(row["id"]), "sha256": digest}


@router.post("/v1/runs", dependencies=[Depends(require_bearer)])
async def create_run(payload: RunIn, request: Request) -> dict[str, str]:
    try:
        run = EvalRun.model_validate(payload.results)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if run.manifest.dataset_sha256 != payload.dataset_sha256:
        raise HTTPException(status_code=422, detail="dataset hash does not match the results manifest")
    pool: asyncpg.Pool = request.app.state.pool
    run_id = uuid4()
    async with pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO runs (id, dataset_sha256, manifest, results, report_html, passed)
            VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6)
            """,
            run_id,
            payload.dataset_sha256,
            json.dumps(payload.manifest),
            json.dumps(run.model_dump()),
            payload.report_html,
            payload.passed,
        )
    return {"id": str(run_id)}


@router.get("/v1/runs", dependencies=[Depends(require_bearer)])
async def list_runs(request: Request, limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT id, dataset_sha256, passed, created_at, results
            FROM runs
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [_summary(row) for row in rows]


@router.get("/v1/runs/{run_id}", dependencies=[Depends(require_bearer)])
async def get_run(run_id: str, request: Request) -> dict[str, Any]:
    row = await _fetch_run(request, run_id)
    return {
        "id": str(row["id"]),
        "dataset_sha256": row["dataset_sha256"],
        "passed": row["passed"],
        "created_at": _iso(row["created_at"]),
        "results": _json(row["results"]),
    }


@router.get("/v1/runs/{run_id}/report.html", dependencies=[Depends(require_bearer)])
async def get_report(run_id: str, request: Request) -> HTMLResponse:
    row = await _fetch_run(request, run_id)
    return HTMLResponse(row["report_html"])


@router.post("/v1/compare", dependencies=[Depends(require_bearer)])
async def compare(payload: CompareIn, request: Request) -> dict[str, Any]:
    row = await _fetch_run(request, payload.run_id)
    try:
        run = EvalRun.model_validate(_json(row["results"]))
        return compare_targets(run, payload.target_a, payload.target_b)
    except EvalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _fetch_run(request: Request, run_id: str) -> asyncpg.Record:
    try:
        parsed = UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid id") from exc
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as connection:
        row = await connection.fetchrow("SELECT * FROM runs WHERE id = $1", parsed)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return row


def _summary(row: asyncpg.Record) -> dict[str, Any]:
    results = _json(row["results"])
    return {
        "id": str(row["id"]),
        "dataset_sha256": row["dataset_sha256"],
        "passed": row["passed"],
        "created_at": _iso(row["created_at"]),
        "targets": [
            {
                "name": target["name"],
                "model": target["model"],
                "quality": target["summary"]["quality"],
                "cost_usd": target["summary"]["cost_usd"],
                "latency_p95_ms": target["summary"]["latency_p95_ms"],
                "prompt_tokens": target["summary"]["prompt_tokens"],
                "completion_tokens": target["summary"]["completion_tokens"],
            }
            for target in results["targets"]
        ],
    }


def _json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _iso(value: datetime) -> str:
    return value.isoformat()
