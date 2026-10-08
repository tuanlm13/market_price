import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.collectors.models import FactRawListing, FactRawComment
from app.normalization.models import (
    FactNormalizedListing, FactNormalizedComment, NormalizationAuditLog
)
from app.normalization.pipeline import NormalizationPipeline
from app.normalization.schemas import ReviewUpdateRequest
from app.normalization.providers.factory import get_ai_provider

logger = logging.getLogger(__name__)

def process_batch_listings(db: Session, limit: int = 50) -> Dict[str, int]:
    """Processes unnormalized raw listings."""
    pipeline = NormalizationPipeline(db)

    # Subquery of already normalized listing IDs
    normalized_subquery = db.query(FactNormalizedListing.raw_listing_id)
    unnormalized = (
        db.query(FactRawListing)
        .filter(~FactRawListing.id.in_(normalized_subquery))
        .limit(limit)
        .all()
    )

    processed_count = 0
    review_count = 0

    for raw in unnormalized:
        try:
            norm = pipeline.normalize_listing(raw)
            processed_count += 1
            if norm.manual_review_required:
                review_count += 1
        except Exception as e:
            db.rollback()
            logger.error(f"Error normalizing raw_listing_id={raw.id}: {e}", exc_info=True)

    return {
        "scanned": len(unnormalized),
        "processed": processed_count,
        "review_required": review_count
    }

def process_batch_comments(db: Session, limit: int = 50) -> Dict[str, int]:
    """Processes unnormalized raw comments."""
    pipeline = NormalizationPipeline(db)

    normalized_subquery = db.query(FactNormalizedComment.raw_comment_id)
    unnormalized = (
        db.query(FactRawComment)
        .filter(~FactRawComment.id.in_(normalized_subquery))
        .limit(limit)
        .all()
    )

    processed_count = 0
    for c in unnormalized:
        try:
            pipeline.normalize_comment(c)
            processed_count += 1
        except Exception as e:
            logger.error(f"Error normalizing comment id={c.id}: {e}", exc_info=True)

    return {
        "scanned": len(unnormalized),
        "processed": processed_count
    }

def get_review_queue(db: Session, limit: int = 50) -> List[FactNormalizedListing]:
    """Retrieves normalized listings flagged for manual review."""
    return (
        db.query(FactNormalizedListing)
        .filter(FactNormalizedListing.manual_review_required == True)
        .order_by(FactNormalizedListing.normalized_at.desc())
        .limit(limit)
        .all()
    )

def apply_manual_correction(
    db: Session,
    normalized_id: int,
    data: ReviewUpdateRequest
) -> FactNormalizedListing:
    """
    Applies manual correction to a normalized listing and logs every change into NormalizationAuditLog.
    NEVER mutates the underlying raw listing source of truth.
    """
    norm = db.query(FactNormalizedListing).filter(FactNormalizedListing.id == normalized_id).first()
    if not norm:
        raise ValueError(f"Normalized listing with id={normalized_id} not found.")

    def log_change(field: str, old_val: Any, new_val: Any):
        if str(old_val) != str(new_val):
            audit = NormalizationAuditLog(
                normalized_listing_id=norm.id,
                field_name=field,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(new_val) if new_val is not None else None,
                corrected_by=data.reviewer,
                reason=data.reason
            )
            db.add(audit)

    if data.product_id is not None:
        log_change("product_id", norm.product_id, data.product_id)
        norm.product_id = data.product_id

    if data.variant_id is not None:
        log_change("variant_id", norm.variant_id, data.variant_id)
        norm.variant_id = data.variant_id

    if data.condition_id is not None:
        log_change("condition_id", norm.condition_id, data.condition_id)
        norm.condition_id = data.condition_id

    if data.normalized_price is not None:
        log_change("normalized_price", norm.normalized_price, data.normalized_price)
        norm.normalized_price = data.normalized_price

    if data.price_valid is not None:
        log_change("price_valid", norm.price_valid, data.price_valid)
        norm.price_valid = data.price_valid

    if data.classification is not None:
        log_change("classification", norm.classification, data.classification)
        norm.classification = data.classification

    log_change("manual_review_required", norm.manual_review_required, data.manual_review_required)
    norm.manual_review_required = data.manual_review_required
    norm.pipeline_stage = "MANUAL"
    norm.ai_confidence = 1.0

    db.commit()
    db.refresh(norm)
    return norm

def get_normalization_metrics(db: Session) -> Dict[str, Any]:
    """Calculates normalization pipeline metrics and cost stats."""
    total_raw = db.query(func.count(FactRawListing.id)).scalar() or 0
    total_norm = db.query(func.count(FactNormalizedListing.id)).scalar() or 0

    rule_stages = ["DETERMINISTIC", "DICTIONARY", "REGEX", "FUZZY"]
    rule_only = (
        db.query(func.count(FactNormalizedListing.id))
        .filter(FactNormalizedListing.pipeline_stage.in_(rule_stages))
        .scalar() or 0
    )

    ai_processed = (
        db.query(func.count(FactNormalizedListing.id))
        .filter(FactNormalizedListing.pipeline_stage == "AI")
        .scalar() or 0
    )

    failed = (
        db.query(func.count(FactNormalizedListing.id))
        .filter(
            (FactNormalizedListing.product_id.is_(None)) |
            (FactNormalizedListing.price_valid == False)
        )
        .scalar() or 0
    )

    review_required = (
        db.query(func.count(FactNormalizedListing.id))
        .filter(FactNormalizedListing.manual_review_required == True)
        .scalar() or 0
    )

    avg_conf = db.query(func.avg(FactNormalizedListing.ai_confidence)).scalar() or 0.0

    provider = get_ai_provider()
    p_metrics = provider.get_metrics()

    return {
        "total_raw_listings": total_raw,
        "total_normalized_listings": total_norm,
        "rule_only": rule_only,
        "ai_processed": ai_processed,
        "failed": failed,
        "review_required": review_required,
        "avg_confidence": round(float(avg_conf), 3),
        "tokens_cost_usd": p_metrics.get("cost_usd", 0.0),
        "active_ai_provider": provider.provider_name
    }
