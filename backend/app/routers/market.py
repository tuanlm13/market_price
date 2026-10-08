from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from database import get_db
from app.market.service import (
    get_market_analytics, get_product_explorer_hierarchy,
    get_paginated_raw_listings, get_data_quality_and_operations
)
from app.taxonomy.models import DimCondition

router = APIRouter(prefix="/market", tags=["Market Intelligence Engine"])

@router.get("/analytics")
def get_market_analytics_endpoint(
    product_id: Optional[int] = Query(None),
    variant_id: Optional[int] = Query(None),
    condition_id: Optional[int] = Query(None),
    source_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db)
):
    """
    Computes percentiles (P10-P90), fair price, quick sell, histogram, source comparison, and trends.
    """
    return get_market_analytics(
        db,
        product_id=product_id,
        variant_id=variant_id,
        condition_id=condition_id,
        source_id=source_id,
        days=days
    )

@router.get("/explorer")
def get_product_explorer_endpoint(db: Session = Depends(get_db)):
    """Returns Category -> Brand -> Model -> Variant taxonomy hierarchy."""
    return get_product_explorer_hierarchy(db)

@router.get("/listings")
def get_market_listings_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    product_id: Optional[int] = Query(None),
    condition_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Paginated raw evidence listings joined with normalized data."""
    return get_paginated_raw_listings(
        db,
        page=page,
        page_size=page_size,
        product_id=product_id,
        condition_id=condition_id
    )

@router.get("/quality")
def get_data_quality_endpoint(db: Session = Depends(get_db)):
    """Quality and Operations monitoring metrics."""
    return get_data_quality_and_operations(db)

@router.get("/conditions")
def get_conditions_endpoint(db: Session = Depends(get_db)):
    """List of all condition taxonomy grades."""
    conditions = db.query(DimCondition).order_by(DimCondition.id.asc()).all()
    return [{"id": c.id, "code": c.code, "name": c.name, "grade": c.grade} for c in conditions]
