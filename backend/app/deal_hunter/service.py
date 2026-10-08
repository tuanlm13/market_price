import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.normalization.models import FactNormalizedListing
from app.collectors.models import FactRawListing
from app.taxonomy.models import DimProduct, DimVariant, DimCondition, DimSource
from app.market.service import get_market_analytics
from .models import FactDealAppraisal
from .appraiser import DealAppraiser
from .comment_appraiser import analyze_comments
from .telegram_provider import TelegramNotificationProvider
from .schemas import DealAppraisalOutput

logger = logging.getLogger(__name__)

class DealHunterService:
    def __init__(self, telegram_provider: Optional[TelegramNotificationProvider] = None):
        self.telegram = telegram_provider or TelegramNotificationProvider()
        self.appraiser = DealAppraiser()

    def appraise_listing_by_id(
        self,
        db: Session,
        normalized_listing_id: int,
        force_alert: bool = False
    ) -> Optional[FactDealAppraisal]:
        """
        Thẩm định 1 listing đã chuẩn hóa:
        1. Lấy thông tin listing & raw metadata.
        2. Truy vấn Market Intelligence Engine để lấy P10, P25, Median, Quick Sell, v.v.
        3. Phân tích comments (nếu có) để tìm effective seller price.
        4. Thẩm định qua DealAppraiser (Rule Engine First + Risk Analysis).
        5. Kiểm tra Deduplication.
        6. Gửi Telegram nếu đáng mua và vượt qua Dedup.
        7. Lưu kết quả vào FactDealAppraisal.
        """
        norm = db.query(FactNormalizedListing).filter(FactNormalizedListing.id == normalized_listing_id).first()
        if not norm or not norm.price_valid or not norm.normalized_price:
            logger.warning(f"Listing {normalized_listing_id} không hợp lệ hoặc thiếu giá để thẩm định.")
            return None

        # CHỈ THẨM ĐỊNH NẾU LÀ TIN BÁN MÁY HOÀN CHỈNH (SELL) VÀ ĐÃ XÁC ĐỊNH ĐƯỢC SẢN PHẨM
        if norm.classification != "SELL" or not norm.product_id:
            logger.info(f"Listing {normalized_listing_id} bị bỏ qua do classification='{norm.classification}' hoặc thiếu product_id.")
            return None

        raw = norm.raw_listing
        if not raw:
            raw = db.query(FactRawListing).filter(FactRawListing.id == norm.raw_listing_id).first()

        # BẮT BUỘC: Kiểm tra tin rác / phụ kiện / linh kiện lỗi
        from app.normalization.rules.classification_rules import is_junk_listing, is_relevant_to_keyword
        raw_title = raw.raw_title if raw else ""
        if is_junk_listing(raw_title):
            logger.info(f"Listing {normalized_listing_id} bị bỏ qua do là tin rác/phụ kiện: '{raw_title}'")
            return None

        # 1. Thu thập thông tin sản phẩm và phân loại
        product = db.query(DimProduct).filter(DimProduct.id == norm.product_id).first() if norm.product_id else None
        if not product:
            logger.info(f"Listing {normalized_listing_id} bị bỏ qua do không tìm thấy DimProduct tương ứng.")
            return None

        # BẮT BUỘC: Tiêu đề phải thực sự khớp chính xác với sản phẩm định giá (không nhầm ốp, bản base vs pro max, thế hệ ram)
        if not is_relevant_to_keyword(raw_title, product.name):
            logger.info(f"Listing {normalized_listing_id} ('{raw_title}') không khớp với sản phẩm '{product.name}'. Bỏ qua thẩm định.")
            return None

        variant = db.query(DimVariant).filter(DimVariant.id == norm.variant_id).first() if norm.variant_id else None
        condition = db.query(DimCondition).filter(DimCondition.id == norm.condition_id).first() if norm.condition_id else None
        source = db.query(DimSource).filter(DimSource.id == raw.source_id).first() if (raw and raw.source_id) else None

        category_code = "DEFAULT"
        if product.category:
            category_code = product.category.code if hasattr(product.category, 'code') and product.category.code else product.category.name

        # 2. Truy vấn Market Analytics
        analytics = get_market_analytics(
            db=db,
            product_id=norm.product_id,
            variant_id=norm.variant_id,
            condition_id=norm.condition_id
        )
        overview = analytics.get("overview", {})

        # 3. Phân tích comments nếu có
        comments_payload = []
        if raw and raw.comments:
            for c in raw.comments:
                comments_payload.append({
                    "text": c.raw_text,
                    "author": c.author or "",
                    "is_author": False
                })

        effective_seller_price, sub_candidates = analyze_comments(
            comments=comments_payload,
            seller_identifier=raw.seller_name_raw if raw else None
        )

        effective_price_source = "SELLER_COMMENT" if effective_seller_price else "LISTING_PRICE"
        eval_price = effective_seller_price if effective_seller_price else float(norm.normalized_price)

        # 4. Thực thi thẩm định
        listing_info = {
            "title": raw.raw_title if raw else "N/A",
            "description": raw.raw_description if raw else "",
            "asking_price": float(norm.normalized_price),
            "source": source.name if source else "Marketplace",
            "condition": condition.code if condition else "GOOD",
            "url": raw.url if raw else "#"
        }

        output: DealAppraisalOutput = self.appraiser.appraise(
            listing_data=listing_info,
            market_stats=overview,
            category_code=category_code,
            effective_price=eval_price,
            effective_price_source=effective_price_source,
            comments=comments_payload
        )

        # 5. DEDUPLICATION CHECK
        prev_appraisal = (
            db.query(FactDealAppraisal)
            .filter(FactDealAppraisal.normalized_listing_id == normalized_listing_id)
            .order_by(desc(FactDealAppraisal.created_at))
            .first()
        )

        should_alert = False
        if force_alert:
            should_alert = (output.decision == "BUY")
        elif prev_appraisal and prev_appraisal.alert_sent:
            # Listing đã từng alert trước đây
            prev_asking_price = float(prev_appraisal.asking_price)
            # Alert lại nếu:
            # 1. Significant price drop (>= 5%)
            price_dropped_significantly = eval_price <= (prev_asking_price * 0.95)
            # 2. Có new effective price từ seller comment
            new_seller_effective_price = (effective_price_source == "SELLER_COMMENT" and eval_price < prev_asking_price)
            
            if (price_dropped_significantly or new_seller_effective_price) and output.decision == "BUY":
                logger.info(f"Listing {normalized_listing_id} thỏa điều kiện alert lại: giá giảm từ {prev_asking_price} xuống {eval_price}")
                should_alert = True
            else:
                logger.info(f"Listing {normalized_listing_id} đã được alert trước đó. Bỏ qua duplicate alert.")
                should_alert = False
        else:
            # Chưa từng alert bao giờ
            should_alert = (output.decision == "BUY")

        # 6. Gửi Telegram nếu thỏa mãn
        alert_sent = False
        alert_sent_at = None

        if should_alert:
            deal_msg_payload = {
                "product_name": product.name if product else (raw.raw_title if raw else "Sản phẩm"),
                "variant_name": variant.name if variant else "Tiêu chuẩn",
                "condition": condition.name if condition else (condition.code if condition else "Đã qua sử dụng"),
                "source": source.name if source else "Chợ Tốt",
                "asking_price": output.asking_price,
                "acquisition_cost": output.acquisition_cost,
                "p10": overview.get("p10", 0),
                "p25": overview.get("p25", 0),
                "median": overview.get("median", 0),
                "quick_sell_price": output.quick_sell_price,
                "expected_profit": output.expected_profit,
                "roi": output.roi,
                "market_confidence": output.market_confidence,
                "liquidity": output.liquidity,
                "reason": output.reason,
                "risks": output.risks,
                "url": raw.url if raw else "#",
                "image_url": (raw.raw_metadata.get("image_url") if (raw and isinstance(raw.raw_metadata, dict)) else None)
            }
            alert_sent = self.telegram.send_deal_alert(deal_msg_payload)
            if alert_sent:
                alert_sent_at = datetime.utcnow()

        # 7. Lưu kết quả vào FactDealAppraisal
        appraisal_record = FactDealAppraisal(
            normalized_listing_id=normalized_listing_id,
            decision=output.decision,
            market_confidence=output.market_confidence,
            liquidity=output.liquidity,
            asking_price=output.asking_price,
            acquisition_cost=output.acquisition_cost,
            quick_sell_price=output.quick_sell_price,
            expected_profit=output.expected_profit,
            roi=output.roi,
            discount_vs_median=output.discount_vs_median,
            discount_vs_p25=output.discount_vs_p25,
            discount_vs_quick_sell=output.discount_vs_quick_sell,
            market_position=output.market_position,
            risks=output.risks,
            ai_reasoning=output.reason,
            ai_confidence=output.confidence,
            alert_sent=alert_sent,
            alert_sent_at=alert_sent_at,
            effective_price_source=output.effective_price_source
        )
        db.add(appraisal_record)
        db.commit()
        db.refresh(appraisal_record)

        return appraisal_record

    def hunt_unappraised_listings(self, db: Session, limit: int = 50) -> Dict[str, Any]:
        """
        Quét các listing hợp lệ chưa thẩm định (hoặc mới cập nhật) để thẩm định hàng loạt.
        """
        # Lấy danh sách ID đã thẩm định
        subquery = db.query(FactDealAppraisal.normalized_listing_id).subquery()
        unappraised_listings = (
            db.query(FactNormalizedListing)
            .filter(
                FactNormalizedListing.classification == "SELL",
                FactNormalizedListing.product_id.isnot(None),
                FactNormalizedListing.price_valid == True,
                FactNormalizedListing.normalized_price > 0,
                ~FactNormalizedListing.id.in_(subquery)
            )
            .limit(limit)
            .all()
        )

        results = {
            "scanned": len(unappraised_listings),
            "buys": 0,
            "watches": 0,
            "skips": 0,
            "alerts_sent": 0
        }

        for norm in unappraised_listings:
            rec = self.appraise_listing_by_id(db, norm.id)
            if rec:
                if rec.decision == "BUY":
                    results["buys"] += 1
                elif rec.decision == "WATCH":
                    results["watches"] += 1
                else:
                    results["skips"] += 1

                if rec.alert_sent:
                    results["alerts_sent"] += 1

        return results
