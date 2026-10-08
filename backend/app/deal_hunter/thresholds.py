from dataclasses import dataclass
from typing import List, Dict

@dataclass
class CategoryThreshold:
    category_code: str
    min_profit: float         # Lợi nhuận tối thiểu kỳ vọng (VND)
    min_roi: float            # ROI tối thiểu (tỷ lệ, vd: 0.15 = 15%)
    min_confidence: int       # Confidence score tối thiểu (0-100)
    min_liquidity: int        # Liquidity score tối thiểu (0-100)
    acceptable_conditions: List[str]
    vn_cost_buffer: float     # Chi phí phát sinh ước tính cho nguồn VN (ship, test)
    goofish_landed_multiplier: float  # Hệ số landed cost cho Goofish (tỷ giá, trung gian, rủi ro)
    goofish_fixed_buffer: float       # Phí cố định cho Goofish (ship quốc tế, v.v.)

# Cấu hình ngưỡng linh hoạt theo từng Category
DEFAULT_THRESHOLDS: Dict[str, CategoryThreshold] = {
    "SMARTPHONE": CategoryThreshold(
        category_code="SMARTPHONE",
        min_profit=500_000.0,       # Tối thiểu 500k VNĐ lợi nhuận
        min_roi=0.10,              # Tối thiểu 10% ROI
        min_confidence=50,
        min_liquidity=40,
        acceptable_conditions=["LIKE_NEW", "EXCELLENT", "GOOD", "FAIR"],
        vn_cost_buffer=60_000.0,
        goofish_landed_multiplier=1.06,
        goofish_fixed_buffer=150_000.0
    ),
    "GPU": CategoryThreshold(
        category_code="GPU",
        min_profit=700_000.0,       # Tối thiểu 700k VNĐ lợi nhuận
        min_roi=0.12,              # Tối thiểu 12% ROI
        min_confidence=50,
        min_liquidity=35,
        acceptable_conditions=["LIKE_NEW", "EXCELLENT", "GOOD"],
        vn_cost_buffer=80_000.0,
        goofish_landed_multiplier=1.08,
        goofish_fixed_buffer=200_000.0
    ),
    "RAM": CategoryThreshold(
        category_code="RAM",
        min_profit=150_000.0,       # Tối thiểu 150k VNĐ lợi nhuận
        min_roi=0.18,              # Tối thiểu 18% ROI
        min_confidence=40,
        min_liquidity=30,
        acceptable_conditions=["LIKE_NEW", "EXCELLENT", "GOOD", "FAIR"],
        vn_cost_buffer=30_000.0,
        goofish_landed_multiplier=1.05,
        goofish_fixed_buffer=50_000.0
    ),
    "LAPTOP": CategoryThreshold(
        category_code="LAPTOP",
        min_profit=1_000_000.0,     # Tối thiểu 1tr VNĐ lợi nhuận
        min_roi=0.12,              # Tối thiểu 12% ROI
        min_confidence=50,
        min_liquidity=35,
        acceptable_conditions=["LIKE_NEW", "EXCELLENT", "GOOD"],
        vn_cost_buffer=100_000.0,
        goofish_landed_multiplier=1.08,
        goofish_fixed_buffer=250_000.0
    )
}

FALLBACK_THRESHOLD = CategoryThreshold(
    category_code="DEFAULT",
    min_profit=400_000.0,
    min_roi=0.12,
    min_confidence=45,
    min_liquidity=35,
    acceptable_conditions=["LIKE_NEW", "EXCELLENT", "GOOD", "FAIR"],
    vn_cost_buffer=50_000.0,
    goofish_landed_multiplier=1.07,
    goofish_fixed_buffer=100_000.0
)

def get_category_threshold(category_code: str = None) -> CategoryThreshold:
    """Trả về ngưỡng thẩm định theo category. Không hardcode mọi category chung một mức."""
    if not category_code:
        return FALLBACK_THRESHOLD
    key = category_code.upper().strip()
    return DEFAULT_THRESHOLDS.get(key, FALLBACK_THRESHOLD)
