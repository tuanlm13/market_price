import re
from typing import Tuple, Optional
from app.normalization.rules.price_parser import parse_price

SELLER_PRICE_PATTERNS = [
    r"\b(giá chuẩn|không fix|đúng giá|chốt \d+|giá công khai|bán đúng giá|inbox giá|đã ib|check ib|không bớt)\b"
]

NEGOTIATION_PATTERNS = [
    r"\b(fix|bớt|bớt không|còn fix|giá fix|bớt xăng xe|có bớt không|thương lượng thêm|chốt giá|trả giá)\b"
]

COMPETING_OFFER_PATTERNS = [
    r"\b(shop khác bán|chỗ kia bán|rẻ hơn|bên kia bán|đắt quá|giá này mua được|chát quá|trên shopee có)\b"
]

SOLD_SIGNAL_PATTERNS = [
    r"\b(đã bán|sold|bay rồi|đã bay|hết hàng|chốt rồi|nhận cọc rồi|đã cọc)\b"
]

WTB_PATTERNS = [
    r"\b(cần mua|mua luôn|còn không|còn hàng không|inbox mình|ship cod không|cho xin sđt|ở đâu qua xem)\b"
]

PRICE_REFERENCE_PATTERNS = [
    r"\b(giá mới|giá hãng|đập hộp bây giờ|hàng chính hãng bán)\b"
]

def classify_comment_intent(raw_text: str) -> Tuple[str, Optional[float], float]:
    """
    Classifies a raw comment:
    NEGOTIATION, SELLER_PRICE, COMPETING_OFFER, SOLD_SIGNAL, PRICE_REFERENCE, WTB, NOISE.
    Returns: (classification, extracted_price, confidence)
    """
    text = (raw_text or "").strip().lower()
    if not text or len(text) < 2:
        return "NOISE", None, 1.0

    # Extract price if mentioned in comment
    price, _, is_valid, _ = parse_price(text)
    extracted_price = price if is_valid else None

    # 1. Sold signal
    for p in SOLD_SIGNAL_PATTERNS:
        if re.search(p, text):
            return "SOLD_SIGNAL", extracted_price, 0.95

    # 2. Seller response / price statement (takes precedence over general negotiation keywords)
    for p in SELLER_PRICE_PATTERNS:
        if re.search(p, text):
            return "SELLER_PRICE", extracted_price, 0.90

    # 3. Negotiation offer/ask
    for p in NEGOTIATION_PATTERNS:
        if re.search(p, text):
            return "NEGOTIATION", extracted_price, 0.90

    # 4. Competing offer / market critique
    for p in COMPETING_OFFER_PATTERNS:
        if re.search(p, text):
            return "COMPETING_OFFER", extracted_price, 0.85

    # 5. Buyer intent / WTB
    for p in WTB_PATTERNS:
        if re.search(p, text):
            return "WTB", extracted_price, 0.85

    # 6. Price reference
    for p in PRICE_REFERENCE_PATTERNS:
        if re.search(p, text):
            return "PRICE_REFERENCE", extracted_price, 0.85

    # If has extracted price but no specific keywords, could be a negotiation offer
    if extracted_price:
        return "NEGOTIATION", extracted_price, 0.75

    return "NOISE", None, 0.80
