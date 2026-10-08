import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

@dataclass
class SubCandidate:
    source_comment: str
    author: str
    extracted_price: float
    raw_text: str

def parse_vietnamese_price(text: str) -> Optional[float]:
    """
    Trích xuất giá tiền từ văn bản tiếng Việt.
    Hỗ trợ:
    - '12tr2' -> 12,200,000
    - '11m8' -> 11,800,000
    - '12.5tr' / '12,5 triệu' -> 12,500,000
    - '850k' -> 850,000
    - '12.200.000' -> 12,200,000
    """
    if not text:
        return None
    
    clean_text = text.lower()

    # 1. Dạng hỗn hợp: 12tr2, 11m8, 12củ5
    pattern_mixed = re.search(r'(\d+)\s*(?:tr|m|củ)\s*(\d+)', clean_text)
    if pattern_mixed:
        major = int(pattern_mixed.group(1))
        minor_str = pattern_mixed.group(2)
        # Nếu minor là 1 chữ số (vd: 2 -> 200,000; 5 -> 500,000)
        if len(minor_str) == 1:
            minor = int(minor_str) * 100_000
        elif len(minor_str) == 2:
            minor = int(minor_str) * 10_000
        else:
            minor = int(minor_str)
        return float(major * 1_000_000 + minor)

    # 2. Dạng thập phân triệu: 12.2tr, 12,5 triệu, 11.8m, 10 củ
    pattern_m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:tr|triệu|m|củ)', clean_text)
    if pattern_m:
        val_str = pattern_m.group(1).replace(',', '.')
        try:
            return float(val_str) * 1_000_000
        except ValueError:
            pass

    # 3. Dạng nghìn: 850k, 12500k, 500 nghìn
    pattern_k = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:k|nghìn|ngàn)', clean_text)
    if pattern_k:
        val_str = pattern_k.group(1).replace(',', '.')
        try:
            return float(val_str) * 1_000
        except ValueError:
            pass

    # 4. Dạng số đầy đủ có dấu chấm: 12.200.000 hoặc 12,200,000
    pattern_full = re.search(r'(\d{1,3}(?:[.,]\d{3}){1,3})', clean_text)
    if pattern_full:
        clean_num = re.sub(r'[.,]', '', pattern_full.group(1))
        try:
            val = float(clean_num)
            if val >= 50_000:  # Ngưỡng tối thiểu hợp lý
                return val
        except ValueError:
            pass

    return None

def analyze_comments(
    comments: List[Dict[str, Any]],
    seller_identifier: Optional[str] = None
) -> Tuple[Optional[float], List[SubCandidate]]:
    """
    Phân tích danh sách bình luận (Facebook post/listing):
    1. Nếu người bán chốt giá mới (vd: '12tr2 lấy nhanh', 'fix 11m5 bay') -> effective_seller_price.
    2. Nếu người khác rao bán ké (vd: 'em có con này 11tr8', 'ké 1 cây 11m') -> sub_candidates.
    """
    effective_seller_price: Optional[float] = None
    sub_candidates: List[SubCandidate] = []

    seller_intent_keywords = [
        "lấy nhanh", "bay nhanh", "chốt", "bán nhanh", "fix", "giảm còn", 
        "hạ giá", "xả", "pass nhanh", "để lại", "bớt"
    ]
    other_seller_keywords = [
        "ké", "em có", "mình có", "bán", "pass lại", "con này", "cây này"
    ]

    for c in comments or []:
        text = str(c.get("text", "")).strip()
        author = str(c.get("author", "")).strip()
        is_seller = bool(c.get("is_author") or (seller_identifier and author == seller_identifier))

        price = parse_vietnamese_price(text)
        if not price:
            continue

        text_lower = text.lower()

        # Trường hợp 1: Người bán tự giảm giá
        if is_seller or any(kw in text_lower for kw in seller_intent_keywords):
            if effective_seller_price is None or price < effective_seller_price:
                effective_seller_price = price

        # Trường hợp 2: Người khác rao bán cạnh tranh
        elif any(kw in text_lower for kw in other_seller_keywords):
            sub_candidates.append(
                SubCandidate(
                    source_comment=text,
                    author=author,
                    extracted_price=price,
                    raw_text=text
                )
            )

    return effective_seller_price, sub_candidates
