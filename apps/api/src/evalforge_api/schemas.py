from typing import Any

from pydantic import BaseModel, Field


class DatasetIn(BaseModel):
    name: str = Field(min_length=1)
    cases: list[dict[str, Any]] = Field(min_length=1)


class RunIn(BaseModel):
    dataset_sha256: str = Field(min_length=64, max_length=64)
    manifest: dict[str, Any]
    results: dict[str, Any]
    report_html: str
    passed: bool


class CompareIn(BaseModel):
    run_id: str
    target_a: str
    target_b: str
