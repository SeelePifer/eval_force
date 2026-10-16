import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dataset_sha256(cases: list[Any], corpora: dict[str, list[Any]] | None = None) -> str:
    payload = canonical_json({"cases": cases, "corpora": corpora or {}})
    return sha256_text(payload)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def prompt_sha256(text: str) -> str:
    return sha256_text(normalize_newlines(text))
