import pytest
from unittest.mock import MagicMock
from app.deal_hunter.ram_bot import (
    is_ram_post,
    RamTelegramNotifier,
    notify_if_ram_post
)

def test_is_ram_post_valid_sellers():
    """Kiểm tra các tin bán RAM thật sự (User là người mua -> chỉ lấy tin người BÁN)."""
    valid_samples = [
        ("RAM Laptop Micron DDR4 8GB 3200MHz", "Hàng bóc máy dell chạy tốt"),
        ("16GB DDR4 ram dùng cho laptop", "Pass lại cho ai cần"),
        ("Bán ram PC, laptop 4GB", "DDR3 4GB bus 1600"),
        ("Ram 8gb pc3l laptop", "Bảo hành 1 tháng"),
        ("Kit ram Corsair Dominator Titanium DDR5 64GB", "Fullbox mới 99%"),
        ("Samsung 32GB DDR4 ECC Server RAM", "Ram server thanh lý"),
        ("Pass thanh ram ddr4 8gb bus 2666 giá 200k", "Mình lên 16gb nên dư ra"),
    ]
    for title, desc in valid_samples:
        ok, reason = is_ram_post(title, desc)
        assert ok is True, f"Failed for '{title}' (reason: {reason})"
        assert reason == "VALID_RAM_SELL"


def test_is_ram_post_blocked_cases():
    """Kiểm tra việc loại bỏ tin cần mua, tin bán laptop nguyên chiếc, tin rác."""
    blocked_samples = [
        # Bán laptop / PC nguyên chiếc
        ("Laptop Lenovo Gaming i5 9300H/ Ram 8Gb/ Ssd 480Gb/ Vga 1050", "Máy còn đẹp", "WHOLE_LAPTOP_OR_PC"),
        # Tin cần mua / tìm mua (User là người mua nên loại người cần mua)
        ("Cần mua 2 thanh ram ddr4 16gb ai có ib", "Khu vực Cầu Giấy HN", "BUY_WANTED_POST"),
        ("Tìm mua ram ddr5 32gb ở HN", "Bác nào có ném vào đây", "BUY_WANTED_POST"),
        ("Thu mua ram cũ hỏng giá cao tận nơi", "Liên hệ sđt 098...", "BUY_WANTED_POST"),
        # Tin bán RAM xác / lỗi / hỏng
        ("Ram Xác - Lỗi Thanh lý nhanh gọn - Hà Nội . Qua 244 Lê Thanh Nghị mua trực tiếp .", "Bán xác linh kiện", "DEFECTIVE_OR_PARTS_RAM"),
        ("Bán xác 10 thanh ram ddr3 cho thợ", "Thanh lý dọn kho", "DEFECTIVE_OR_PARTS_RAM"),
        ("10 thanh ram ddr4 bị lỗi không nhận", "", "DEFECTIVE_OR_PARTS_RAM"),
        # Thẻ trang cá nhân / Profile Card thành viên nhóm (như Trang Nguyễn, Trần Thanh)
        ("Trang Nguyễn (PP Ssd Ram Kingbank)", "Người sáng tạo nội dung số · 2,2K người theo dõi · Thêm bạn bè", "PROFILE_OR_USER_CARD"),
        ("Trần Thanh (thanh ram)", "1.5K người theo dõi · Nhắn tin · Thêm bạn bè", "PROFILE_OR_USER_CARD"),
        # Phụ kiện / tin rác
        ("Quạt tản nhiệt RAM RGB Jonsbo", "Phụ kiện làm mát", "INTENT_ACCESSORY"),
        # Sản phẩm khác
        ("iPhone 16 128GB VN/A", "Máy đẹp keng", "NO_RAM_KEYWORD"),
        ("Dji Action4 bao gồm tất cả phụ kiện", "Máy như mới", "INTENT_ACCESSORY"),
    ]
    for title, desc, expected_reason in blocked_samples:
        ok, reason = is_ram_post(title, desc)
        assert ok is False, f"Should be blocked: '{title}' (got reason: {reason})"
        assert reason == expected_reason


def test_ram_telegram_notifier_format_and_dedup():
    """Kiểm tra format tin nhắn thông báo RAM và cơ chế chống trùng lặp."""
    notifier = RamTelegramNotifier(mock_mode=True, default_chat_id="123456789")

    item = {
        "title": "RAM Corsair Vengeance DDR5 32GB (2x16GB) 5600MHz",
        "price_text": "2.400.000 đ",
        "group_name": "Chợ Linh Kiện Máy Tính Hà Nội",
        "seller_name": "Nguyễn Văn A",
        "description": "Bán kit ram ddr5 corsair mới mua 2 tháng còn bảo hành Mai Hoàng",
        "comment_count": 3,
        "url": "https://www.facebook.com/groups/chocongnghe/posts/999888777"
    }

    # Gửi lần 1: Thành công
    sent1 = notifier.send_ram_sale_alert(item)
    assert sent1 is True
    assert len(notifier.sent_alerts) == 1

    last_msg = notifier.sent_alerts[0]["text"]
    assert "BÀI ĐĂNG BÁN RAM MỚI" in last_msg
    assert "RAM Corsair Vengeance DDR5" in last_msg
    assert "2.400.000 đ" in last_msg
    assert "Chợ Linh Kiện Máy Tính Hà Nội" in last_msg
    assert "Nguyễn Văn A" in last_msg
    assert "Thời gian:" in last_msg

    # Gửi lần 2 cùng URL: Bị chặn dedup
    sent2 = notifier.send_ram_sale_alert(item)
    assert sent2 is False
    assert len(notifier.sent_alerts) == 1


def test_notify_if_ram_post_hook():
    """Kiểm tra hook notify_if_ram_post hoạt động khi nhận đối tượng FactRawListing."""
    mock_raw = MagicMock()
    mock_raw.raw_title = "RAM Laptop Micron DDR4 8GB 3200MHz"
    mock_raw.raw_description = "Bán thanh ram laptop bóc máy"
    mock_raw.raw_price_text = "350.000 đ"
    mock_raw.seller_name_raw = "Trần B"
    mock_raw.url = "https://www.facebook.com/groups/ram/posts/111222333"
    mock_raw.raw_metadata = {"group_name": "Hội Trao Đổi RAM Laptop"}
    mock_raw.comments = []

    notifier = RamTelegramNotifier(mock_mode=True, default_chat_id="123456789")
    from app.deal_hunter import ram_bot
    ram_bot.ram_notifier = notifier

    # Tin bán RAM hợp lệ -> Alert thành công
    res = notify_if_ram_post(mock_raw)
    assert res is True
    assert len(notifier.sent_alerts) == 1
    assert "Hội Trao Đổi RAM Laptop" in notifier.sent_alerts[0]["text"]

    # Tin không phải RAM -> Bỏ qua
    mock_raw.raw_title = "iPhone 15 Pro Max"
    mock_raw.raw_description = "Máy nguyên zin nguyên áp suất"
    mock_raw.url = "https://www.facebook.com/groups/iphone/posts/555"
    res_iphone = notify_if_ram_post(mock_raw)
    assert res_iphone is False


def test_clean_facebook_text():
    """Kiểm tra việc làm sạch ký tự ẩn và rác ngắt dòng của Facebook."""
    from app.deal_hunter.ram_bot import clean_facebook_text

    raw_noisy_text = (
        "Loan Le\n"
        "o͏\n"
        "e͏\n"
        "r͏\n"
        "o͏\n"
        "p͏\n"
        "s͏\n"
        "14 giờ\n"
        "Thanh lý kit ram DDR5 32GB 5600MHz Corsair\n"
        "Bảo hành Mai Hoàng 3 năm\n"
        "Xem thêm"
    )

    cleaned = clean_facebook_text(raw_noisy_text)
    assert "o" not in [l.strip() for l in cleaned.split("\n")]
    assert "Thanh lý kit ram DDR5 32GB 5600MHz Corsair" in cleaned
    assert "Bảo hành Mai Hoàng 3 năm" in cleaned
    assert "Xem thêm" not in cleaned
    assert "14 giờ" not in cleaned


def test_multiple_chat_ids_comma_separated():
    """Kiểm tra bot hỗ trợ nhiều chat ID ngăn cách bởi dấu phẩy và gửi broadcast tới tất cả."""
    from app.deal_hunter.telegram_provider import TelegramNotificationProvider
    
    # 1. Test RamTelegramNotifier với nhiều chat_id
    ram_notifier = RamTelegramNotifier(mock_mode=True, default_chat_id="111111, 222222 , 333333")
    assert ram_notifier.default_chat_ids == ["111111", "222222", "333333"]
    assert ram_notifier.default_chat_id == "111111"

    item = {
        "title": "Bán kit RAM DDR5 32GB Corsair",
        "price": 2500000.0,
        "price_text": "2.5tr",
        "url": "https://facebook.com/groups/ram/posts/888",
        "group_name": "Chợ RAM"
    }
    sent = ram_notifier.send_ram_sale_alert(item)
    assert sent is True
    # Cả 3 chat_id đều phải nhận được alert
    sent_cids = [a["chat_id"] for a in ram_notifier.sent_alerts]
    assert sent_cids == ["111111", "222222", "333333"]

    # 2. Test TelegramNotificationProvider với nhiều chat_id
    deal_provider = TelegramNotificationProvider(mock_mode=True, default_chat_id="444444, 555555")
    assert deal_provider.default_chat_ids == ["444444", "555555"]
    assert deal_provider.default_chat_id == "444444"

    deal_item = {
        "title": "RTX 4060 giá rẻ",
        "price": 5000000.0,
        "market_median": 7000000.0,
        "expected_profit": 2000000.0,
        "roi": 0.4,
        "source": "Chợ Tốt"
    }
    deal_sent = deal_provider.send_deal_alert(deal_item)
    assert deal_sent is True
    sent_msg_cids = [m["chat_id"] for m in deal_provider.sent_messages]
    assert sent_msg_cids == ["444444", "555555"]


def test_extract_facebook_post_id():
    """Kiểm tra trích xuất Post ID từ mọi định dạng URL Facebook."""
    from app.normalization.rules.classification_rules import extract_facebook_post_id

    # 1. URL dạng standard posts
    assert extract_facebook_post_id("https://www.facebook.com/groups/3434490203447677/posts/4659368897626462") == "4659368897626462"
    assert extract_facebook_post_id("https://www.facebook.com/groups/ram/posts/123456/") == "123456"

    # 2. URL dạng permalink story_fbid
    assert extract_facebook_post_id("https://www.facebook.com/permalink.php?story_fbid=987654321&id=1000") == "987654321"

    # 3. URL dạng photo set=pcb hoặc set=gm
    assert extract_facebook_post_id("https://www.facebook.com/photo/?fbid=111&set=pcb.555666777") == "555666777"
    assert extract_facebook_post_id("https://www.facebook.com/photo/?fbid=111&set=gm.444333222") == "444333222"

    # 4. Khi có source_listing_id sẵn
    assert extract_facebook_post_id("https://www.facebook.com/some_page", source_listing_id="999888") == "999888"


def test_notify_if_general_facebook_post():
    """Kiểm tra thông báo bài đăng Facebook tổng quát (Pocket 3, Action cam...) và deduplication."""
    from app.deal_hunter.bot_listener import notify_if_general_facebook_post, general_fb_notifier

    mock_raw = MagicMock()
    mock_raw.id = 9991
    mock_raw.source_listing_id = "4659368897626462"
    mock_raw.raw_title = "Cần bán DJI Osmo Pocket 3 combo đẹp keng"
    mock_raw.raw_description = "Bảo hành 2027, hoạt động hoàn hảo mọi tính năng"
    mock_raw.raw_price_text = "7.700.000 đ"
    mock_raw.seller_name_raw = "Hiep"
    mock_raw.url = "https://www.facebook.com/groups/3434490203447677/posts/4659368897626462"
    mock_raw.raw_metadata = {"group_name": "Pocket 4P-Pocket 4- Insta Luna Việt Nam"}
    mock_raw.comments = []

    # Mock Telegram bot
    general_fb_notifier.bot_token = "mock_token"
    general_fb_notifier.default_chat_ids = ["chat_123"]
    general_fb_notifier._notified_post_ids.clear()
    general_fb_notifier._notified_urls.clear()
    general_fb_notifier._send_telegram = MagicMock(return_value=True)

    # 1. Bài bán Pocket 3 hợp lệ -> Gửi alert thành công
    res = notify_if_general_facebook_post(mock_raw, group_name="Pocket 4P-Pocket 4- Insta Luna Việt Nam")
    assert res is True
    assert general_fb_notifier._send_telegram.call_count == 1
    sent_text = general_fb_notifier._send_telegram.call_args[0][0]
    assert "PHÁT HIỆN BÀI ĐĂNG MỚI TRÊN FACEBOOK" in sent_text
    assert "DJI Osmo Pocket 3" in sent_text
    assert "7.700.000 đ" in sent_text

    # 2. Gửi lần 2: Đã lưu post_id vào cache -> Bị chặn trùng lặp
    res2 = notify_if_general_facebook_post(mock_raw)
    assert res2 is False
    assert general_fb_notifier._send_telegram.call_count == 1

    # 3. Tin tìm mua -> Bị lọc bỏ
    mock_buy = MagicMock()
    mock_buy.raw_title = "Cần mua Pocket 3 cũ"
    mock_buy.raw_description = "Ai có pass e với"
    mock_buy.url = "https://facebook.com/groups/1/posts/888"
    mock_buy.raw_metadata = {}
    res_buy = notify_if_general_facebook_post(mock_buy)
    assert res_buy is False

    # 4. Tin RAM -> Bị bỏ qua (vì ram_bot xử lý)
    mock_ram = MagicMock()
    mock_ram.raw_title = "Bán thanh ram DDR4 16GB"
    mock_ram.raw_description = "Ram PC kingston"
    mock_ram.url = "https://facebook.com/groups/1/posts/999"
    mock_ram.raw_metadata = {}
    res_ram = notify_if_general_facebook_post(mock_ram)
    assert res_ram is False

