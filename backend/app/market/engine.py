import math
from typing import List, Dict, Any, Optional, Tuple

def _percentile(sorted_vals: List[float], p: float) -> float:
    """Computes percentile with linear interpolation using standard Python."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    k = (n - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f))

def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    """Calculates P10, P25, Median (P50), P75, P90 from a list of numeric prices."""
    if not values:
        return {
            "p10": 0.0, "p25": 0.0, "median": 0.0, "p75": 0.0, "p90": 0.0
        }
    sorted_vals = sorted(values)
    return {
        "p10": round(_percentile(sorted_vals, 10.0), 0),
        "p25": round(_percentile(sorted_vals, 25.0), 0),
        "median": round(_percentile(sorted_vals, 50.0), 0),
        "p75": round(_percentile(sorted_vals, 75.0), 0),
        "p90": round(_percentile(sorted_vals, 90.0), 0),
    }

def filter_outliers_iqr(values: List[float]) -> Tuple[List[float], List[float]]:
    """
    Tukey's IQR filter:
    Identifies inliers within [Q1 - 1.5 * IQR, Q3 + 1.5 * IQR].
    Returns (inliers, outliers).
    """
    if len(values) < 4:
        return values, []

    sorted_vals = sorted(values)
    q25 = _percentile(sorted_vals, 25.0)
    q75 = _percentile(sorted_vals, 75.0)
    iqr = q75 - q25

    lower_bound = max(0.0, q25 - (1.5 * iqr))
    upper_bound = q75 + (1.5 * iqr)

    inliers = [v for v in values if lower_bound <= v <= upper_bound]
    outliers = [v for v in values if v < lower_bound or v > upper_bound]
    return inliers, outliers

def calculate_fair_and_quick_sell(inliers: List[float], percentiles: Dict[str, float]) -> Tuple[float, float]:
    """
    Calculates Fair Market Price (trimmed mean) and Quick Sell Price (sub-market fast liquidation).
    """
    if not inliers:
        return 0.0, 0.0

    # Fair Price: mean of inliers
    fair_price = round(sum(inliers) / float(len(inliers)), 0)

    # Quick Sell Price: target P15-P20 or 90% of P25
    median = percentiles.get("median", 0.0)
    p25 = percentiles.get("p25", 0.0)
    p10 = percentiles.get("p10", 0.0)

    if p10 > 0 and p25 > 0:
        quick_sell = round((p10 + p25) / 2.0, 0)
    elif median > 0:
        quick_sell = round(median * 0.88, 0)
    else:
        quick_sell = round(fair_price * 0.88, 0)

    return fair_price, quick_sell

def calculate_confidence_score(sample_size: int, source_count: int, recency_days: float = 7.0) -> int:
    """
    Computes Market Confidence (0 - 100):
    - Sample size (up to 50 pts)
    - Source diversity (up to 30 pts)
    - Recency (up to 20 pts)
    """
    sample_pts = min(50, sample_size * 2.5)
    source_pts = min(30, source_count * 10)
    recency_pts = 20 if recency_days <= 7 else (10 if recency_days <= 30 else 5)
    total = int(round(sample_pts + source_pts + recency_pts))
    return min(100, max(10, total))

def calculate_liquidity_score(sample_size: int, active_ratio: float = 0.8) -> int:
    """Computes Liquidity (0 - 100) based on listing volume and turnover activity."""
    base = min(60, sample_size * 3)
    activity = int(active_ratio * 40)
    return min(100, max(15, base + activity))

def generate_price_histogram(prices: List[float], num_buckets: int = 8) -> List[Dict[str, Any]]:
    """Generates price histogram buckets with listing counts."""
    if not prices:
        return []

    min_p = min(prices)
    max_p = max(prices)
    if min_p == max_p:
        return [{
            "bucket_min": min_p,
            "bucket_max": max_p,
            "label": f"{int(min_p):,} đ",
            "count": len(prices)
        }]

    step = (max_p - min_p) / float(num_buckets)
    buckets = []
    for i in range(num_buckets):
        b_min = min_p + (i * step)
        b_max = min_p + ((i + 1) * step)
        if i == num_buckets - 1:
            cnt = sum(1 for p in prices if b_min <= p <= b_max)
        else:
            cnt = sum(1 for p in prices if b_min <= p < b_max)

        label = f"{int(b_min / 1000000):,}M - {int(b_max / 1000000):,}M" if b_max >= 1000000 else f"{int(b_min):,} - {int(b_max):,}"
        buckets.append({
            "bucket_min": round(b_min, 0),
            "bucket_max": round(b_max, 0),
            "label": label,
            "count": cnt
        })

    return buckets
