from evalforge.hashing import dataset_sha256, prompt_sha256


def test_dataset_hash_is_stable_for_key_order() -> None:
    first = dataset_sha256([{"b": 1, "a": "north"}])
    second = dataset_sha256([{"a": "north", "b": 1}])
    assert first == second
    assert first != dataset_sha256([{"a": "north", "b": 2}])


def test_corpus_text_changes_the_dataset_hash() -> None:
    cases = [{"id": "rag-1", "corpus": "corpus.jsonl"}]
    original = dataset_sha256(cases, {"corpus.jsonl": [{"id": "refund-window", "text": "30 days"}]})
    changed = dataset_sha256(cases, {"corpus.jsonl": [{"id": "refund-window", "text": "14 days"}]})
    assert original != changed


def test_prompt_hash_ignores_crlf() -> None:
    assert prompt_sha256("Answer\r\nQuestion") == prompt_sha256("Answer\nQuestion")
