import re
from typing import Tuple, Optional

# Patterns for fake / dummy placeholder prices
DUMMY_PRICE_PATTERNS = [
    r"^0+(\s*đ|\s*vnd)?$",
    r"^1+(\s*đ|\s*vnd)?$",
    r"^123+(\s*đ|\s*vnd)?$",
    r"^1234+(\s*đ|\s*vnd)?$",
    r"^12345+(\s*đ|\s*vnd)?$",
    r"^123456+(\s*đ|\s*vnd)?$",
    r"^777+(\s*đ|\s*vnd)?$",
    r"^888+(\s*đ|\s*vnd)?$",
    r"^999+(\s*đ|\s*vnd)?$",
    r"^999999+(\s*đ|\s*vnd)?$",
    r"^111111+(\s*đ|\s*vnd)?$",
]

INBOX_KEYWORDS = [
    "inbox", "ib", "liên hệ", "lh", "thương lượng", "thương lượng trực tiếp",
    "call", "alo", "nhắn tin", "thỏa thuận", "pm", "giá ib"
]

INSTALLMENT_KEYWORDS = [
    "trả góp", "trả trước", "chỉ từ", "hỗ trợ góp", "đưa trước", "góp 0%",
    "chỉ cần đưa", "trước chỉ", "góp từ", "góp chỉ", "bao nợ xấu", "đưa trước từ",
    "nhận máy trước", "góp qua cccd", "hồ sơ duyệt", "góp duyệt nhanh", "thanh toán đợt 1"
]

DEPOSIT_KEYWORDS = [
    "cọc", "đặt cọc", "tiền cọc", "deposit", "cọc giữ", "cọc ship", "cọc máy"
]

def parse_price(raw_text: Optional[str], default_currency: str = "VND") -> Tuple[Optional[float], str, bool, Optional[str]]:
    """
    Parses complex Vietnamese and Chinese marketplace prices into numeric amounts.
    Detects invalid, placeholder, inbox, or installment teaser prices.

    Returns:
        (clean_price, currency, price_valid, price_validity_reason)
    """
    if not raw_text:
        return None, default_currency, False, "EMPTY_PRICE"

    text = str(raw_text).strip().lower()

    # 1. Check for inbox / contact for price / hidden price with 'x' (vd: 14xxx, 6Trxxx)
    if re.search(r"\b\d+\s*x{2,}\b|\b\d+tr\s*x{2,}\b", text):
        return None, default_currency, False, "HIDDEN_PRICE_INBOX"

    for kw in INBOX_KEYWORDS:
        if kw in text:
            return None, default_currency, False, "INBOX_REQUIRED"

    # 2. Check for installment teaser
    for kw in INSTALLMENT_KEYWORDS:
        if kw in text:
            return None, default_currency, False, "INSTALLMENT_TEASER"

    # 3. Check for deposit only
    for kw in DEPOSIT_KEYWORDS:
        if kw in text:
            return None, default_currency, False, "DEPOSIT_ONLY"

    # 4. Check dummy numbers
    clean_digits = re.sub(r"[.,\s]", "", text)
    clean_digits_no_curr = re.sub(r"[đvndcny¥元]+", "", clean_digits)
    for p in DUMMY_PRICE_PATTERNS:
        if re.match(p, clean_digits):
            return None, default_currency, False, "PLACEHOLDER_PRICE"
    if clean_digits_no_curr in ("1", "0", "123", "1234", "12345", "123456", "999999", "77777", "88888"):
        return None, default_currency, False, "PLACEHOLDER_PRICE"

    # 5. Detect currency
    currency = default_currency
    if "¥" in text or "cny" in text or "元" in text or "万" in text:
        currency = "CNY"
    elif "đ" in text or "vnd" in text or "tr" in text or "triệu" in text or "k" in text:
        currency = "VND"

    # 6. Parse Chinese Wan (万) -> 1万 = 10,000 CNY
    # e.g., 1.85万 -> 18,500 CNY
    wan_match = re.search(r"(\d+(?:[.,]\d+)?)\s*万", text)
    if wan_match:
        val_str = wan_match.group(1).replace(",", ".")
        try:
            return float(val_str) * 10000.0, "CNY", True, None
        except ValueError:
            pass

    # Chinese Yuan direct: ¥5000 or 5000元
    cny_match = re.search(r"(?:¥\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*(?:元|cny))", text)
    if cny_match:
        val_str = (cny_match.group(1) or cny_match.group(2)).replace(",", ".")
        try:
            return float(val_str), "CNY", True, None
        except ValueError:
            pass

    # 7. Parse Vietnamese shorthand:
    # Pattern 1: 18tr5, 18 triệu 5, 18 tr 500
    tr_split_match = re.search(r"(\d+)\s*(?:tr|triệu)\s*(\d+)", text)
    if tr_split_match:
        million_part = float(tr_split_match.group(1))
        sub_str = tr_split_match.group(2)
        if len(sub_str) == 1:  # 18tr5 -> 18.5 tr
            sub_part = float(sub_str) * 100_000.0
        elif len(sub_str) == 2:  # 18tr50 -> 18.5 tr
            sub_part = float(sub_str) * 10_000.0
        elif len(sub_str) == 3:  # 18tr500 -> 18.5 tr
            sub_part = float(sub_str) * 1_000.0
        else:
            sub_part = float(sub_str)
        total = (million_part * 1_000_000.0) + sub_part
        return total, "VND", True, None

    # Pattern 2: 18.5tr, 18,5tr, 18.5 triệu
    tr_dec_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:tr|triệu)", text)
    if tr_dec_match:
        val_str = tr_dec_match.group(1).replace(",", ".")
        try:
            return float(val_str) * 1_000_000.0, "VND", True, None
        except ValueError:
            pass

    # Pattern 3: 18500k, 18.500k
    k_match = re.search(r"(\d+(?:[.,]\d+)?)\s*k(?:\b|\s|đ)", text)
    if k_match:
        val_str = k_match.group(1).replace(".", "").replace(",", ".")
        try:
            return float(val_str) * 1_000.0, "VND", True, None
        except ValueError:
            pass

    # Pattern 4: Standard numeric string: 18.500.000 đ, 31,500,000, 31500000
    cleaned = re.sub(r"[^\d.,]", "", text)
    if cleaned:
        # Check standard dot-separated thousands: 18.500.000
        if cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")
        elif cleaned.count(",") > 1:
            cleaned = cleaned.replace(",", "")
        elif "." in cleaned and "," in cleaned:
            # 18,500.00 or 18.500,00
            if cleaned.rfind(".") > cleaned.rfind(","):
                cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "." in cleaned:
            parts = cleaned.split(".")
            if len(parts[-1]) == 3:  # e.g. 500.000
                cleaned = cleaned.replace(".", "")
        elif "," in cleaned:
            parts = cleaned.split(",")
            if len(parts[-1]) == 3:  # e.g. 500,000
                cleaned = cleaned.replace(",", "")

        try:
            val = float(cleaned)
            # Suspicious threshold check: Không có thiết bị công nghệ nào giá dưới 50.000đ
            if val < 50_000.0 and currency == "VND":
                return None, currency, False, "UNREASONABLY_LOW_PRICE"
            return val, currency, True, None
        except ValueError:
            pass

    return None, default_currency, False, "UNPARSEABLE_PRICE"
