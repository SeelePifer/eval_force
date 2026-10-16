from typing import Any

from evalforge.hashing import canonical_json
from evalforge.models import Case, ExpectedCall


def arguments_match(actual: dict[str, Any], subset: dict[str, Any]) -> bool:
    return all(actual.get(key) == expected for key, expected in subset.items())


def tool_match_score(expected_calls: list[ExpectedCall], actual_calls: list[tuple[str, dict[str, Any]]]) -> float:
    if not expected_calls and not actual_calls:
        return 1.0
    if not expected_calls or not actual_calls:
        return 0.0
    matched = 0
    for expected, actual in zip(expected_calls, actual_calls, strict=False):
        name, arguments = actual
        if expected.name == name and arguments_match(arguments, expected.arguments_subset):
            matched += 1
    return matched / max(len(expected_calls), len(actual_calls))


def stub_lookup_key(arguments: dict[str, Any]) -> str:
    if len(arguments) == 1:
        return str(next(iter(arguments.values())))
    return canonical_json(arguments)


def execute_stub(case: Case, name: str, arguments: dict[str, Any]) -> str:
    table = case.tool_stubs.get(name)
    if table is None:
        return "stub not found"
    return table.get(stub_lookup_key(arguments), "stub not found")


def tool_schemas(case: Case) -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for name in case.tool_stubs:
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"Fixture tool {name}",
                    "parameters": {"type": "object", "additionalProperties": True},
                },
            }
        )
    return schemas
