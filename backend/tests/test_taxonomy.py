import pytest
from fastapi.testclient import TestClient
from main import app
from app.taxonomy.conditions import CONDITION_DEFINITIONS, get_condition_by_code
from app.taxonomy.attributes import generate_canonical_id, CATEGORY_SCHEMA_SPECS

client = TestClient(app)

def test_condition_taxonomy():
    assert len(CONDITION_DEFINITIONS) == 9
    codes = [c["code"] for c in CONDITION_DEFINITIONS]
    for required_code in ["N0", "N1", "U0", "U1", "U2", "U3", "R0", "D0", "P0"]:
        assert required_code in codes

    n0 = get_condition_by_code("N0")
    assert n0["name"] == "New Sealed"
    assert n0["grade"] == "NEW"

    u1 = get_condition_by_code("u1")
    assert u1["name"] == "Used Good"
    assert u1["grade"] == "USED"

def test_canonical_id_generation():
    cid1 = generate_canonical_id("Apple", "iPhone 16", "128GB", "VN/A", "N0")
    assert cid1 == "APPLE|IPHONE-16|128GB|VNA|N0"

    cid2 = generate_canonical_id("MSI", "RTX 4060", "8GB", "Gaming X", "U1")
    assert cid2 == "MSI|RTX-4060|8GB|GAMING-X|U1"

    cid3 = generate_canonical_id("Samsung", "DDR4-ECC", "32GB-3200", "2Rx4", "N0")
    assert cid3 == "SAMSUNG|DDR4-ECC|32GB-3200|2RX4|N0"

def test_category_schema_attributes():
    assert "SMARTPHONE" in CATEGORY_SCHEMA_SPECS
    assert "GPU" in CATEGORY_SCHEMA_SPECS
    assert "RAM" in CATEGORY_SCHEMA_SPECS

    sp_keys = CATEGORY_SCHEMA_SPECS["SMARTPHONE"]["required_keys"] + CATEGORY_SCHEMA_SPECS["SMARTPHONE"]["optional_keys"]
    assert "storage" in sp_keys
    assert "battery_health" in sp_keys
    assert "warranty" in sp_keys

    gpu_keys = CATEGORY_SCHEMA_SPECS["GPU"]["required_keys"] + CATEGORY_SCHEMA_SPECS["GPU"]["optional_keys"]
    assert "vram" in gpu_keys
    assert "mining_history" in gpu_keys

    ram_keys = CATEGORY_SCHEMA_SPECS["RAM"]["required_keys"] + CATEGORY_SCHEMA_SPECS["RAM"]["optional_keys"]
    assert "capacity" in ram_keys
    assert "frequency" in ram_keys
    assert "ecc" in ram_keys

def test_api_get_categories():
    response = client.get("/categories?scope=market")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    slugs = [c["slug"] for c in data]
    assert "smartphone" in slugs
    assert "gpu" in slugs
    assert "ram" in slugs

def test_api_get_brands():
    response = client.get("/brands")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 4
    slugs = [b["slug"] for b in data]
    assert "apple" in slugs
    assert "msi" in slugs
    assert "samsung" in slugs

def test_api_get_products():
    response = client.get("/products?scope=market")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    names = [p["name"] for p in data]
    assert "iPhone 16" in names
    assert "MSI GeForce RTX 4060" in names

def test_api_get_product_detail():
    # Find iPhone 16
    list_resp = client.get("/taxonomy/products")
    assert list_resp.status_code == 200
    products = list_resp.json()
    iphone = next(p for p in products if p["name"] == "iPhone 16")

    detail_resp = client.get(f"/taxonomy/products/{iphone['id']}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["name"] == "iPhone 16"
    assert data["brand"]["slug"] == "apple"
    assert data["category"]["slug"] == "smartphone"
    assert len(data["variants"]) >= 2
    skus = [v["sku"] for v in data["variants"]]
    assert "IPHONE16-128GB-VNA" in skus
    assert "IPHONE16-256GB-VNA" in skus

def test_api_get_variants():
    response = client.get("/variants")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 4
    skus = [v["sku"] for v in data]
    assert "IPHONE16-128GB-VNA" in skus
    assert "MSI-RTX4060-GAMING-X-8G" in skus
    assert "SAMSUNG-DDR4-32GB-ECC-3200-2RX4" in skus

def test_api_get_conditions():
    response = client.get("/conditions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 9
    codes = [c["code"] for c in data]
    assert "N0" in codes
    assert "U1" in codes
    assert "P0" in codes

def test_api_get_market_segments():
    response = client.get("/market-segments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 7
    keys = [s["canonical_key"] for s in data]
    assert any("IPHONE16" in k for k in keys)
    assert any("RTX4060" in k for k in keys)
    assert any("SAMSUNG" in k for k in keys)
