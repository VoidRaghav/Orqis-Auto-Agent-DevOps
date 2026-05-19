"""
Model pricing table.

Prices are per 1 million tokens (input, output) in USD.
Source: official pricing pages as of April 2026.
Returns None if the model is unknown — cost stays null on the event,
which is better than silently showing a wrong number.
"""

from typing import Optional

# (input_cost_per_1m, output_cost_per_1m) in USD
_PRICES: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o":                    (2.50,  10.00),
    "gpt-4o-mini":               (0.15,   0.60),
    "gpt-4-turbo":               (10.00, 30.00),
    "gpt-4":                     (30.00, 60.00),
    "gpt-3.5-turbo":             (0.50,  1.50),
    "o1":                        (15.00, 60.00),
    "o1-mini":                   (3.00,  12.00),
    "o3-mini":                   (1.10,   4.40),
    # Anthropic
    "claude-opus-4-6":           (15.00, 75.00),
    "claude-sonnet-4-6":         (3.00,  15.00),
    "claude-haiku-4-5-20251001": (0.80,   4.00),
    "claude-3-5-sonnet-20241022":(3.00,  15.00),
    "claude-3-5-haiku-20241022": (0.80,   4.00),
    "claude-3-opus-20240229":    (15.00, 75.00),
    # Google
    "gemini-1.5-pro":            (3.50,  10.50),
    "gemini-1.5-flash":          (0.075,  0.30),
    "gemini-2.0-flash":          (0.10,   0.40),
}


def calculate(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """
    Return total cost in USD for a single LLM call, or None if model unknown.
    Normalised model name lookup — strips version suffixes for fuzzy matching.
    """
    key = _resolve(model)
    if key is None:
        return None
    input_price, output_price = _PRICES[key]
    return round(
        (input_tokens * input_price + output_tokens * output_price) / 1_000_000,
        8,
    )


def _resolve(model: str) -> Optional[str]:
    """Find the best matching key in _PRICES for a given model string."""
    model = model.lower().strip()

    # Exact match first
    if model in _PRICES:
        return model

    # Prefix match — handles "gpt-4o-2024-05-13" -> "gpt-4o"
    for key in _PRICES:
        if model.startswith(key):
            return key

    # Substring match — handles "openai/gpt-4o" or "accounts/fireworks/gpt-4o"
    for key in _PRICES:
        if key in model:
            return key

    return None
