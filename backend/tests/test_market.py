import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal

from app.market.engine import (
    calculate_percentiles, filter_outliers_iqr, calculate_fair_and_quick_sell,
    calculate_confidence_score, calculate_liquidity_score, generate_price_histogram
)
from app.market.service import (
    get_market_analytics, get_product_explorer_hierarchy,
    get_paginated_raw_listings, get_data_quality_and_operations
)

client = TestClient(app)

# ==============================================================================
# 1. MARKET ENGINE UNIT TESTS
# ==============================================================================

def test_percentiles_calculation():
    # Known dataset: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
    prices = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    pct = calculate_percentiles(prices)
    assert pct["median"] == 55.0
    assert pct["p25"] <= pct["median"]
    assert pct["p75"] >= pct["median"]
    assert pct["p10"] <= pct["p25"]
    assert pct["p90"] >= pct["p75"]


def test_outlier_filtering_iqr():
    # Normal prices around 18M - 20M, with one extreme fake outlier 300M
    normal_prices = [18_000_000.0, 18_500_000.0, 19_000_000.0, 19_200_000.0, 19_800_000.0, 20_000_000.0]
    outlier_prices = [300_000_000.0]
    combined = normal_prices + outlier_prices

    inliers, outliers = filter_outliers_iqr(combined)
    assert 300_000_000.0 in outliers
    assert len(inliers) == len(normal_prices)


def test_fair_and_quick_sell_pricing():
    prices = [18_000_000.0, 18_500_000.0, 19_000_000.0, 19_500_000.0, 20_000_000.0]
    pct = calculate_percentiles(prices)
    fair, quick = calculate_fair_and_quick_sell(prices, pct)

    # Fair price should be average: 19.0M
    assert fair == 19_000_000.0
    # Quick sell price must be below fair price to enable fast 24h liquidation
    assert quick < fair
    assert quick >= 16_000_000.0


def test_confidence_and_liquidity_scoring():
    # Large sample + multiple sources -> High confidence
    conf_high = calculate_confidence_score(sample_size=35, source_count=4, recency_days=3.0)
    assert conf_high >= 90

    # Small sample -> Lower confidence (never overstate confidence with small samples)
    conf_low = calculate_confidence_score(sample_size=2, source_count=1, recency_days=20.0)
    assert conf_low < 50

    # Liquidity score
    liq = calculate_liquidity_score(sample_size=25, active_ratio=0.85)
    assert 0 <= liq <= 100


def test_price_histogram_generation():
    prices = [100.0, 110.0, 120.0, 150.0, 180.0, 200.0]
    buckets = generate_price_histogram(prices, num_buckets=4)
    assert len(buckets) == 4
    total_count = sum(b["count"] for b in buckets)
    assert total_count == len(prices)


# ==============================================================================
# 2. MARKET API ENDPOINT TESTS
# ==============================================================================

def test_api_market_analytics():
    # Test search for iPhone 16 / New Sealed
    resp = client.get("/market/analytics?product_id=1&condition_id=1&days=30")
    assert resp.status_code == 200
    data = resp.json()

    assert "overview" in data
    overview = data["overview"]
    assert "p10" in overview
    assert "p25" in overview
    assert "median" in overview
    assert "p75" in overview
    assert "p90" in overview
    assert "fair_price" in overview
    assert "quick_sell_price" in overview
    assert "confidence" in overview
    assert "liquidity" in overview
    assert "trend_percentage" in overview

    assert "histogram" in data
    assert "source_comparison" in data
    assert "trend_history" in data
    assert "metadata" in data
    assert data["metadata"]["calculation_version"] == "v1.0.0"


def test_api_market_explorer():
    resp = client.get("/market/explorer")
    assert resp.status_code == 200
    hierarchy = resp.json()
    assert isinstance(hierarchy, list)
    assert len(hierarchy) > 0
    # Top level is category
    cat = hierarchy[0]
    assert "name" in cat
    assert "brands" in cat


def test_api_market_listings_pagination():
    resp = client.get("/market/listings?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_api_market_quality():
    resp = client.get("/market/quality")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_raw" in data
    assert "total_normalized" in data
    assert "review_queue" in data
    assert "invalid_prices" in data
    assert "collectors" in data
    assert "overall_market_confidence" in data
