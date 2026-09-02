from termagent.models import TokenUsage
from termagent.pricing import estimate_cost_usd


def test_estimate_cost_for_known_model():
    cost = estimate_cost_usd(
        "gpt-5.6-luna",
        TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000),
    )

    assert cost == 1.4


def test_unknown_model_cost_is_zero_but_safe():
    assert estimate_cost_usd("custom-model", TokenUsage(input_tokens=10, output_tokens=10)) == 0.0
