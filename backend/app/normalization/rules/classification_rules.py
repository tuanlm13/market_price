import re
from typing import Tuple

SPAM_KEYWORDS = [
    "vay tiền", "tuyển dụng", "việc làm", "cho vay", "tài chính", "sim số đẹp",
    "đổi thẻ", "kiếm tiền online", "tuyển ctv", "đăng ký nhận ngay", "lãi suất",
    "kéo tài xỉu", "cờ bạc", "tài khoản ngân hàng"
]

WANTED_BUY_PATTERNS = [
    r"\b(cần mua|tìm mua|thu mua|mua lại|cần tìm|cần kiếm|wtb|looking for|mua xác|thu số lượng|thu gom|nhận thu)\b"
]

SERVICE_PATTERNS = [
    r"\b(nhận sửa|ép kính|thay màn|thay pin|sửa chữa|unlock|vệ sinh|bẻ khoá|bypass|chạy phần mềm|cứu dữ liệu|thay vỏ|thay lưng|độ vỏ|sửa vga|đóng chip|sửa main|đóng vram|câu dây)\b"
]

PARTS_PATTERNS = [
    r"\b(xác máy|rã xác|bán xác|xác điện thoại|xác vga|xác laptop|xác pc|rã linh kiện|xác còn nguồn|xác chết|chết nguồn|mất nguồn|chết màn|hỏng màn|sọc màn|màn sọc|đốm màn|chảy mực|dính icloud|icloud ẩn|icloud|dính tk|lỗi main|chết main|hỏng main|không lên nguồn|mất face|mất vân|bypass|máy cỏ|rã đồ)\b"
]

ACCESSORY_PATTERNS = [
    r"\b(ốp lưng|ốp|case|cường lực|kính cường lực|dán màn|dán ppf|ppf|skin|bao da|vỏ ốp|củ sạc|dây sạc|cáp sạc|cáp|củ|hộp máy|box rỗng|vỏ hộp|hộp|dock sạc|khay sim|bút cảm ứng|dây đeo|nguồn sạc|túi chống sốc|quạt tản|hub chuyển đổi|đầu chuyển|đầu sạc)\b"
]

SELL_PATTERNS = [
    r"\b(bán|cần bán|pass|thanh lý|xả|nhượng lại|lên đời pass|bán lại|fullbox|mới keng|ra đi|bay nhanh|chính hãng|nguyên seal|zin|keng)\b"
]

def classify_listing_intent(title: str, description: str = "") -> Tuple[str, float]:
    """
    Classifies listing intent:
    SELL, BUY, WANTED, SERVICE, ACCESSORY, PARTS, SPAM, UNKNOWN.
    Returns (classification, confidence).
    """
    title_lower = (title or "").lower().strip()
    text = f"{title_lower} {(description or '').lower()}".strip()

    # 1. Spam detection
    for kw in SPAM_KEYWORDS:
        if kw in text:
            return "SPAM", 0.95

    # 2. Priority check on Title first for accessories and parts
    # (Nếu tiêu đề chứa 'ốp lưng', 'cường lực', 'xác máy'... thì 99% không phải bán máy hoàn chỉnh)
    for pat in ACCESSORY_PATTERNS:
        if re.search(pat, title_lower):
            return "ACCESSORY", 0.95

    for pat in PARTS_PATTERNS:
        if re.search(pat, title_lower):
            return "PARTS", 0.95

    for pat in SERVICE_PATTERNS:
        if re.search(pat, title_lower):
            return "SERVICE", 0.95

    for pat in WANTED_BUY_PATTERNS:
        if re.search(pat, title_lower):
            return "BUY", 0.95

    # 3. Check full text (Title + Description)
    for pat in ACCESSORY_PATTERNS:
        if re.search(pat, text):
            return "ACCESSORY", 0.85

    for pat in PARTS_PATTERNS:
        if re.search(pat, text):
            return "PARTS", 0.85

    for pat in SERVICE_PATTERNS:
        if re.search(pat, text):
            return "SERVICE", 0.85

    for pat in WANTED_BUY_PATTERNS:
        if re.search(pat, text):
            return "BUY", 0.90

    # 4. Sell detection
    for pat in SELL_PATTERNS:
        if re.search(pat, text):
            return "SELL", 0.90

    # Default assumption for marketplace listings is SELL if no other intent found
    return "SELL", 0.70
