from typing import Dict, Any, List, Optional
import re

def slugify(text: str) -> str:
    text = text.strip().upper()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text

def generate_canonical_id(
    brand: str,
    product: str,
    spec: str,
    sub_spec: str = "STD",
    condition: str = "N0"
) -> str:
    """
    Format standard: BRAND|PRODUCT|SPEC|SUB_SPEC|CONDITION
    Example:
      APPLE|IPHONE16|128GB|VN-A|N0
      MSI|RTX4060|8GB|GAMING-X|U1
      SAMSUNG|DDR4-ECC|32GB-3200|2RX4|N0
    """
    parts = [
        slugify(brand),
        slugify(product),
        slugify(spec),
        slugify(sub_spec),
        condition.strip().upper()
    ]
    return "|".join(parts)

CATEGORY_SCHEMA_SPECS: Dict[str, Dict[str, Any]] = {
    "SMARTPHONE": {
        "required_keys": ["storage", "region"],
        "optional_keys": [
            "battery_health",
            "warranty",
            "activation_status",
            "repair_history",
            "screen_condition"
        ],
        "default_sub_spec_key": "region",
        "default_spec_key": "storage"
    },
    "GPU": {
        "required_keys": ["vram", "model_series"],
        "optional_keys": [
            "warranty",
            "mining_history",
            "repair_history",
            "fullbox"
        ],
        "default_sub_spec_key": "model_series",
        "default_spec_key": "vram"
    },
    "RAM": {
        "required_keys": ["ddr", "capacity", "frequency"],
        "optional_keys": [
            "ecc",
            "rank",
            "chip",
            "form_factor"  # desktop / laptop / server
        ],
        "default_sub_spec_key": "rank",
        "default_spec_key": "capacity"
    }
}
