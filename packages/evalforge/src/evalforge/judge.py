import json

RUBRIC_V1 = """Rubric-Version: v1
Score how well the answer matches the expected answer on factual content.
Use 1 when the facts match and 0 when they contradict or miss the expected fact.
Return only JSON of the form {{"score": <number from 0 to 1>}}.
Question: {question}
Expected: {expected}
Answer: {answer}
"""

RUBRICS = {"v1": RUBRIC_V1}


def render_rubric(*, version: str, question: str, expected: str, answer: str) -> str:
    template = RUBRICS.get(version)
    if template is None:
        known = ", ".join(sorted(RUBRICS))
        raise ValueError(f"unknown judge rubric {version}. Known rubrics: {known}")
    return template.format(question=question, expected=expected, answer=answer)


def parse_judge_score(text: str) -> float | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    score = payload.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    value = float(score)
    if value < 0 or value > 1:
        return None
    return value
