from collections import Counter


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def normalized_exact(expected: str, actual: str) -> float:
    return 1.0 if normalize_text(expected) == normalize_text(actual) else 0.0


def contains_score(expected: str, actual: str) -> float:
    expected_norm = normalize_text(expected)
    if not expected_norm:
        return 1.0 if not normalize_text(actual) else 0.0
    return 1.0 if expected_norm in normalize_text(actual) else 0.0


def token_f1(expected: str, actual: str) -> float:
    expected_tokens = normalize_text(expected).split()
    actual_tokens = normalize_text(actual).split()
    if not expected_tokens and not actual_tokens:
        return 1.0
    if not expected_tokens or not actual_tokens:
        return 0.0
    expected_counts = Counter(expected_tokens)
    actual_counts = Counter(actual_tokens)
    overlap = sum((expected_counts & actual_counts).values())
    if overlap == 0:
        return 0.0
    precision = overlap / sum(actual_counts.values())
    recall = overlap / sum(expected_counts.values())
    return 2 * precision * recall / (precision + recall)


def answer_scores(expected: str, actual: str) -> dict[str, float]:
    exact = normalized_exact(expected, actual)
    contains = contains_score(expected, actual)
    f1 = token_f1(expected, actual)
    return {
        "normalized_exact": exact,
        "contains": contains,
        "token_f1": f1,
        "answer_quality": (exact + contains + f1) / 3,
    }


def case_quality(
    answer_quality: float,
    retrieval_recall: float | None = None,
    tool_match: float | None = None,
) -> float:
    parts = [answer_quality]
    if retrieval_recall is not None:
        parts.append(retrieval_recall)
    if tool_match is not None:
        parts.append(tool_match)
    return sum(parts) / len(parts)
