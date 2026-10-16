import re
from collections import Counter

from evalforge.models import Chunk

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def lexical_retrieve(query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
    if top_k <= 0:
        return []
    query_counts = Counter(tokenize(query))
    scored: list[tuple[int, str, Chunk]] = []
    for chunk in chunks:
        chunk_counts = Counter(tokenize(chunk.text))
        score = sum(query_counts[token] * chunk_counts[token] for token in query_counts)
        scored.append((score, chunk.id, chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for score, _, chunk in scored if score > 0][:top_k]


def retrieval_recall(expected_ids: list[str], retrieved_ids: list[str]) -> float:
    expected = set(expected_ids)
    if not expected:
        return 1.0
    return len(expected & set(retrieved_ids)) / len(expected)
