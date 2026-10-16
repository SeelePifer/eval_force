import json
from pathlib import Path

from evalforge.errors import EvalError
from evalforge.hashing import dataset_sha256
from evalforge.models import Case, Chunk


def load_authored_cases(path: Path) -> tuple[list[dict], list[Case], str]:
    if not path.is_file():
        raise EvalError(f"dataset not found: {path}")
    authored: list[dict] = []
    text = path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            raw = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise EvalError(f"{path}:{line_number} is not valid JSON") from exc
        if not isinstance(raw, dict):
            raise EvalError(f"{path}:{line_number} must be a JSON object")
        authored.append(raw)
    if not authored:
        raise EvalError(f"dataset is empty: {path}")
    try:
        cases = [Case.model_validate(raw) for raw in authored]
    except ValueError as exc:
        raise EvalError(str(exc)) from exc
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise EvalError("case ids must be unique")
    return authored, cases, dataset_sha256(authored)


def load_corpus(path: Path) -> list[Chunk]:
    if not path.is_file():
        raise EvalError(f"corpus not found: {path}")
    chunks: list[Chunk] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            raw = json.loads(stripped)
            chunks.append(Chunk.model_validate(raw))
        except (json.JSONDecodeError, ValueError) as exc:
            raise EvalError(f"{path}:{line_number} is not a valid chunk") from exc
    if not chunks:
        raise EvalError(f"corpus is empty: {path}")
    ids = [chunk.id for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise EvalError(f"chunk ids must be unique: {path}")
    return chunks
