from pathlib import Path

import yaml

from evalforge.errors import EvalError
from evalforge.models import PricingTable


def load_pricing(path: Path) -> PricingTable:
    if not path.is_file():
        raise EvalError(f"pricing table not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        return PricingTable.model_validate(raw)
    except ValueError as exc:
        raise EvalError(f"invalid pricing table: {exc}") from exc


def cost_usd(pricing: PricingTable, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = pricing.models.get(model)
    if price is None:
        known = ", ".join(sorted(pricing.models)) or "(none)"
        raise EvalError(f"model {model} is missing from pricing {pricing.version}. Known models: {known}")
    input_cost = prompt_tokens * price.input_per_million / 1_000_000
    output_cost = completion_tokens * price.output_per_million / 1_000_000
    return input_cost + output_cost
