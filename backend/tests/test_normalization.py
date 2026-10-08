import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal

from app.normalization.rules.price_parser import parse_price
from app.normalization.rules.classification_rules import classify_listing_intent
from app.normalization.rules.condition_mapper import map_condition
from app.normalization.rules.alias_matcher import match_product_and_variant, extract_variant_attributes
from app.normalization.rules.comment_rules import classify_comment_intent
from app.normalization.providers.mock import MockAIProvider
from app.normalization.pipeline import NormalizationPipeline
from app.collectors.models import FactRawListing, FactRawComment
from app.normalization.models import (
    FactNormalizedListing, FactNormalizedComment, NormalizationAuditLog
)
from app.normalization.service import (
    get_review_queue, apply_manual_correction, get_normalization_metrics
)
from app.normalization.schemas import ReviewUpdateRequest

client = TestClient(app)

# ==============================================================================
# 1. PRICE PARSER & INVALID PRICING TESTS
# ==============================================================================

def test_parse_price_vietnamese_formats():
    # 18tr5 -> 18,500,000 VND
    price, curr, valid, reason = parse_price("18tr5")
    assert valid is True
    assert curr == "VND"
    assert price == 18_500_000.0

    # 18.5tr -> 18,500,000 VND
    price, curr, valid, reason = parse_price("18.5tr")
    assert valid is True
    assert price == 18_500_000.0

    # 18500k -> 18,500,000 VND
    price, curr, valid, reason = parse_price("18500k")
    assert valid is True
    assert price == 18_500_000.0

    # 31.500.000 đ
    price, curr, valid, reason = parse_price("31.500.000 đ")
    assert valid is True
    assert price == 31_500_000.0


def test_parse_price_chinese_formats():
    # 1.85万 -> 18,500 CNY
    price, curr, valid, reason = parse_price("1.85万")
    assert valid is True
    assert curr == "CNY"
    assert price == 18_500.0

    # ¥5000 -> 5000 CNY
    price, curr, valid, reason = parse_price("¥5000")
    assert valid is True
    assert curr == "CNY"
    assert price == 5_000.0

    # 4999元
    price, curr, valid, reason = parse_price("4999元")
    assert valid is True
    assert curr == "CNY"
    assert price == 4_999.0


def test_detect_invalid_and_placeholder_prices():
    # Dummy sequences
    for dummy in ["1đ", "1234đ", "123456đ", "999999đ", "0đ"]:
        price, _, valid, reason = parse_price(dummy)
        assert valid is False
        assert reason == "PLACEHOLDER_PRICE"

    # Inbox / contact required
    for ib in ["giá inbox", "inbox để biết giá", "liên hệ trực tiếp", "thương lượng"]:
        price, _, valid, reason = parse_price(ib)
        assert valid is False
        assert reason == "INBOX_REQUIRED"

    # Installment teaser
    price, _, valid, reason = parse_price("Trả góp chỉ từ 500k")
    assert valid is False
    assert reason == "INSTALLMENT_TEASER"

    # Deposit only
    price, _, valid, reason = parse_price("Cọc trước 200k")
    assert valid is False
    assert reason == "DEPOSIT_ONLY"


# ==============================================================================
# 2. INTENT CLASSIFICATION TESTS
# ==============================================================================

def test_intent_classification():
    assert classify_listing_intent("Pass lại iPhone 16 Pro Max fullbox")[0] == "SELL"
    assert classify_listing_intent("Cần mua RTX 4060 còn bảo hành dài")[0] == "BUY"
    assert classify_listing_intent("Nhận ép kính thay màn iPhone lấy ngay")[0] == "SERVICE"
    assert classify_listing_intent("Ốp lưng da chống sốc iPhone 16")[0] == "ACCESSORY"
    assert classify_listing_intent("Bán xác VGA RTX 4060 lỗi nguồn")[0] == "PARTS"
    assert classify_listing_intent("Hỗ trợ vay tiền tài chính duyệt nhanh")[0] == "SPAM"


# ==============================================================================
# 3. CONDITION TAXONOMY MAPPING TESTS
# ==============================================================================

def test_condition_mapping():
    # NEW_SEAL -> N0
    code, conf, review = map_condition("iPhone 16 Pro Max nguyên seal chưa active")
    assert code == "N0"
    assert conf >= 0.90
    assert review is False

    # LIKE_NEW_99 -> U0
    code, conf, review = map_condition("Máy 99% keng xà beng không tì vết")
    assert code == "U0"
    assert review is False

    # FOR_PARTS -> P0
    code, conf, review = map_condition("Rã xác linh kiện hỏng màn mất nguồn")
    assert code == "P0"
    assert review is False

    # No condition clue -> Do not guess!
    code, conf, review = map_condition("Bán nhanh trong ngày tại Hà Nội")
    assert code is None
    assert review is True


# ==============================================================================
# 4. PRODUCT ALIASES & VARIANT ATTRIBUTES TESTS
# ==============================================================================

def test_product_alias_matching():
    db = SessionLocal()
    try:
        # "ip16", "iphone16", "苹果16" -> iPhone 16
        for alias in ["Bán gấp iphone16 128gb", "Pass lại ip16 màu đen", "转让 苹果16 国行"]:
            product, variant, conf, stage, attrs = match_product_and_variant(alias, db)
            assert product is not None
            assert product.name == "iPhone 16"
            assert stage == "DICTIONARY"

        # Attribute extraction
        attrs = extract_variant_attributes("iPhone 16 Pro Max 256GB Desert Titanium")
        assert attrs.get("storage") == "256GB"
        assert attrs.get("color") == "Desert Titanium"
    finally:
        db.close()


# ==============================================================================
# 5. COMMENT CLASSIFICATION TESTS
# ==============================================================================

def test_comment_classification():
    # Negotiation
    cls, price, conf = classify_comment_intent("Còn fix giá xăng xe không bác?")
    assert cls == "NEGOTIATION"

    # Seller price with parsed amount
    cls, price, conf = classify_comment_intent("Đúng giá 18.5tr không bớt nhé")
    assert cls == "SELLER_PRICE"
    assert price == 18_500_000.0

    # Competing offer
    cls, _, _ = classify_comment_intent("Bên CellphoneS đang bán rẻ hơn kìa")
    assert cls == "COMPETING_OFFER"

    # Sold signal
    cls, _, _ = classify_comment_intent("Hàng đã bay rồi nhé cả nhà")
    assert cls == "SOLD_SIGNAL"

    # WTB
    cls, _, _ = classify_comment_intent("Còn không bạn, cho xin sđt qua xem")
    assert cls == "WTB"


# ==============================================================================
# 6. PIPELINE RESOLUTION & MANUAL REVIEW AUDIT TESTS
# ==============================================================================

def test_pipeline_rule_only_bypasses_ai():
    db = SessionLocal()
    try:
        # Create a raw listing with clear alias and valid price
        raw = FactRawListing(
            source_id=11,  # ChoTot or existing source
            source_listing_id=f"test_pipe_{int(datetime.utcnow().timestamp())}",
            url="https://chotot.com/test.htm",
            raw_title="iPhone 16 128GB nguyên seal chính hãng VN/A",
            raw_description="Máy mới 100% chưa active",
            raw_price_text="19.500.000 đ",
            raw_currency="VND",
            seller_name_raw="Shop Apple",
            location_raw="Hà Nội"
        )
        db.add(raw)
        db.commit()
        db.refresh(raw)

        pipeline = NormalizationPipeline(db)
        norm = pipeline.normalize_listing(raw)

        # High confidence alias item is resolved at DICTIONARY stage without invoking AI
        assert norm.pipeline_stage == "DICTIONARY"
        assert norm.product is not None
        assert norm.product.name == "iPhone 16"
        assert norm.condition.code == "N0"
        assert float(norm.normalized_price) == 19_500_000.0
        assert norm.price_valid is True
        assert norm.manual_review_required is False
    finally:
        db.close()


def test_manual_review_audit_preserves_raw_source():
    db = SessionLocal()
    try:
        # Create an ambiguous raw listing needing review
        raw = FactRawListing(
            source_id=11,
            source_listing_id=f"test_review_{int(datetime.utcnow().timestamp())}",
            url="https://chotot.com/test_rev.htm",
            raw_title="Điện thoại lạ không rõ hãng giá inbox",
            raw_price_text="giá inbox",
            raw_currency="VND"
        )
        db.add(raw)
        db.commit()
        db.refresh(raw)

        pipeline = NormalizationPipeline(db)
        norm = pipeline.normalize_listing(raw)

        assert norm.manual_review_required is True
        assert norm.price_valid is False

        # Apply manual correction
        update_data = ReviewUpdateRequest(
            product_id=1,
            condition_id=1,
            normalized_price=3_500_000.0,
            price_valid=True,
            classification="SELL",
            manual_review_required=False,
            reviewer="qa_lead",
            reason="Confirmed device model and negotiable price"
        )

        updated_norm = apply_manual_correction(db, norm.id, update_data)
        assert updated_norm.manual_review_required is False
        assert float(updated_norm.normalized_price) == 3_500_000.0
        assert updated_norm.pipeline_stage == "MANUAL"

        # Verify audit logs created
        logs = db.query(NormalizationAuditLog).filter(
            NormalizationAuditLog.normalized_listing_id == norm.id
        ).all()
        assert len(logs) > 0
        field_names = [l.field_name for l in logs]
        assert "normalized_price" in field_names
        assert "product_id" in field_names

        # Crucial check: RAW SOURCE IS UNTOUCHED
        db.refresh(raw)
        assert raw.raw_price_text == "giá inbox"
        assert raw.raw_title == "Điện thoại lạ không rõ hãng giá inbox"
    finally:
        db.close()


# ==============================================================================
# 7. API ENDPOINT TESTS
# ==============================================================================

def test_api_normalization_endpoints():
    # 1. Metrics endpoint
    resp_metrics = client.get("/normalization/metrics")
    assert resp_metrics.status_code == 200
    metrics = resp_metrics.json()
    assert "total_raw_listings" in metrics
    assert "rule_only" in metrics
    assert "ai_processed" in metrics
    assert "avg_confidence" in metrics
    assert metrics["active_ai_provider"] in ("mock", "openai_compatible", "gemini")

    # 2. Review queue endpoint
    resp_review = client.get("/normalization/review?limit=10")
    assert resp_review.status_code == 200
    review_queue = resp_review.json()
    assert isinstance(review_queue, list)

    # 3. Normalized listings endpoint
    resp_listings = client.get("/normalization/listings?limit=5")
    assert resp_listings.status_code == 200
    assert isinstance(resp_listings.json(), list)


# ==============================================================================
# 8. NOISE FILTERING & PRODUCT INTEGRITY TESTS
# ==============================================================================

def test_accessory_and_parts_not_matched_to_main_device():
    """
    1. Trả đúng kết quả mong muốn, KHÔNG nhầm lẫn sản phẩm:
    Ốp lưng, kính cường lực, bao da, xác máy tuyệt đối KHÔNG ĐƯỢC match vào iPhone 16/16 Plus.
    """
    db = SessionLocal()
    try:
        accessories = [
            "Ốp lưng iPhone 16 Plus chống sốc",
            "Kính cường lực iPhone 16 KingKong",
            "Bao da iPhone 16 Pro Max cao cấp",
            "Hộp rỗng iPhone 16 128GB",
            "Củ sạc nhanh 20W cho iPhone 16",
            "Bán xác iPhone 16 dính iCloud rã đồ",
        ]
        for acc in accessories:
            prod, var, conf, stage, _ = match_product_and_variant(acc, db)
            assert prod is None, f"Phụ kiện/Xác '{acc}' không được phép match thành sản phẩm điện thoại!"
            assert "EXCLUDED" in stage
    finally:
        db.close()


def test_strict_model_matching_plus_vs_base():
    """
    iPhone 16 Plus chỉ lấy iPhone 16 Plus, không lấy nhầm sang iPhone 16 thường.
    Và iPhone 16 thường không lấy nhầm sang iPhone 16 Plus.
    """
    db = SessionLocal()
    try:
        # 1. iPhone 16 Plus
        p_plus, _, _, _, _ = match_product_and_variant("Bán iPhone 16 Plus 128GB màu xanh", db)
        if p_plus:
            assert p_plus.name == "iPhone 16 Plus"
            assert "plus" in p_plus.slug

        # 2. iPhone 16 Base (không có plus)
        p_base, _, _, _, _ = match_product_and_variant("iPhone 16 128GB chính hãng VN/A", db)
        if p_base:
            assert p_base.name == "iPhone 16"
            assert p_base.slug == "iphone-16"

        # 3. Tin đăng iPhone 16 Plus tuyệt đối không match vào iPhone 16 Base
        from app.taxonomy.models import DimProduct
        from app.normalization.rules.alias_matcher import is_spec_compatible
        base_product = db.query(DimProduct).filter(DimProduct.slug == "iphone-16").first()
        if base_product:
            assert not is_spec_compatible(base_product, "iPhone 16 Plus 128GB")
            assert not is_spec_compatible(base_product, "iPhone 16 Pro Max 256GB")
            assert is_spec_compatible(base_product, "iPhone 16 128GB đen")
    finally:
        db.close()


def test_ram_generation_integrity():
    """
    RAM DDR5 là chỉ lấy DDR5, không lấy DDR3 hay DDR4.
    """
    from app.taxonomy.models import DimProduct
    from app.normalization.rules.alias_matcher import is_spec_compatible
    
    # Tạo mock object kiểm tra logic
    class FakeProduct:
        slug = "ram-ddr5"
        name = "RAM DDR5 16GB 5600MHz"

    prod_ddr5 = FakeProduct()
    # DDR3/DDR4 không tương thích với RAM DDR5
    assert not is_spec_compatible(prod_ddr5, "RAM laptop DDR3 4GB 1600MHz")
    assert not is_spec_compatible(prod_ddr5, "Bán kit RAM DDR4 16GB 3200")
    assert is_spec_compatible(prod_ddr5, "Bán thanh RAM DDR5 16GB bóc máy")


def test_pipeline_price_floor_guard():
    """
    2. Giá cần phải xem xét phán đoán đúng:
    Làm gì có iPhone 16 nào giá 1.350.000 đ!
    Pipeline phải phát hiện giá ảo / giá trả góp bất thường và gán price_valid = False.
    """
    db = SessionLocal()
    try:
        pipeline = NormalizationPipeline(db)

        # Raw listing iPhone 16 rao 1.350.000 đ
        raw_phone = FactRawListing(
            source_id=11,
            source_listing_id=f"test_ip16_{int(datetime.utcnow().timestamp())}",
            url="https://facebook.com/marketplace/item/99999",
            raw_title="iPhone 16 128GB đẹp keng nguyên zin",
            raw_description="Máy quốc tế zin",
            raw_price_text="1.350.000 đ",
            raw_currency="VND",
            last_seen_at=datetime.utcnow()
        )
        db.add(raw_phone)
        db.commit()

        norm = pipeline.normalize_listing(raw_phone)
        # Giá 1.350.000đ cho iPhone 16 BẮT BUỘC bị từ chối hợp lệ
        assert norm.price_valid is False
        assert norm.price_validity_reason in ("UNREALISTIC_LOW_PRICE", "INSTALLMENT_TEASER")
    finally:
        db.close()
