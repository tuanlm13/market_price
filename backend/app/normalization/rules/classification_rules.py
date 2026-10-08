import re
from typing import Tuple, List

SPAM_KEYWORDS = [
    "vay tiền", "tuyển dụng", "việc làm", "cho vay", "tài chính", "sim số đẹp",
    "đổi thẻ", "kiếm tiền online", "tuyển ctv", "đăng ký nhận ngay", "lãi suất",
    "kéo tài xỉu", "cờ bạc", "tài khoản ngân hàng", "game slot", "game bài",
    "tín dụng đen", "app vay", "giải pháp vốn"
]

WANTED_BUY_PATTERNS = [
    r"\b(cần mua|tìm mua|thu mua|mua lại|cần tìm|cần kiếm|wtb|looking for|mua xác|thu số lượng|thu gom|nhận thu)\b"
]

SERVICE_PATTERNS = [
    r"\b(nhận sửa|ép kính|thay màn|thay pin|sửa chữa|unlock|vệ sinh|bẻ khoá|bypass|chạy phần mềm|cứu dữ liệu|thay vỏ|thay lưng|độ vỏ|sửa vga|đóng chip|sửa main|đóng vram|câu dây|dịch vụ sửa|nhận ép|nhận thay)\b"
]

PARTS_PATTERNS = [
    r"\b(xác máy|rã xác|bán xác|xác điện thoại|xác vga|xác laptop|xác pc|rã linh kiện|xác còn nguồn|xác chết|chết nguồn|mất nguồn|chết màn|hỏng màn|sọc màn|màn sọc|đốm màn|chảy mực|dính icloud|icloud ẩn|icloud|dính tk|lỗi main|chết main|hỏng main|không lên nguồn|mất face|mất vân|bypass|máy cỏ|rã đồ|xác còn|linh kiện lẻ|board mạch|chip ic|tụ điện)\b"
]

ACCESSORY_PATTERNS = [
    # Ốp / Case / Bảo vệ
    r"\b(ốp lưng|ốp bảo vệ|khung ốp|vỏ ốp|bao da|ốp silicon|ốp trong|ốp chống sốc)\b",
    r"\b(protective case|protective cover|protection case|bumper case|armor case)\b",
    r"(?:^|\W)(case|ốp)(?:\W|$)",
    # Kính cường lực / Dán
    r"\b(cường lực|kính cường lực|dán màn|dán ppf|ppf|skin|miếng dán|kính bảo vệ)\b",
    # Sạc / Cáp
    r"\b(củ sạc|dây sạc|cáp sạc|dock sạc|nguồn sạc|bộ sạc|adapter sạc|sạc nhanh|sạc dự phòng)\b",
    r"(?:^|\W)(cáp|củ)(?:\W|$)",
    # Hộp / Phụ kiện khác
    r"\b(hộp máy|hộp rỗng|box rỗng|vỏ hộp|hộp zin|box zin|vỏ box|khay sim|bút cảm ứng|dây đeo|túi chống sốc|quạt tản|hub chuyển đổi|đầu chuyển|đầu sạc|tai nghe rời|tai nghe zin|airpods giả|earpods|phụ kiện|gậy chụp|giá đỡ|đế giữ|kẹp điện thoại|giá kẹp)\b",
    # Phụ kiện DJI / Drone / Camera
    r"\b(khung bảo vệ|khung ốp bảo vệ|propeller guard|gimbal protector|nd filter|bộ lọc|tay cầm phụ|remote controller|pin dji|pin drone|cánh quạt)\b",
    r"\b(dji osmo.*(?:case|ốp|bảo vệ|filter|mount|holder))\b",
]

SELL_PATTERNS = [
    r"\b(bán|cần bán|pass|thanh lý|xả|nhượng lại|lên đời pass|bán lại|fullbox|mới keng|ra đi|bay nhanh|chính hãng|nguyên seal|zin|keng)\b"
]

# ============================================================================
# JUNK TITLE PATTERNS — Nhận diện nhanh tin rác dựa trên tiêu đề
# Dùng cho bot_listener để lọc trước khi trả kết quả
# ============================================================================
JUNK_TITLE_PATTERNS = [
    # Phụ kiện rõ ràng
    r"\b(ốp lưng|ốp bảo vệ|khung ốp|vỏ ốp|bao da|case bảo vệ|protective case)\b",
    r"\b(cường lực|kính cường lực|miếng dán|dán ppf|skin|ppf)\b",
    r"\b(củ sạc|dây sạc|cáp sạc|dock sạc|sạc dự phòng|adapter)\b",
    r"\b(hộp rỗng|box rỗng|vỏ hộp|khay sim)\b",
    r"\b(phụ kiện|gậy chụp|giá đỡ|đế giữ|kẹp điện thoại|remote|tay cầm)\b",
    # Linh kiện lỗi / xác
    r"\b(xác máy|rã xác|bán xác|xác chết|rã đồ|rã linh kiện)\b",
    r"\b(dính icloud|chết nguồn|mất nguồn|hỏng màn|chết main|sọc màn|mất face|mất vân)\b",
    # Dịch vụ
    r"\b(nhận sửa|ép kính|sửa chữa|dịch vụ|unlock|bypass)\b",
    # Spam
    r"\b(vay tiền|tuyển dụng|cho vay|tài chính|kiếm tiền online|sim số đẹp)\b",
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


def is_junk_listing(title: str) -> bool:
    """
    Kiểm tra nhanh title có phải tin rác (phụ kiện, linh kiện hỏng, dịch vụ, spam) hay không.
    Dùng cho bot_listener để pre-filter trước khi trả kết quả Telegram.
    """
    title_lower = (title or "").lower().strip()
    for pat in JUNK_TITLE_PATTERNS:
        if re.search(pat, title_lower):
            return True
    return False


def is_relevant_to_keyword(title: str, keyword: str) -> bool:
    """
    Kiểm tra title có THỰC SỰ liên quan đến keyword user tìm kiếm hay không.
    Chặn các trường hợp:
    - Search 'iPhone 16 Plus' nhưng match 'Ốp lưng iPhone 16 Plus'
    - Search 'RAM DDR5' nhưng match 'RAM DDR3' hoặc 'Bán RAM PC, laptop 4GB'
    - Search 'RTX 4060' nhưng match 'Quạt tản RTX 4060'
    """
    title_lower = (title or "").lower().strip()
    kw_lower = keyword.lower().strip()

    # Bước 1: Loại bỏ tin rác ngay
    if is_junk_listing(title):
        return False

    # Bước 2: Tất cả các từ keyword phải xuất hiện trong title
    kw_parts = [p.strip() for p in kw_lower.split() if p.strip()]
    if not all(part in title_lower for part in kw_parts):
        return False

    # Bước 3: Kiểm tra tính nhất quán đặc tả (spec consistency)
    # RAM generation guard
    if "ddr5" in kw_lower and not re.search(r"\b(ddr5|pc5)\b", title_lower):
        return False
    if "ddr4" in kw_lower and not re.search(r"\b(ddr4|pc4)\b", title_lower):
        return False
    if "ddr3" in kw_lower and not re.search(r"\b(ddr3|pc3)\b", title_lower):
        return False

    # iPhone model guard
    if "plus" in kw_lower and not re.search(r"\b(plus|\+)\b", title_lower):
        return False
    if "pro max" in kw_lower and not re.search(r"\b(pro\s*max|prm|promax)\b", title_lower):
        return False
    if "pro" in kw_lower and "max" not in kw_lower and "plus" not in kw_lower:
        if not re.search(r"\bpro\b", title_lower):
            return False

    # iPhone BASE model guard: khi user tìm "iphone 16" (không có plus/pro/max)
    # thì title KHÔNG ĐƯỢC chứa plus, pro, max, mini
    iphone_match = re.search(r"iphone\s*(\d+)", kw_lower)
    if iphone_match:
        has_suffix_in_kw = any(s in kw_lower for s in ["plus", "pro", "max", "mini"])
        if not has_suffix_in_kw:
            # User đang tìm model base -> chặn title có plus/pro/max/mini
            if re.search(r"\b(plus|\+|pro|max|promax|prm|mini)\b", title_lower):
                return False

    # Bước 4: Chặn tin bán linh kiện generic khi user tìm sản phẩm cụ thể
    # VD: user tìm "ram ddr5" nhưng title chỉ là "Bán ram PC, laptop 4GB" (không có DDR5)
    if "ram" in kw_lower and "ddr" in kw_lower:
        # Nếu keyword chỉ rõ thế hệ DDR nhưng title không có -> loại
        ddr_gen = re.search(r"(ddr\d)", kw_lower)
        if ddr_gen:
            gen_str = ddr_gen.group(1)
            if gen_str not in title_lower:
                return False

    return True

