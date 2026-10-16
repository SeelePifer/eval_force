from evalforge.scorers import answer_scores, case_quality, token_f1


def test_exact_answer_scores_one() -> None:
    scores = answer_scores("  Refunds Are Allowed Within 30 Days. ", "refunds are allowed within 30 days.")
    assert scores["normalized_exact"] == 1
    assert scores["contains"] == 1
    assert scores["token_f1"] == 1
    assert scores["answer_quality"] == 1


def test_token_f1_partial_overlap() -> None:
    score = token_f1("30 days", "the refund window is 30 days")
    assert score == 0.5


def test_case_quality_averages_retrieval_and_tools() -> None:
    assert case_quality(1.0, 0.5, 0.0) == 0.5
