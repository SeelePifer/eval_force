from evalforge.models import ExpectedCall
from evalforge.tool_calls import execute_stub, tool_match_score
from evalforge.models import Case


def test_tool_match_requires_order_and_argument_subset() -> None:
    expected = [ExpectedCall(name="lookup_policy", arguments_subset={"topic": "refund"})]
    assert tool_match_score(expected, [("lookup_policy", {"topic": "refund", "extra": 1})]) == 1
    assert tool_match_score(expected, [("lookup_policy", {"topic": "shipping"})]) == 0
    assert tool_match_score(expected, [("lookup_policy", {"topic": "refund"}), ("other", {})]) == 0.5


def test_missing_stub_does_not_raise() -> None:
    case = Case(
        id="tool-1",
        type="tools",
        input="Look up the refund policy.",
        expected="Refunds are allowed within 30 days.",
        expected_calls=[ExpectedCall(name="lookup_policy", arguments_subset={"topic": "refund"})],
        tool_stubs={"lookup_policy": {"refund": "Refunds are allowed within 30 days."}},
    )
    assert execute_stub(case, "lookup_policy", {"topic": "refund"}) == "Refunds are allowed within 30 days."
    assert execute_stub(case, "missing", {}) == "stub not found"
