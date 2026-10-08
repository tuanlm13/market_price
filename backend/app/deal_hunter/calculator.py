from typing import Dict, Any, Optional
from decimal import Decimal
from .thresholds import CategoryThreshold, get_category_threshold

def calculate_acquisition_cost(
    source: str,
    asking_price: float,
    threshold: CategoryThreshold
) -> float:
    """
    Tính chi phí sở hữu (Acquisition Cost):
    - Goofish: Landed cost (giá mua + phí trung gian/vận chuyển quốc tế).
    - VN sources: asking price + configured cost buffer (ship nội địa, kiểm hàng).
    """
    src = (source or "").lower()
    if "goofish" in src or "xianyu" in src:
        # Landed cost cho Goofish
        return round(asking_price * threshold.goofish_landed_multiplier + threshold.goofish_fixed_buffer, 2)
    else:
        # Nguồn nội địa VN (Chợ Tốt, Facebook, v.v.)
        return round(asking_price + threshold.vn_cost_buffer, 2)

def calculate_financial_metrics(
    asking_price: float,
    acquisition_cost: float,
    market_stats: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministic math cho Deal Appraisal:
    - discount_vs_median
    - discount_vs_p25
    - discount_vs_quick_sell
    - expected_profit = quick_sell_price - acquisition_cost
    - roi = expected_profit / acquisition_cost
    - market_position
    """
    p10 = float(market_stats.get("p10") or 0.0)
    p25 = float(market_stats.get("p25") or 0.0)
    median = float(market_stats.get("median") or 0.0)
    quick_sell_price = float(market_stats.get("quick_sell_price") or 0.0)

    # Chiết khấu so với các mốc chuẩn
    discount_vs_median = round((median - asking_price) / median, 4) if median > 0 else 0.0
    discount_vs_p25 = round((p25 - asking_price) / p25, 4) if p25 > 0 else 0.0
    discount_vs_quick_sell = round((quick_sell_price - asking_price) / quick_sell_price, 4) if quick_sell_price > 0 else 0.0

    # Lợi nhuận và ROI
    expected_profit = round(quick_sell_price - acquisition_cost, 2)
    roi = round(expected_profit / acquisition_cost, 4) if acquisition_cost > 0 else 0.0

    # Định vị thị trường
    market_position = "ABOVE_MEDIAN"
    if p10 > 0 and asking_price <= p10:
        market_position = "DEEP_DISCOUNT"
    elif p25 > 0 and asking_price <= p25:
        market_position = "BELOW_P25"
    elif median > 0 and asking_price <= median:
        market_position = "BELOW_MEDIAN"
    elif median > 0 and asking_price <= median * 1.05:
        market_position = "AT_MEDIAN"

    return {
        "asking_price": asking_price,
        "acquisition_cost": acquisition_cost,
        "quick_sell_price": quick_sell_price,
        "expected_profit": expected_profit,
        "roi": roi,
        "discount_vs_median": discount_vs_median,
        "discount_vs_p25": discount_vs_p25,
        "discount_vs_quick_sell": discount_vs_quick_sell,
        "market_position": market_position
    }
