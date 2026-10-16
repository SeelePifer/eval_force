import json
from pathlib import Path

from evalforge.errors import EvalError
from evalforge.hashing import dataset_sha256
from evalforge.models import Case, Chunk


def load_authored_cases(path: Path) -> tuple[list[dict], list[Case], dict[str, list[dict]], str]:
    authored = _load_objects(
        path,
        missing_label=f"dataset not found: {path}",
        empty_label=f"dataset is empty: {path}",
    )
    try:
        cases = [Case.model_validate(raw) for raw in authored]
    except ValueError as exc:
        raise EvalError(str(exc)) from exc
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise EvalError("case ids must be unique")
    corpora: dict[str, list[dict]] = {}
    for case in cases:
        if not case.corpus or case.corpus in corpora:
            continue
        corpus_path = path.parent / case.corpus
        corpora[case.corpus] = _load_objects(
            corpus_path,
            missing_label=f"corpus not found: {corpus_path}",
            empty_label=f"corpus is empty: {corpus_path}",
        )
    return authored, cases, corpora, dataset_sha256(authored, corpora)


def _load_objects(path: Path, *, missing_label: str, empty_label: str) -> list[dict]:
    if not path.is_file():
        raise EvalError(missing_label)
    authored: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
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
        raise EvalError(empty_label)
    return authored


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
