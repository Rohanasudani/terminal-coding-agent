from __future__ import annotations

from dataclasses import dataclass

from .models import TokenUsage


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok_usd: float
    output_per_mtok_usd: float


MODEL_PRICES: dict[str, ModelPrice] = {
    "gpt-5.6-sol": ModelPrice(input_per_mtok_usd=4.00, output_per_mtok_usd=20.00),
    "gpt-5.6": ModelPrice(input_per_mtok_usd=4.00, output_per_mtok_usd=20.00),
    "gpt-5.6-terra": ModelPrice(input_per_mtok_usd=2.00, output_per_mtok_usd=12.00),
    "gpt-5.6-luna": ModelPrice(input_per_mtok_usd=0.20, output_per_mtok_usd=1.20),
}


def estimate_cost_usd(model: str, usage: TokenUsage) -> float:
    price = MODEL_PRICES.get(model)
    if not price:
        return 0.0

    input_cost = usage.input_tokens / 1_000_000 * price.input_per_mtok_usd
    output_cost = usage.output_tokens / 1_000_000 * price.output_per_mtok_usd
    return round(input_cost + output_cost, 6)
