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
