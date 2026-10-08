import re
from typing import Tuple, Optional

# Mapping to Phase 0 Taxonomy Condition Codes:
# N0: New Sealed
# N1: New Open Box
# U0: Like New (99%)
# U1: Used Good (95%)
# U2: Used Normal (90%)
# U3: Used Fair (80%)
# P0: Parts Only
CONDITION_PATTERNS = [
    # 1. P0 - Parts Only / Xác máy
    ("P0", [
        r"\b(xác|bán xác|rã xác|hỏng màn|chết nguồn|mất nguồn|lỗi main|dính icloud|dính tài khoản|nát|bể nát|cháy nổ|vỡ màn|hư màn|尸体)\b"
    ], 0.95),

    # 2. N0 - New Sealed
    ("N0", [
        r"\b(nguyên seal|chưa bóc|chưa active|mới 100%|new seal|chưa khui|fullbox new|chưa bóc seal|chưa kích hoạt|全新|未拆封)\b"
    ], 0.95),

    # 3. N1 - New Open Box
    ("N1", [
        r"\b(open box|openbox|mới active|vừa bóc|mở hộp|đập hộp|kích hoạt online|chưa qua sử dụng|99\.9%|active gần)\b"
    ], 0.90),

    # 4. U0 - Like New (99%)
    ("U0", [
        r"\b(99%|like new|likenew|đẹp keng|leng keng|keng xà beng|không vết xước|gần như mới|zin all|99新|几乎全新)\b"
    ], 0.90),

    # 5. U1 - Used Good (95%)
    ("U1", [
        r"\b(95%|rất đẹp|phẩy nhẹ|trầy nhẹ|xước dăm|xước nhẹ|dăm nhẹ|95新)\b"
    ], 0.85),

    # 6. U2 - Used Normal (90%)
    ("U2", [
        r"\b(90%|cũ theo thời gian|cấn nhẹ|trầy viền|tróc sơn|pin 8x|90新)\b"
    ], 0.85),

    # 7. U3 - Used Fair (80%)
    ("U3", [
        r"\b(80%|cấn góc|móp góc|màn ám nhẹ|ám nhẹ|xấu|cũ kỹ|vỏ xấu|80新)\b"
    ], 0.80),
]

# Aliases dictionary for human-readable codes mapping to Phase 0
CODE_ALIASES = {
    "NEW_SEAL": "N0",
    "OPEN_BOX": "N1",
    "LIKE_NEW_99": "U0",
    "VERY_GOOD_95": "U1",
    "GOOD_90": "U2",
    "FAIR_80": "U3",
    "FOR_PARTS": "P0",
}

def map_condition(text: str) -> Tuple[Optional[str], float, bool]:
    """
    Maps raw text to DimCondition code without guessing.
    Returns: (condition_code, confidence, manual_review_required)
    """
    if not text:
        return None, 0.0, True

    norm_text = text.lower()

    for code, patterns, conf in CONDITION_PATTERNS:
        for p in patterns:
            if re.search(p, norm_text):
                return code, conf, False

    # No condition information found in text -> do NOT guess!
    return None, 0.5, True
