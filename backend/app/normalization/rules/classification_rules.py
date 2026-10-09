import re
from typing import Tuple, List, Optional
from datetime import datetime, timedelta

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
    r"\b(ốp lưng|ốp bảo vệ|khung ốp|khung bảo vệ|khung kim loại|khung cage|khung viền|camera cage|metal cage|vỏ ốp|bao da|case bảo vệ|protective case)\b",
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
    # Loại bỏ các cụm từ mô tả máy chính kèm đồ (vd: "kèm phụ kiện", "bao gồm tất cả phụ kiện")
    cleaned = re.sub(r"\b(bao gồm|kèm|đủ|full|gồm|tất cả|tặng)\s+(?:tất cả\s+)?phụ kiện\b", "", title_lower)
    for pat in JUNK_TITLE_PATTERNS:
        if re.search(pat, cleaned):
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

    # Bước 2: Kiểm tra từ khóa sản phẩm cốt lõi
    # 2.1 Xử lý đặc thù cho dòng máy quay bỏ túi (Pocket 3, Pocket 2, Pocket 4...)
    pocket_match = re.search(r"pocket\s*(\d+)", kw_lower)
    if pocket_match:
        pocket_num = pocket_match.group(1)
        # Bắt buộc phải có chữ "pocket" và số phiên bản (hoặc pocket3)
        has_pocket = bool(re.search(r"\bpocket\b", title_lower))
        has_num = bool(re.search(rf"\b{pocket_num}\b", title_lower) or re.search(rf"pocket\s*{pocket_num}", title_lower))
        if not (has_pocket and has_num):
            return False
        # Chặn nếu là phiên bản pocket khác (ví dụ tìm pocket 3 nhưng title ghi rõ pocket 4, pocket 2)
        other_nums = [n for n in ["1", "2", "3", "4", "5"] if n != pocket_num]
        for on in other_nums:
            if re.search(rf"\bpocket\s*{on}\b", title_lower):
                return False
    else:
        # 2.2 Cho phép thương hiệu tiền tố (dji, osmo, apple) là tùy chọn nếu các từ định danh cốt lõi đã đủ
        optional_brands = {"dji", "osmo", "apple"}
        core_kw_parts = [p for p in kw_lower.split() if p and p not in optional_brands]
        if len(core_kw_parts) >= 2:
            if not all(part in title_lower for part in core_kw_parts):
                return False
        else:
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


def extract_facebook_post_id(url: str, source_listing_id: str = "") -> str:
    """
    Trích xuất Post ID duy nhất từ Facebook URL hoặc source_listing_id.
    Hỗ trợ các định dạng:
    - /posts/{id}
    - /permalink.php?story_fbid={id}
    - fbid={id}
    - set=pcb.{id} hoặc set=gm.{id}
    - multi_permalinks={id}
    """
    if source_listing_id and str(source_listing_id).isdigit():
        return str(source_listing_id)
    if not url:
        return ""
    m = re.search(r"/posts/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"story_fbid=(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"set=(?:gm|pcb)\.(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"multi_permalinks=(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"fbid=(\d+)", url)
    if m:
        return m.group(1)
    return ""


def parse_facebook_time(
    raw_text: str = "",
    aria_label: str = "",
    reference_time: Optional[datetime] = None
) -> Tuple[Optional[datetime], str]:
    """
    Bóc tách thời gian đăng bài thật của Facebook từ chuỗi text hoặc aria-label.
    Hỗ trợ:
    - Vừa xong / just now
    - Phút: N phút / N phút trước
    - Giờ: N giờ / N giờ trước
    - Hôm qua: hôm qua lúc H:M
    - Ngày: N ngày / N ngày trước
    - Ngày cụ thể trong năm: 18 tháng 9 / 18 thg 9 / 19 Tháng 9 lúc 04:40
    - Tuần: N tuần / N tuần trước
    - Tháng: N tháng trước
    """
    now = reference_time or datetime.utcnow()
    combined = f"{aria_label} {raw_text}".strip()
    if not combined:
        return None, ""

    # Gỡ bỏ các ký tự ẩn zero-width và combining diacritics chống cào dữ liệu của Facebook
    clean = re.sub(r'[\u0300-\u036f\u200b-\u200f\ufeff\u034f]', '', combined)
    clean_lower = clean.lower()

    # 1. "vừa xong" / "just now"
    if "vừa xong" in clean_lower or "just now" in clean_lower:
        return now, "vừa xong"

    # 2. Phút: "15 phút" / "15 phút trước" / "15 mins"
    m_min = re.search(r"(\d+)\s*(?:phút|min|m\b)", clean_lower)
    if m_min and not re.search(r"\b\d+\s*(?:ngày|tháng|tuần)", clean_lower):
        mins = int(m_min.group(1))
        dt = now - timedelta(minutes=mins)
        return dt, f"{mins} phút trước"

    # 3. Giờ: "2 giờ" / "2 giờ trước" / "2 hrs"
    m_hr = re.search(r"(\d+)\s*(?:giờ|tiếng|hr|h\b)", clean_lower)
    if m_hr and not re.search(r"\b\d+\s*(?:ngày|tháng|tuần)", clean_lower):
        hrs = int(m_hr.group(1))
        dt = now - timedelta(hours=hrs)
        return dt, f"{hrs} giờ trước"

    # 4. Hôm qua: "hôm qua lúc 14:30" / "yesterday at 14:30"
    if "hôm qua" in clean_lower or "yesterday" in clean_lower:
        m_time = re.search(r"(\d{1,2}):(\d{2})", clean)
        hour = int(m_time.group(1)) if m_time else 12
        minute = int(m_time.group(2)) if m_time else 0
        now_vn = now + timedelta(hours=7)
        dt_vn = now_vn - timedelta(days=1)
        dt_vn = dt_vn.replace(hour=hour, minute=minute, second=0, microsecond=0)
        dt_utc = dt_vn - timedelta(hours=7)
        time_str = f"hôm qua lúc {hour:02d}:{minute:02d}" if m_time else "hôm qua"
        return dt_utc, time_str

    # 5. Ngày cụ thể trong năm (Tiếng Việt & Tiếng Anh):
    # VD: "Thứ bảy, 19 Tháng 9, 2026 lúc 04:40" hoặc "18 tháng 9 lúc 15:30" hoặc "18 thg 9" hoặc "18 Sep"
    m_date = re.search(
        r"(\d{1,2})\s*(?:tháng|thg)\s*(\d{1,2})(?:[,\s]*(\d{4}))?(?:\s*lúc\s*(\d{1,2}):(\d{2}))?",
        clean_lower
    )
    if m_date:
        day = int(m_date.group(1))
        month = int(m_date.group(2))
        now_vn = now + timedelta(hours=7)
        year = int(m_date.group(3)) if m_date.group(3) else now_vn.year
        hour = int(m_date.group(4)) if m_date.group(4) else 12
        minute = int(m_date.group(5)) if m_date.group(5) else 0

        # Nếu không ghi năm mà tháng lớn hơn tháng hiện tại -> ngày thuộc năm trước
        if not m_date.group(3) and month > now_vn.month:
            year -= 1

        try:
            dt_vn = datetime(year, month, day, hour, minute)
            dt_utc = dt_vn - timedelta(hours=7)
            time_str = f"{day:02d}/{month:02d}/{year}"
            if m_date.group(4):
                time_str = f"{hour:02d}:{minute:02d} {time_str}"
            return dt_utc, time_str
        except ValueError:
            pass

    # Tiếng Anh: "September 18 at 4:40 AM" / "18 September" / "18 Sep"
    months_en = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    m_en = re.search(
        r"(?:(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}))(?:[,\s]*(\d{4}))?",
        clean_lower
    )
    if m_en:
        day = int(m_en.group(1) or m_en.group(4))
        mon_str = (m_en.group(2) or m_en.group(3))[:3]
        month = months_en.get(mon_str, 1)
        now_vn = now + timedelta(hours=7)
        year = int(m_en.group(5)) if m_en.group(5) else now_vn.year
        if not m_en.group(5) and month > now_vn.month:
            year -= 1
        try:
            dt_vn = datetime(year, month, day, 12, 0)
            dt_utc = dt_vn - timedelta(hours=7)
            return dt_utc, f"{day:02d}/{month:02d}/{year}"
        except ValueError:
            pass

    # 6. Ngày trước: "3 ngày" / "3 ngày trước" / "3 days"
    m_day = re.search(r"(\d+)\s*(?:ngày|day|d\b)", clean_lower)
    if m_day and not re.search(r"(?:tháng|thg)", clean_lower):
        days = int(m_day.group(1))
        dt = now - timedelta(days=days)
        return dt, f"{days} ngày trước"

    # 7. Tuần: "2 tuần" / "2 tuần trước" / "2 weeks"
    m_wk = re.search(r"(\d+)\s*(?:tuần|week|w\b)", clean_lower)
    if m_wk:
        weeks = int(m_wk.group(1))
        dt = now - timedelta(weeks=weeks)
        return dt, f"{weeks} tuần trước"

    # 8. Tháng trước: "1 tháng trước"
    m_mon = re.search(r"(\d+)\s*(?:tháng|month)\s*trước", clean_lower)
    if m_mon:
        mons = int(m_mon.group(1))
        dt = now - timedelta(days=30 * mons)
        return dt, f"{mons} tháng trước"

    return None, clean[:60]


