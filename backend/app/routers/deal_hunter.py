import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database import get_db
from app.deal_hunter.models import FactDealAppraisal
from app.deal_hunter.service import DealHunterService
from app.deal_hunter.telegram_provider import TelegramNotificationProvider
from app.normalization.models import FactNormalizedListing
from app.collectors.models import FactRawListing
from app.taxonomy.models import DimProduct

router = APIRouter(prefix="/deals", tags=["deal-hunter"])
logger = logging.getLogger(__name__)

deal_service = DealHunterService()

@router.post("/hunt")
def trigger_deal_hunter(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Quét và thẩm định các listing mới chưa được đánh giá."""
    try:
        results = deal_service.hunt_unappraised_listings(db, limit=limit)
        return {"status": "success", "summary": results}
    except Exception as e:
        logger.error(f"Lỗi khi chạy Deal Hunter: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/appraise/{listing_id}")
def appraise_single_listing(
    listing_id: int,
    force_alert: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Thẩm định thủ công một listing đã chuẩn hóa theo ID."""
    appraisal = deal_service.appraise_listing_by_id(db, listing_id, force_alert=force_alert)
    if not appraisal:
        raise HTTPException(status_code=404, detail="Listing không tồn tại hoặc không đủ điều kiện thẩm định")
    
    return {
        "status": "success",
        "appraisal": {
            "id": appraisal.id,
            "normalized_listing_id": appraisal.normalized_listing_id,
            "decision": appraisal.decision,
            "asking_price": float(appraisal.asking_price),
            "acquisition_cost": float(appraisal.acquisition_cost),
            "quick_sell_price": float(appraisal.quick_sell_price),
            "expected_profit": float(appraisal.expected_profit),
            "roi": appraisal.roi,
            "market_position": appraisal.market_position,
            "market_confidence": appraisal.market_confidence,
            "liquidity": appraisal.liquidity,
            "reason": appraisal.ai_reasoning,
            "risks": appraisal.risks,
            "alert_sent": appraisal.alert_sent,
            "alert_sent_at": appraisal.alert_sent_at,
            "created_at": appraisal.created_at
        }
    }

@router.get("")
def list_deals(
    decision: Optional[str] = Query(None, description="Lọc theo BUY, WATCH, SKIP"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Danh sách các cơ hội đầu tư và kết quả thẩm định."""
    query = (
        db.query(FactDealAppraisal, FactNormalizedListing, FactRawListing, DimProduct)
        .join(FactNormalizedListing, FactDealAppraisal.normalized_listing_id == FactNormalizedListing.id)
        .join(FactRawListing, FactNormalizedListing.raw_listing_id == FactRawListing.id)
        .outerjoin(DimProduct, FactNormalizedListing.product_id == DimProduct.id)
    )

    if decision:
        query = query.filter(FactDealAppraisal.decision == decision.upper().strip())

    total = query.count()
    records = query.order_by(desc(FactDealAppraisal.created_at)).offset(skip).limit(limit).all()

    items = []
    for app, norm, raw, prod in records:
        items.append({
            "id": app.id,
            "listing_id": norm.id,
            "product_name": prod.name if prod else raw.raw_title,
            "title": raw.raw_title,
            "decision": app.decision,
            "asking_price": float(app.asking_price),
            "acquisition_cost": float(app.acquisition_cost),
            "quick_sell_price": float(app.quick_sell_price),
            "expected_profit": float(app.expected_profit),
            "roi": app.roi,
            "market_position": app.market_position,
            "market_confidence": app.market_confidence,
            "liquidity": app.liquidity,
            "alert_sent": app.alert_sent,
            "alert_sent_at": app.alert_sent_at,
            "created_at": app.created_at,
            "url": raw.url,
            "reason": app.ai_reasoning,
            "risks": app.risks
        })

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items
    }

@router.get("/stats")
def get_deal_stats(db: Session = Depends(get_db)):
    """Thống kê tổng hợp hoạt động của Deal Hunter."""
    total_appraisals = db.query(FactDealAppraisal).count()
    buy_count = db.query(FactDealAppraisal).filter(FactDealAppraisal.decision == "BUY").count()
    watch_count = db.query(FactDealAppraisal).filter(FactDealAppraisal.decision == "WATCH").count()
    skip_count = db.query(FactDealAppraisal).filter(FactDealAppraisal.decision == "SKIP").count()
    alerts_sent = db.query(FactDealAppraisal).filter(FactDealAppraisal.alert_sent == True).count()

    return {
        "total_appraisals": total_appraisals,
        "buy_count": buy_count,
        "watch_count": watch_count,
        "skip_count": skip_count,
        "alerts_sent": alerts_sent
    }

@router.post("/test-telegram")
def test_telegram_connection(
    chat_id: Optional[str] = None
):
    """Kiểm tra kết nối và gửi thông báo thử nghiệm tới Telegram."""
    provider = TelegramNotificationProvider()
    test_data = {
        "product_name": "iPhone 13 128GB (TEST ALERT)",
        "variant_name": "128GB VN/A",
        "condition": "LIKE_NEW (99%)",
        "source": "Chợ Tốt",
        "asking_price": 10500000,
        "acquisition_cost": 10560000,
        "p10": 11500000,
        "p25": 12000000,
        "median": 12800000,
        "quick_sell_price": 11800000,
        "expected_profit": 1240000,
        "roi": 0.1174,
        "market_confidence": 92,
        "liquidity": 85,
        "reason": "Kèo thơm thử nghiệm: Giá rẻ hơn P10 thị trường 1tr đ.",
        "risks": ["Test Alert Verification"],
        "url": "https://www.chotot.com"
    }

    ok = provider.send_deal_alert(test_data, chat_id=chat_id)
    return {
        "status": "success" if ok else "failed",
        "mock_mode": provider.mock_mode,
        "chat_id_used": chat_id or provider.default_chat_id or "Not configured"
    }
