"""Model-specific configurations for Marshall speakers."""

from __future__ import annotations

from typing import Final

# Model names as they appear in the device
MODEL_ACTON_II: Final = "Acton II"
MODEL_ACTON_III: Final = "Acton III"
MODEL_STANMORE_II: Final = "Stanmore II"
MODEL_STANMORE_III: Final = "Stanmore III"
MODEL_WOBURN_III: Final = "Woburn III"

# Features per model
MODEL_FEATURES: dict[str, dict[str, bool]] = {
    MODEL_ACTON_II: {
        "rca_input": False,
        "led_brightness": True,
        "bluetooth": True,
        "aux_input": True,
        "eq": False,
        "interaction_sounds": True,
    },
    MODEL_ACTON_III: {
        "rca_input": False,
        "led_brightness": True,
        "bluetooth": True,
        "aux_input": True,
        "eq": True,
        "interaction_sounds": True,
    },
    MODEL_STANMORE_II: {
        "rca_input": True,
        "led_brightness": True,
        "bluetooth": True,
        "aux_input": True,
        "eq": True,
        "interaction_sounds": True,
    },
    MODEL_STANMORE_III: {
        "rca_input": True,
        "led_brightness": True,
        "bluetooth": True,
        "aux_input": True,
        "eq": True,
        "interaction_sounds": True,
    },
    MODEL_WOBURN_III: {
        "rca_input": True,
        "led_brightness": True,
        "bluetooth": True,
        "aux_input": True,
        "eq": True,
        "interaction_sounds": True,
    },
}

# Default features for unknown models (conservative approach)
DEFAULT_MODEL_FEATURES: dict[str, bool] = {
    "rca_input": True,
    "led_brightness": True,
    "bluetooth": True,
    "aux_input": True,
    "eq": False,
    "interaction_sounds": True,
}


def get_model_features(model: str | None) -> dict[str, bool]:
    """Get features supported by a specific model."""
    if model is None:
        return DEFAULT_MODEL_FEATURES.copy()

    # Try exact match first
    if model in MODEL_FEATURES:
        return MODEL_FEATURES[model].copy()

    # Try partial match, longest model name first so "Acton III" beats "Acton II"
    for known_model, features in sorted(
        MODEL_FEATURES.items(), key=lambda kv: len(kv[0]), reverse=True
    ):
        if known_model.lower() in model.lower():
            return features.copy()

    # Default to assuming all features are available for unknown models
    return DEFAULT_MODEL_FEATURES.copy()
