from pathlib import Path

from evalforge.dataset import load_corpus
from evalforge.rag import lexical_retrieve, retrieval_recall

ROOT = Path(__file__).parents[1]
CORPUS = ROOT / "datasets" / "evalforge-qa-v1" / "corpus.jsonl"


def test_recall_is_fraction_of_expected_chunks() -> None:
    assert retrieval_recall(["a", "b"], ["b", "c"]) == 0.5
    assert retrieval_recall([], []) == 1


def test_public_corpus_retrieves_the_expected_chunks() -> None:
    chunks = load_corpus(CORPUS)
    refund = lexical_retrieve("What is the refund window for a return?", chunks, top_k=2)
    shipping = lexical_retrieve("What is the standard shipping arrival time?", chunks, top_k=2)
    assert refund[0].id == "refund-window"
    assert shipping[0].id == "shipping-sla"
