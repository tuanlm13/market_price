import re
from typing import Optional, Dict, Any
from app.normalization.providers.base import AIProvider
from app.normalization.schemas import AIListingNormalizationResult, AICommentClassificationResult
from app.normalization.rules.price_parser import parse_price
from app.normalization.rules.condition_mapper import map_condition
from app.normalization.rules.classification_rules import classify_listing_intent
from app.normalization.rules.comment_rules import classify_comment_intent

class MockAIProvider(AIProvider):
    """
    Mock AI Provider for local testing and unit tests.
    Does not require external network or API keys.
    Validates output through Pydantic schemas.
    """
    provider_name: str = "mock"

    def __init__(self):
        self.call_count = 0
        self.tokens_prompt = 0
        self.tokens_completion = 0

    def normalize_listing(
        self,
        title: str,
        description: str = "",
        raw_price_text: Optional[str] = None,
        raw_currency: str = "VND"
    ) -> AIListingNormalizationResult:
        self.call_count += 1
        self.tokens_prompt += 120
        self.tokens_completion += 80

        full_text = f"{title} {description}".lower()

        # Heuristic product detection
        canonical_name = None
        brand = None
        if "iphone 16 pro max" in full_text or "ip 16 prm" in full_text:
            canonical_name = "iPhone 16 Pro Max"
            brand = "Apple"
        elif "iphone 16" in full_text or "ip16" in full_text or "ip 16" in full_text or "苹果16" in full_text:
            canonical_name = "iPhone 16"
            brand = "Apple"
        elif "rtx 4060" in full_text:
            canonical_name = "GeForce RTX 4060"
            brand = "Nvidia"
        elif "wh-1000xm5" in full_text or "xm5" in full_text:
            canonical_name = "Sony WH-1000XM5"
            brand = "Sony"

        # Attributes
        attrs = {}
        if "128gb" in full_text or "128g" in full_text:
            attrs["storage"] = "128GB"
        elif "256gb" in full_text or "256g" in full_text:
            attrs["storage"] = "256GB"
        elif "512gb" in full_text or "512g" in full_text:
            attrs["storage"] = "512GB"

        if "desert" in full_text:
            attrs["color"] = "Desert Titanium"
        elif "black" in full_text or "đen" in full_text:
            attrs["color"] = "Black"

        # Price parsing
        price_val, curr, is_valid, invalid_reason = parse_price(raw_price_text or title, default_currency=raw_currency)

        # Condition
        cond_code, cond_conf, manual_review = map_condition(full_text)

        # Classification
        classification, _ = classify_listing_intent(title, description)

        confidence = 0.88 if canonical_name else 0.60
        manual_review_needed = manual_review or (confidence < 0.75) or not is_valid

        return AIListingNormalizationResult(
            canonical_product_name=canonical_name,
            brand_name=brand,
            variant_attributes=attrs,
            condition_code=cond_code,
            classification=classification,
            clean_price_amount=price_val,
            currency=curr,
            price_valid=is_valid,
            price_validity_reason=invalid_reason,
            confidence=confidence,
            manual_review_required=manual_review_needed,
            reasoning=f"Mock AI extracted product={canonical_name}, valid_price={is_valid}"
        )

    def classify_comment(
        self,
        raw_text: str
    ) -> AICommentClassificationResult:
        self.call_count += 1
        self.tokens_prompt += 50
        self.tokens_completion += 30

        cls, extracted_price, conf = classify_comment_intent(raw_text)
        return AICommentClassificationResult(
            classification=cls,
            extracted_price=extracted_price,
            currency="VND",
            confidence=conf
        )

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "call_count": self.call_count,
            "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion,
            "cost_usd": 0.0
        }
