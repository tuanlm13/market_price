from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from database import get_db
from app.collectors.service import get_all_collector_health, run_collector_job, COLLECTOR_REGISTRY
from app.collectors.models import FactRawListing, FactListingPriceSnapshot, FactRawComment

router = APIRouter(prefix="/collectors", tags=["Raw Market Collectors"])

@router.get("/status")
def get_collectors_status(db: Session = Depends(get_db)):
    """
    Returns the real-time operational and authentication health of all collectors:
    - source
    - status (IDLE, RUNNING, SUCCESS, ERROR, AUTH_REQUIRED, BLOCKED)
    - last_start
    - last_success
    - last_error
    - items_scanned
    - items_new
    - auth_status (OK, LOGIN_REQUIRED, CHECKPOINT)
    """
    return get_all_collector_health(db)

@router.post("/{source_code}/trigger")
def trigger_collector(
    source_code: str,
    background_tasks: BackgroundTasks,
    query: str = Query(""),
    db: Session = Depends(get_db)
):
    code = source_code.upper()
    if code not in COLLECTOR_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collector '{source_code}'. Available: {list(COLLECTOR_REGISTRY.keys())}"
        )

    # Launch background task so API responds immediately
    background_tasks.add_task(run_collector_job, code, query)
    return {
        "status": "TRIGGERED",
        "message": f"Collector {code} started in background with query '{query}'"
    }

@router.get("/listings")
def get_recent_raw_listings(
    source_code: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db)
):
    """View recent raw marketplace listings captured by collectors."""
    query = db.query(FactRawListing).order_by(FactRawListing.last_seen_at.desc())
    if source_code:
        from app.taxonomy.models import DimSource
        src = db.query(DimSource).filter(DimSource.code == source_code.upper()).first()
        if src:
            query = query.filter(FactRawListing.source_id == src.id)

    listings = query.limit(limit).all()
    results = []
    for l in listings:
        results.append({
            "id": l.id,
            "source_id": l.source_id,
            "source_listing_id": l.source_listing_id,
            "url": l.url,
            "raw_title": l.raw_title,
            "raw_price_text": l.raw_price_text,
            "raw_currency": l.raw_currency,
            "seller_name_raw": l.seller_name_raw,
            "location_raw": l.location_raw,
            "published_at": l.published_at,
            "first_seen_at": l.first_seen_at,
            "last_seen_at": l.last_seen_at,
            "snapshots_count": len(l.price_snapshots),
            "comments_count": len(l.comments)
        })
    return results

@router.get("/listings/{listing_id}/comments")
def get_listing_comments(listing_id: int, db: Session = Depends(get_db)):
    """View raw comments for a given listing."""
    comments = (
        db.query(FactRawComment)
        .filter(FactRawComment.listing_id == listing_id)
        .order_by(FactRawComment.first_seen_at.asc())
        .all()
    )
    return [
        {
            "id": c.id,
            "source_comment_id": c.source_comment_id,
            "author": c.author,
            "raw_text": c.raw_text,
            "created_at_source": c.created_at_source,
            "first_seen_at": c.first_seen_at
        }
        for c in comments
    ]
