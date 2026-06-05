"""
XinMate — Prompt Builder
=========================
Generates varied prompts for each persona × category × variation.
"""

import random
from typing import Tuple
from config import (
    PersonaConfig,
    CATEGORIES,
    CATEGORY_SCENARIOS,
    MOODS,
    NEGATIVE_PROMPT,
    FULL_BODY_NEGATIVE_EXTRA,
)


def build_prompt(
    persona: PersonaConfig,
    category: str,
    image_index: int,
) -> Tuple[str, str, dict]:
    """
    Build a unique prompt for a persona + category + image index.

    Returns:
        (positive_prompt, negative_prompt, metadata_dict)
    """
    cat_cfg = CATEGORIES[category]
    scenarios = CATEGORY_SCENARIOS[category]

    # Deterministic variation based on index
    scenario = scenarios[image_index % len(scenarios)]
    mood = MOODS[image_index % len(MOODS)]

    # Build positive prompt
    parts = [
        persona.base_prompt,
        mood,
        scenario,
        cat_cfg["prompt_suffix"],
    ]
    positive = ", ".join(parts)

    # Build negative prompt
    negative = NEGATIVE_PROMPT
    if category == "full_body":
        negative = f"{negative}, {FULL_BODY_NEGATIVE_EXTRA}"

    # Metadata for DB import
    meta = {
        "category": cat_cfg["db_category"],
        "mood": mood,
        "scenario": scenario,
        "tags": persona.tags + [category, mood.split()[0]],
        "isNsfw": False,
    }

    return positive, negative, meta


def get_seed(persona: PersonaConfig, category: str, image_index: int) -> int:
    """Deterministic seed per persona + category + index."""
    cat_keys = list(CATEGORIES.keys())
    cat_offset = cat_keys.index(category) * 1000
    return persona.seed_base + cat_offset + image_index


def get_dimensions(category: str) -> Tuple[int, int]:
    """Get width × height for a category."""
    return CATEGORIES[category]["dimensions"]
