import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.collectors.models import FactRawListing, FactRawComment
from app.taxonomy.models import DimProduct, DimVariant, DimCondition, DimMarketSegment
from app.normalization.models import FactNormalizedListing, FactNormalizedComment
from app.normalization.rules.price_parser import parse_price
from app.normalization.rules.classification_rules import classify_listing_intent
from app.normalization.rules.condition_mapper import map_condition
from app.normalization.rules.alias_matcher import match_product_and_variant
from app.normalization.rules.comment_rules import classify_comment_intent
from app.normalization.providers.factory import get_ai_provider

logger = logging.getLogger(__name__)

NORMALIZATION_VERSION = "v1.0.0"

class NormalizationPipeline:
    """
    Tiered Normalization Pipeline:
    deterministic rules -> dictionary -> regex -> fuzzy match -> AI provider
    Items resolved in early tiers DO NOT call AI (saving cost and latency).
    """

    def __init__(self, db: Session):
        self.db = db
        self.ai_provider = get_ai_provider()

    def normalize_listing(self, raw_listing: FactRawListing) -> FactNormalizedListing:
        """
        Executes pipeline on a single FactRawListing and creates/updates FactNormalizedListing.
        """
        raw_title = raw_listing.raw_title or ""
        raw_desc = raw_listing.raw_description or ""
        full_text = f"{raw_title} {raw_desc}"

        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # STEP 1: DETERMINISTIC RULES & REGEX
        # -------------------------------------------------------------
        clean_price, currency, price_valid, invalid_reason = parse_price(
            raw_listing.raw_price_text or raw_title,
            default_currency=raw_listing.raw_currency or "VND"
        )

        classification, intent_conf = classify_listing_intent(raw_title, raw_desc)
        cond_code, cond_conf, cond_review_needed = map_condition(full_text)

        # -------------------------------------------------------------
        # STEP 2: DICTIONARY & EXACT ALIAS MATCHING
        # -------------------------------------------------------------
        product, variant, prod_conf, stage, attrs = match_product_and_variant(
            raw_title, self.db, raw_desc
        )

        manual_review = False
        pipeline_stage = stage
        overall_conf = 1.0

        # Nếu classification là ACCESSORY, PARTS, SERVICE, SPAM, BUY -> Tuyệt đối không gán thiết bị chính
        if classification in ("ACCESSORY", "PARTS", "SERVICE", "SPAM", "BUY", "WANTED"):
            product = None
            variant = None

        # If product resolved via dictionary or deterministic rules with high confidence
        if product and stage in ("DICTIONARY", "DETERMINISTIC"):
            overall_conf = round((intent_conf * 0.3) + (prod_conf * 0.5) + (cond_conf * 0.2), 2)
            if not price_valid or cond_review_needed:
                manual_review = True

        # -------------------------------------------------------------
        # STEP 3: FUZZY MATCH CHECK
        # -------------------------------------------------------------
        elif product and stage == "FUZZY" and prod_conf >= 0.82:
            overall_conf = round(prod_conf * 0.8, 2)
            if overall_conf < 0.75 or not price_valid:
                manual_review = True

        # -------------------------------------------------------------
        # STEP 4: AI FALLBACK (Only for unresolved or low confidence items!)
        # -------------------------------------------------------------
        elif not product and classification not in ("ACCESSORY", "PARTS", "SERVICE", "SPAM"):
            logger.info(f"[Pipeline] Fallback to AI Provider for listing id={raw_listing.id} ('{raw_title[:40]}')")
            ai_res = self.ai_provider.normalize_listing(
                title=raw_title,
                description=raw_desc,
                raw_price_text=raw_listing.raw_price_text,
                raw_currency=raw_listing.raw_currency or "VND"
            )
            pipeline_stage = "AI"
            overall_conf = ai_res.confidence
            classification = ai_res.classification

            if ai_res.clean_price_amount is not None:
                clean_price = ai_res.clean_price_amount
                price_valid = ai_res.price_valid
                invalid_reason = ai_res.price_validity_reason

            if ai_res.condition_code:
                cond_code = ai_res.condition_code

            attrs = {**attrs, **ai_res.variant_attributes}
            manual_review = ai_res.manual_review_required or (overall_conf < 0.75) or not price_valid

            # Try to resolve canonical product suggested by AI (nếu không phải là ACCESSORY/PARTS)
            if ai_res.canonical_product_name and classification not in ("ACCESSORY", "PARTS", "SERVICE", "SPAM"):
                from app.normalization.rules.alias_matcher import is_spec_compatible
                suggested_clean = ai_res.canonical_product_name.lower().strip()
                matched_p = (
                    self.db.query(DimProduct)
                    .filter(
                        (DimProduct.name.ilike(f"%{suggested_clean}%")) |
                        (DimProduct.slug == suggested_clean)
                    )
                    .first()
                )
                if matched_p and is_spec_compatible(matched_p, full_text):
                    product = matched_p
                    if product.variants:
                        variant = product.variants[0]

        # -------------------------------------------------------------
        # STEP 4.5: SANITY FLOOR BOUND & PRICE ANOMALY GUARD
        # -------------------------------------------------------------
        if product and clean_price and price_valid and currency == "VND":
            p_name_lower = (product.name or "").lower()
            # iPhone: Không có chiếc iPhone đời mới nào (15, 16) giá dưới 5.000.000đ mà hoàn chỉnh hoạt động
            if ("iphone 16" in p_name_lower or "iphone 15" in p_name_lower) and clean_price < 5_000_000.0:
                price_valid = False
                invalid_reason = "UNREALISTIC_LOW_PRICE"
            elif "rtx 4060" in p_name_lower and clean_price < 2_500_000.0:
                price_valid = False
                invalid_reason = "UNREALISTIC_LOW_PRICE"
            elif "ddr5" in p_name_lower and clean_price < 400_000.0:
                price_valid = False
                invalid_reason = "UNREALISTIC_LOW_PRICE"

            # Check thêm từ khóa trả góp lách luật trong bài đăng điện thoại có giá < 8 triệu
            if "iphone" in p_name_lower and clean_price < 8_000_000.0:
                import re
                if re.search(r"\b(góp|trả trước|đưa trước|hồ sơ|cccd|nợ xấu)\b", full_text.lower()):
                    price_valid = False
                    invalid_reason = "INSTALLMENT_TEASER"

        # -------------------------------------------------------------
        # STEP 5: RESOLVE TAXONOMY FOREIGN KEYS (Condition & Market Segment)
        # -------------------------------------------------------------
        condition_record = None
        if cond_code:
            from app.normalization.rules.condition_mapper import CODE_ALIASES
            resolved_code = CODE_ALIASES.get(cond_code.upper(), cond_code.upper())
            condition_record = self.db.query(DimCondition).filter(DimCondition.code == resolved_code).first()

        market_seg_id = None
        if variant and condition_record:
            m_seg = (
                self.db.query(DimMarketSegment)
                .filter(
                    DimMarketSegment.variant_id == variant.id,
                    DimMarketSegment.condition_id == condition_record.id
                )
                .first()
            )
            if m_seg:
                market_seg_id = m_seg.id

        # -------------------------------------------------------------
        # STEP 6: PERSIST TO fact_normalized_listing
        # -------------------------------------------------------------
        existing_norm = (
            self.db.query(FactNormalizedListing)
            .filter(FactNormalizedListing.raw_listing_id == raw_listing.id)
            .first()
        )

        if existing_norm:
            existing_norm.product_id = product.id if product else None
            existing_norm.variant_id = variant.id if variant else None
            existing_norm.condition_id = condition_record.id if condition_record else None
            existing_norm.market_segment_id = market_seg_id
            existing_norm.normalized_price = clean_price
            existing_norm.currency = currency
            existing_norm.price_valid = price_valid
            existing_norm.price_validity_reason = invalid_reason
            existing_norm.normalized_attributes = attrs
            existing_norm.classification = classification
            existing_norm.ai_confidence = overall_conf
            existing_norm.pipeline_stage = pipeline_stage
            existing_norm.normalization_version = NORMALIZATION_VERSION
            existing_norm.manual_review_required = manual_review
            existing_norm.normalized_at = datetime.utcnow()
            norm_record = existing_norm
        else:
            norm_record = FactNormalizedListing(
                raw_listing_id=raw_listing.id,
                product_id=product.id if product else None,
                variant_id=variant.id if variant else None,
                condition_id=condition_record.id if condition_record else None,
                market_segment_id=market_seg_id,
                normalized_price=clean_price,
                currency=currency,
                price_valid=price_valid,
                price_validity_reason=invalid_reason,
                normalized_attributes=attrs,
                classification=classification,
                ai_confidence=overall_conf,
                pipeline_stage=pipeline_stage,
                normalization_version=NORMALIZATION_VERSION,
                manual_review_required=manual_review
            )
            self.db.add(norm_record)

        self.db.commit()
        self.db.refresh(norm_record)
        return norm_record

    def normalize_comment(self, raw_comment: FactRawComment) -> FactNormalizedComment:
        """Normalizes and classifies a single FactRawComment."""
        cls, price, conf = classify_comment_intent(raw_comment.raw_text)

        existing = (
            self.db.query(FactNormalizedComment)
            .filter(FactNormalizedComment.raw_comment_id == raw_comment.id)
            .first()
        )
        if existing:
            existing.classification = cls
            existing.extracted_price = price
            existing.ai_confidence = conf
            existing.normalized_at = datetime.utcnow()
            norm_c = existing
        else:
            norm_c = FactNormalizedComment(
                raw_comment_id=raw_comment.id,
                classification=cls,
                extracted_price=price,
                currency="VND",
                ai_confidence=conf
            )
            self.db.add(norm_c)

        self.db.commit()
        self.db.refresh(norm_c)
        return norm_c
