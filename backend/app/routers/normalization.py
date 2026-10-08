from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from database import get_db
from app.normalization.service import (
    process_batch_listings, process_batch_comments,
    get_review_queue, apply_manual_correction, get_normalization_metrics
)
from app.normalization.schemas import (
    ReviewItemResponse, ReviewUpdateRequest, NormalizationMetricsResponse
)
from app.normalization.models import FactNormalizedListing

router = APIRouter(prefix="/normalization", tags=["AI Product Normalization & Classification"])

@router.get("/metrics", response_model=NormalizationMetricsResponse)
def get_metrics_endpoint(db: Session = Depends(get_db)):
    """
    Returns pipeline performance metrics:
    rule_only, ai_processed, failed, review_required, avg_confidence, tokens/cost.
    """
    return get_normalization_metrics(db)

@router.post("/process")
def process_normalization_batch(
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Triggers batch normalization on unnormalized raw listings and comments.
    """
    res_listings = process_batch_listings(db, limit=limit)
    res_comments = process_batch_comments(db, limit=limit)
    return {
        "status": "COMPLETED",
        "listings": res_listings,
        "comments": res_comments
    }

@router.get("/review")
def get_review_queue_endpoint(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Retrieves listings flagged for manual human review (low confidence, ambiguous condition, invalid price).
    """
    items = get_review_queue(db, limit=limit)
    results = []
    for item in items:
        raw = item.raw_listing
        results.append({
            "id": item.id,
            "raw_listing_id": item.raw_listing_id,
            "raw_title": raw.raw_title if raw else "",
            "raw_description": raw.raw_description if raw else "",
            "raw_price_text": raw.raw_price_text if raw else "",
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else None,
            "variant_id": item.variant_id,
            "condition_id": item.condition_id,
            "condition_code": item.condition.code if item.condition else None,
            "normalized_price": float(item.normalized_price) if item.normalized_price is not None else None,
            "currency": item.currency,
            "price_valid": item.price_valid,
            "price_validity_reason": item.price_validity_reason,
            "classification": item.classification,
            "ai_confidence": item.ai_confidence,
            "pipeline_stage": item.pipeline_stage,
            "manual_review_required": item.manual_review_required,
            "normalized_at": item.normalized_at
        })
    return results

@router.post("/review/{id}")
def submit_manual_correction(
    id: int,
    data: ReviewUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Submits manual correction for a normalized listing.
    Logs every field modification into NormalizationAuditLog without modifying raw source.
    """
    try:
        updated = apply_manual_correction(db, id, data)
        return {
            "status": "SUCCESS",
            "message": f"Successfully updated normalized listing {id} with audit tracking.",
            "data": {
                "id": updated.id,
                "product_id": updated.product_id,
                "variant_id": updated.variant_id,
                "condition_id": updated.condition_id,
                "normalized_price": float(updated.normalized_price) if updated.normalized_price is not None else None,
                "price_valid": updated.price_valid,
                "classification": updated.classification,
                "manual_review_required": updated.manual_review_required,
                "pipeline_stage": updated.pipeline_stage
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply correction: {str(e)}")

@router.get("/listings")
def get_normalized_listings(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Returns recently normalized listings."""
    items = (
        db.query(FactNormalizedListing)
        .order_by(FactNormalizedListing.normalized_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for item in items:
        raw = item.raw_listing
        results.append({
            "id": item.id,
            "raw_listing_id": item.raw_listing_id,
            "raw_title": raw.raw_title if raw else "",
            "product_name": item.product.name if item.product else None,
            "variant_name": item.variant.name if item.variant else None,
            "condition_code": item.condition.code if item.condition else None,
            "normalized_price": float(item.normalized_price) if item.normalized_price is not None else None,
            "currency": item.currency,
            "price_valid": item.price_valid,
            "price_validity_reason": item.price_validity_reason,
            "classification": item.classification,
            "pipeline_stage": item.pipeline_stage,
            "ai_confidence": item.ai_confidence,
            "manual_review_required": item.manual_review_required,
            "normalized_at": item.normalized_at
        })
    return results
