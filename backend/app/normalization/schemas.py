from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

# ==============================================================================
# STRUCTURED LLM / AI OUTPUT SCHEMAS
# ==============================================================================

class AIListingNormalizationResult(BaseModel):
    """
    Validated structured output from AI Provider for listing normalization.
    Free-text responses are rejected; only validated fields are accepted.
    """
    canonical_product_name: Optional[str] = Field(None, description="Matched or suggested canonical product name")
    brand_name: Optional[str] = Field(None, description="Extracted brand name (e.g. Apple, Nvidia, Sony)")
    variant_attributes: Dict[str, Any] = Field(default_factory=dict, description="Extracted variant attributes like storage, ram, color")
    condition_code: Optional[str] = Field(None, description="Mapped condition code (e.g. NEW_SEAL, LIKE_NEW_99)")
    classification: str = Field(
        default="SELL",
        description="Intent classification: SELL, BUY, WANTED, SERVICE, ACCESSORY, PARTS, SPAM, UNKNOWN"
    )
    clean_price_amount: Optional[float] = Field(None, description="Parsed numeric price")
    currency: str = Field(default="VND", description="Detected or default currency")
    price_valid: bool = Field(default=True, description="True if price is genuine, False if placeholder/inbox/deposit")
    price_validity_reason: Optional[str] = Field(None, description="Reason if price is invalid")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Overall extraction confidence score (0.0 - 1.0)")
    manual_review_required: bool = Field(default=False, description="Flag if human verification is needed")
    reasoning: Optional[str] = Field(None, description="Brief explanation from AI provider")


class AICommentClassificationResult(BaseModel):
    """
    Validated structured output from AI Provider for comment classification.
    """
    classification: str = Field(
        description="Comment classification: NEGOTIATION, SELLER_PRICE, COMPETING_OFFER, SOLD_SIGNAL, PRICE_REFERENCE, WTB, NOISE"
    )
    extracted_price: Optional[float] = Field(None, description="Numeric price offered or referenced in comment")
    currency: str = Field(default="VND", description="Currency of the extracted price")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")


# ==============================================================================
# API REQUEST & RESPONSE SCHEMAS
# ==============================================================================

class ReviewItemResponse(BaseModel):
    id: int
    raw_listing_id: int
    raw_title: str
    raw_description: Optional[str]
    raw_price_text: Optional[str]
    product_id: Optional[int]
    product_name: Optional[str]
    variant_id: Optional[int]
    condition_id: Optional[int]
    condition_code: Optional[str]
    normalized_price: Optional[float]
    currency: str
    price_valid: bool
    price_validity_reason: Optional[str]
    classification: str
    ai_confidence: float
    pipeline_stage: str
    manual_review_required: bool
    normalized_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReviewUpdateRequest(BaseModel):
    product_id: Optional[int] = None
    variant_id: Optional[int] = None
    condition_id: Optional[int] = None
    normalized_price: Optional[float] = None
    price_valid: Optional[bool] = None
    classification: Optional[str] = None
    manual_review_required: bool = False
    reviewer: str = Field(default="manual_reviewer")
    reason: Optional[str] = Field(None, description="Reason for correction")


class NormalizationMetricsResponse(BaseModel):
    total_raw_listings: int
    total_normalized_listings: int
    rule_only: int
    ai_processed: int
    failed: int
    review_required: int
    avg_confidence: float
    tokens_cost_usd: float = 0.0
    active_ai_provider: str
