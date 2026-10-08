import pytest
from app.deal_hunter.thresholds import get_category_threshold, CategoryThreshold
from app.deal_hunter.calculator import calculate_acquisition_cost, calculate_financial_metrics
from app.deal_hunter.comment_appraiser import parse_vietnamese_price, analyze_comments
from app.deal_hunter.appraiser import DealAppraiser
from app.deal_hunter.telegram_provider import TelegramNotificationProvider
from app.deal_hunter.schemas import DealAppraisalOutput

def test_category_thresholds():
    """Kiểm tra cấu hình ngưỡng độc lập theo từng category, không hardcode."""
    phone_th = get_category_threshold("SMARTPHONE")
    gpu_th = get_category_threshold("GPU")
    ram_th = get_category_threshold("RAM")
    fallback_th = get_category_threshold("UNKNOWN_CAT")

    assert phone_th.min_profit == 500_000.0
    assert phone_th.min_roi == 0.10
    assert "FAIR" in phone_th.acceptable_conditions

    assert gpu_th.min_profit == 700_000.0
    assert gpu_th.min_roi == 0.12
    # GPU rủi ro cao hơn nên không chấp nhận FAIR
    assert "FAIR" not in gpu_th.acceptable_conditions

    assert ram_th.min_profit == 150_000.0
    assert ram_th.min_roi == 0.18

    assert fallback_th.category_code == "DEFAULT"

def test_calculator_acquisition_cost():
    """Kiểm tra tính giá vốn: VN sources (buffer) vs Goofish (landed cost)."""
    th = get_category_threshold("SMARTPHONE")

    # VN source (Chợ Tốt, FB)
    vn_cost = calculate_acquisition_cost("Chợ Tốt", 10_000_000.0, th)
    assert vn_cost == 10_000_000.0 + th.vn_cost_buffer

    # Goofish (Landed cost: tỷ giá + phí trung gian + phí cố định)
    goofish_cost = calculate_acquisition_cost("Goofish (闲鱼)", 10_000_000.0, th)
    expected_landed = round(10_000_000.0 * th.goofish_landed_multiplier + th.goofish_fixed_buffer, 2)
    assert goofish_cost == expected_landed

def test_calculator_financial_metrics():
    """Kiểm tra công thức deterministic math: profit, ROI, discounts, market position."""
    market_stats = {
        "p10": 11_000_000.0,
        "p25": 11_800_000.0,
        "median": 12_500_000.0,
        "quick_sell_price": 11_500_000.0
    }

    asking_price = 10_000_000.0
    acquisition_cost = 10_060_000.0

    metrics = calculate_financial_metrics(asking_price, acquisition_cost, market_stats)

    # expected_profit = quick_sell - acquisition_cost
    assert metrics["expected_profit"] == 11_500_000.0 - 10_060_000.0
    assert metrics["expected_profit"] == 1_440_000.0

    # ROI = profit / acquisition_cost
    expected_roi = round(1_440_000.0 / 10_060_000.0, 4)
    assert metrics["roi"] == expected_roi

    # Discount vs median = (12.5m - 10m) / 12.5m = 0.20 (20%)
    assert metrics["discount_vs_median"] == 0.20

    # Market position: asking_price (10m) <= p10 (11m) -> DEEP_DISCOUNT
    assert metrics["market_position"] == "DEEP_DISCOUNT"

def test_vietnamese_price_parsing():
    """Kiểm tra bóc tách các biến thể giá tiền tiếng Việt thường gặp."""
    assert parse_vietnamese_price("12tr2 lấy nhanh") == 12_200_000.0
    assert parse_vietnamese_price("11m8 bay gấp") == 11_800_000.0
    assert parse_vietnamese_price("fix mạnh 12.5tr") == 12_500_000.0
    assert parse_vietnamese_price("850k không bớt") == 850_000.0
    assert parse_vietnamese_price("chốt 12.200.000 đ") == 12_200_000.0

def test_comment_appraisal_effective_price_and_sub_candidates():
    """Kiểm tra phân tích comments: seller giảm giá vs user khác chào bán."""
    comments = [
        {"author": "buyer1", "text": "Có fix không bác?", "is_author": False},
        {"author": "seller", "text": "12tr2 lấy nhanh trong ngày bác ơi", "is_author": True},
        {"author": "other_seller", "text": "ké em có con này 11tr8 đẹp keng", "is_author": False}
    ]

    effective_price, sub_candidates = analyze_comments(comments, seller_identifier="seller")

    assert effective_price == 12_200_000.0
    assert len(sub_candidates) == 1
    assert sub_candidates[0].extracted_price == 11_800_000.0
    assert sub_candidates[0].author == "other_seller"

def test_deal_appraiser_decision_flow():
    """Kiểm tra quyết định BUY, WATCH, SKIP của Rule Engine và AI explanation."""
    appraiser = DealAppraiser()

    market_stats = {
        "p10": 11_000_000.0,
        "p25": 11_800_000.0,
        "median": 12_500_000.0,
        "quick_sell_price": 11_500_000.0,
        "confidence": 85,
        "liquidity": 80
    }

    # Case 1: Kèo thơm hoàn hảo -> BUY
    good_listing = {
        "title": "iPhone 13 128GB zin đẹp",
        "description": "Máy nguyên zin pin 90% không lỗi lầm",
        "asking_price": 9_800_000.0,
        "source": "Chợ Tốt",
        "condition": "LIKE_NEW"
    }
    res_buy = appraiser.appraise(good_listing, market_stats, category_code="SMARTPHONE")
    assert res_buy.decision == "BUY"
    assert res_buy.expected_profit > 500_000.0
    assert res_buy.roi >= 0.10
    # AI không được sửa số liệu market numbers
    assert res_buy.quick_sell_price == 11_500_000.0
    assert "Kèo thơm đáng mua" in res_buy.reason

    # Case 2: Giá quá cao / lỗ -> SKIP
    expensive_listing = {
        "title": "iPhone 13 128GB fullbox",
        "description": "Máy người dùng giữ kỹ",
        "asking_price": 12_000_000.0,
        "source": "Chợ Tốt",
        "condition": "LIKE_NEW"
    }
    res_skip = appraiser.appraise(expensive_listing, market_stats, category_code="SMARTPHONE")
    assert res_skip.decision == "SKIP"
    assert "Bỏ qua" in res_skip.reason

    # Case 3: Máy hỏng xác không được chấp nhận -> SKIP
    junk_listing = {
        "title": "iPhone 13 xác vỡ màn",
        "description": "Bán xác lấy linh kiện",
        "asking_price": 4_000_000.0,
        "source": "Chợ Tốt",
        "condition": "FOR_PARTS"
    }
    res_junk = appraiser.appraise(junk_listing, market_stats, category_code="SMARTPHONE")
    assert res_junk.decision == "SKIP"

    # Case 4: Có rủi ro trong mô tả (mất face) -> hạ cấp từ BUY xuống WATCH
    risky_listing = {
        "title": "iPhone 13 128GB",
        "description": "Máy zin mất face id bán rẻ",
        "asking_price": 9_500_000.0,
        "source": "Chợ Tốt",
        "condition": "GOOD"
    }
    res_risky = appraiser.appraise(risky_listing, market_stats, category_code="SMARTPHONE")
    assert res_risky.decision == "WATCH"
    assert any("FaceID" in r for r in res_risky.risks)

def test_telegram_provider_mock_and_message_format():
    """Kiểm tra TelegramNotificationProvider mock mode và định dạng tin nhắn chuẩn."""
    provider = TelegramNotificationProvider(mock_mode=True)

    deal_payload = {
        "product_name": "iPhone 13 128GB",
        "variant_name": "128GB Quốc Tế",
        "condition": "LIKE_NEW (99%)",
        "source": "Chợ Tốt",
        "asking_price": 9800000.0,
        "acquisition_cost": 9860000.0,
        "p10": 11000000.0,
        "p25": 11800000.0,
        "median": 12500000.0,
        "quick_sell_price": 11500000.0,
        "expected_profit": 1640000.0,
        "roi": 0.1663,
        "market_confidence": 88,
        "liquidity": 82,
        "reason": "Giá thấp hơn P10 thị trường 12%",
        "risks": ["Không phát hiện rủi ro bất thường"],
        "url": "https://chotot.com/item/12345"
    }

    success = provider.send_deal_alert(deal_payload, chat_id="123456789")
    assert success is True
    assert len(provider.sent_messages) == 1

    msg_text = provider.sent_messages[0]["text"]
    assert "🚨 <b>DEAL MỚI PHÁT HIỆN</b>" in msg_text
    assert "iPhone 13 128GB" in msg_text
    assert "9.800.000 đ" in msg_text
    assert "1.640.000 đ" in msg_text
    assert "16.6%" in msg_text
    assert "P10" in msg_text
    assert "Quick Sell" in msg_text
    assert "https://chotot.com/item/12345" in msg_text

def test_deduplication_price_drop_rule():
    """Kiểm tra quy tắc deduplication: không alert lại trừ khi giá giảm >= 5%."""
    # Giả lập logic kiểm tra dedup
    prev_asking_price = 10_000_000.0
    
    # Giảm nhẹ 2% (9.8m) -> không đủ ngưỡng 5% -> Dedup (không alert)
    price_minor_drop = 9_800_000.0
    should_alert_minor = price_minor_drop <= (prev_asking_price * 0.95)
    assert should_alert_minor is False

    # Giảm sâu 6% (9.4m) -> thỏa ngưỡng 5% -> Alert lại
    price_major_drop = 9_400_000.0
    should_alert_major = price_major_drop <= (prev_asking_price * 0.95)
    assert should_alert_major is True


def test_deal_appraiser_deep_discount_anomaly_guard():
    """
    Kiểm tra Anomaly Guard:
    iPhone 16 rao 1.350.000 đ (thị trường 18.5M) KHÔNG ĐƯỢC coi là BUY deal.
    Hệ thống phải phán đoán đây là giá ảo/bất thường và SKIP ngay lập tức!
    """
    appraiser = DealAppraiser()

    market_stats = {
        "p10": 17_000_000.0,
        "p25": 17_800_000.0,
        "median": 18_500_000.0,
        "quick_sell_price": 16_500_000.0,
        "confidence": 85,
        "liquidity": 80
    }

    # Tin đăng iPhone 16 rao 1.350.000 đ
    unrealistic_listing = {
        "title": "📱 IPHONE 16 PLUS LOCK CNC – 2 SIM VẬT LÝ",
        "description": "Máy đẹp zin keng",
        "asking_price": 1_350_000.0,
        "source": "Facebook Marketplace",
        "condition": "GOOD"
    }

    res = appraiser.appraise(unrealistic_listing, market_stats, category_code="SMARTPHONE")
    assert res.decision == "SKIP"
    assert "Giá thấp bất thường" in res.reason or "CẢNH BÁO GIÁ ẢO" in str(res.risks)
    assert any("CẢNH BÁO GIÁ ẢO" in r for r in res.risks)


def test_deal_appraiser_installment_bait_skip():
    """
    Kiểm tra chiêu trò trả góp:
    Bài đăng ghi trả trước hoặc góp -> SKIP ngay lập tức.
    """
    appraiser = DealAppraiser()
    market_stats = {
        "p10": 17_000_000.0,
        "p25": 17_800_000.0,
        "median": 18_500_000.0,
        "quick_sell_price": 16_500_000.0,
        "confidence": 85,
        "liquidity": 80
    }

    installment_listing = {
        "title": "iPhone 16 128GB trả trước chỉ từ 2tr nhận máy",
        "description": "Hỗ trợ góp qua CCCD duyệt nhanh không giữ giấy tờ",
        "asking_price": 2_000_000.0,
        "source": "Chợ Tốt",
        "condition": "LIKE_NEW"
    }

    res = appraiser.appraise(installment_listing, market_stats, category_code="SMARTPHONE")
    assert res.decision == "SKIP"
    assert "trả góp" in res.reason or "trả trước" in res.reason
