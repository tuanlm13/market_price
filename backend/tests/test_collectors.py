import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from app.collectors.chotot import ChoTotCollector
from app.collectors.goofish import GoofishCollector
from app.collectors.facebook_marketplace import FacebookMarketplaceCollector
from app.collectors.facebook_group import FacebookGroupCollector
from app.collectors.models import (
    FactRawListing, FactListingPriceSnapshot, FactRawComment, CollectorHealth
)
from app.taxonomy.models import DimSource

client = TestClient(app)

# ==============================================================================
# 1. PARSER UNIT TESTS (Mocked Payloads - No Internet Required)
# ==============================================================================

def test_chotot_parser():
    collector = ChoTotCollector()
    mock_payload = [
        {
            "list_id": 11223344,
            "subject": "iPhone 16 Pro Max 256GB Desert Titanium VN/A",
            "body": "Máy mới kích hoạt 2 tuần, fullbox nguyên hóa đơn.",
            "price": 31500000,
            "price_string": "31.500.000 đ",
            "account_name": "Nguyễn Văn A",
            "account_id": "acc_9988",
            "area_name": "Quận 1, TP Hồ Chí Minh",
            "date": 1712049200000,
            "category": 5010,
            "images": ["https://img.chotot.com/1.jpg"]
        }
    ]

    parsed = collector.parse(mock_payload)
    assert len(parsed) == 1
    item = parsed[0]
    assert item["source_listing_id"] == "11223344"
    assert "iPhone 16 Pro Max" in item["raw_title"]
    assert item["raw_price_text"] == "31.500.000 đ"
    assert item["raw_currency"] == "VND"
    assert item["seller_name_raw"] == "Nguyễn Văn A"
    assert item["seller_id_raw"] == "acc_9988"
    assert "Quận 1" in item["location_raw"]
    assert item["raw_metadata"]["category_id"] == 5010


def test_goofish_parser():
    collector = GoofishCollector()
    mock_payload = [
        {
            "id": "gf_889977",
            "title": "iPhone 16 128G 黑色 国行 在保",
            "description": "国行99新，无磕碰，电池100%，带原装配件",
            "price": "4999",
            "seller": "小鱼数码",
            "sellerId": "seller_7766",
            "location": "上海市浦东新区",
            "tags": ["二手手机", "在保"]
        }
    ]

    parsed = collector.parse(mock_payload)
    assert len(parsed) == 1
    item = parsed[0]
    assert item["source_listing_id"] == "gf_889977"
    assert "iPhone 16 128G" in item["raw_title"]
    assert item["raw_price_text"] == "4999"
    assert item["raw_currency"] == "CNY"
    assert item["seller_name_raw"] == "小鱼数码"
    assert item["location_raw"] == "上海市浦东新区"
    assert item["raw_metadata"]["source_platform"] == "goofish"


def test_facebook_marketplace_parser():
    collector = FacebookMarketplaceCollector()
    mock_payload = [
        {
            "item_id": "fb_item_554433",
            "title": "VGA RTX 4060 Asus Dual 8GB OC like new",
            "description": "Bảo hành chính hãng 24 tháng, bao test tại nhà.",
            "price": "7.200.000 ₫",
            "location": "Hà Nội",
            "seller": "Gamer Store",
            "seller_id": "seller_fb_123"
        }
    ]

    parsed = collector.parse(mock_payload)
    assert len(parsed) == 1
    item = parsed[0]
    assert item["source_listing_id"] == "fb_item_554433"
    assert "RTX 4060" in item["raw_title"]
    assert item["raw_price_text"] == "7.200.000 ₫"
    assert item["raw_currency"] == "VND"
    assert item["location_raw"] == "Hà Nội"


def test_facebook_group_parser_with_nested_comments():
    collector = FacebookGroupCollector()
    mock_payload = [
        {
            "post_id": "post_grp_1001",
            "author": "Trần Thị B",
            "author_id": "usr_456",
            "text": "Cần bán RTX 4060Ti 8GB giá 8.5tr còn bảo hành 2 năm.\nGiao dịch trực tiếp Cầu Giấy.",
            "price": "8.5tr",
            "comments": [
                {
                    "source_comment_id": "cmt_1001_1",
                    "author": "Lê Văn C",
                    "raw_text": "Còn fix không bạn ơi?",
                    "created_at_source": datetime.utcnow()
                },
                {
                    "source_comment_id": "cmt_1001_2",
                    "author": "Trần Thị B",
                    "raw_text": "Bớt 200k xăng xe nhé bác.",
                    "created_at_source": datetime.utcnow()
                }
            ]
        }
    ]

    parsed = collector.parse(mock_payload)
    assert len(parsed) == 1
    item = parsed[0]
    assert item["source_listing_id"] == "post_grp_1001"
    assert "RTX 4060Ti" in item["raw_title"]
    assert len(item["comments"]) == 2
    assert item["comments"][0]["source_comment_id"] == "cmt_1001_1"
    assert item["comments"][0]["raw_text"] == "Còn fix không bạn ơi?"


# ==============================================================================
# 2. PERSISTENCE, DEDUPLICATION & PRICE SNAPSHOT TESTS
# ==============================================================================

def test_persist_new_and_deduplication():
    db = SessionLocal()
    try:
        collector = ChoTotCollector()
        unique_id = f"test_ct_{int(datetime.utcnow().timestamp())}"

        mock_item = {
            "source_listing_id": unique_id,
            "url": f"https://www.chotot.com/{unique_id}.htm",
            "raw_title": "Tai nghe Sony WH-1000XM5 Fullbox",
            "raw_description": "Hàng chính hãng Sony VN.",
            "raw_price_text": "6.000.000 đ",
            "raw_currency": "VND",
            "seller_name_raw": "Shop Audio",
            "seller_id_raw": "acc_audio",
            "location_raw": "Hà Nội",
            "published_at": datetime.utcnow(),
            "raw_metadata": {"condition": "99%"},
            "comments": []
        }

        # First run: should create new listing + 1 price snapshot
        stats1 = collector.persist([mock_item], db)
        assert stats1["new"] == 1
        assert stats1["scanned"] == 1

        src = collector.get_source_record(db)
        listing = db.query(FactRawListing).filter(
            FactRawListing.source_id == src.id,
            FactRawListing.source_listing_id == unique_id
        ).first()
        assert listing is not None
        assert listing.raw_price_text == "6.000.000 đ"

        snapshots = db.query(FactListingPriceSnapshot).filter(
            FactListingPriceSnapshot.listing_id == listing.id
        ).all()
        assert len(snapshots) == 1
        assert snapshots[0].price_raw == "6.000.000 đ"

        # Second run: same price -> should update last_seen_at, NO new snapshot
        first_last_seen = listing.last_seen_at
        stats2 = collector.persist([mock_item], db)
        assert stats2["new"] == 0
        assert stats2["updated"] == 1

        snapshots_after_same = db.query(FactListingPriceSnapshot).filter(
            FactListingPriceSnapshot.listing_id == listing.id
        ).all()
        assert len(snapshots_after_same) == 1

        # Third run: price changed to 5.500.000 đ -> should create 2nd snapshot!
        mock_item_price_drop = {**mock_item, "raw_price_text": "5.500.000 đ"}
        stats3 = collector.persist([mock_item_price_drop], db)
        assert stats3["updated"] == 1

        db.refresh(listing)
        assert listing.raw_price_text == "5.500.000 đ"

        snapshots_after_drop = db.query(FactListingPriceSnapshot).filter(
            FactListingPriceSnapshot.listing_id == listing.id
        ).order_by(FactListingPriceSnapshot.captured_at.asc()).all()
        assert len(snapshots_after_drop) == 2
        assert snapshots_after_drop[0].price_raw == "6.000.000 đ"
        assert snapshots_after_drop[1].price_raw == "5.500.000 đ"

    finally:
        db.close()


def test_persist_comments_deduplication():
    db = SessionLocal()
    try:
        collector = FacebookGroupCollector()
        post_id = f"test_fb_post_{int(datetime.utcnow().timestamp())}"

        mock_item = {
            "source_listing_id": post_id,
            "url": f"https://www.facebook.com/groups/post/{post_id}",
            "raw_title": "Thanh lý màn hình LG 27GP850",
            "raw_description": "Màn hình 2K 165Hz IPS ngon lành cành đào.",
            "raw_price_text": "5.2tr",
            "raw_currency": "VND",
            "seller_name_raw": "User Tech",
            "seller_id_raw": "u1",
            "location_raw": "TP HCM",
            "published_at": datetime.utcnow(),
            "raw_metadata": {},
            "comments": [
                {
                    "source_comment_id": f"c_{post_id}_1",
                    "author": "Buyer A",
                    "raw_text": "Còn bảo hành bao lâu bạn?",
                    "created_at_source": datetime.utcnow()
                }
            ]
        }

        # Run 1: 1 comment saved
        stats1 = collector.persist([mock_item], db)
        assert stats1["comments"] == 1

        src = collector.get_source_record(db)
        listing = db.query(FactRawListing).filter(
            FactRawListing.source_id == src.id,
            FactRawListing.source_listing_id == post_id
        ).first()

        db_comments = db.query(FactRawComment).filter(FactRawComment.listing_id == listing.id).all()
        assert len(db_comments) == 1
        assert db_comments[0].source_comment_id == f"c_{post_id}_1"

        # Run 2: Re-persisting same comment + new comment -> only new comment saved
        mock_item["comments"].append({
            "source_comment_id": f"c_{post_id}_2",
            "author": "Buyer B",
            "raw_text": "Inbox mình sđt nhé.",
            "created_at_source": datetime.utcnow()
        })
        stats2 = collector.persist([mock_item], db)
        assert stats2["comments"] == 1

        db_comments_after = db.query(FactRawComment).filter(FactRawComment.listing_id == listing.id).all()
        assert len(db_comments_after) == 2

    finally:
        db.close()


# ==============================================================================
# 3. ANTI-BOT ERROR HANDLING & HEALTH UPDATE TESTS
# ==============================================================================

def test_collector_health_on_auth_and_checkpoint():
    db = SessionLocal()
    try:
        collector = GoofishCollector()

        # Simulate AUTH_REQUIRED exception
        def mock_fetch_auth(*args, **kwargs):
            raise RuntimeError("AUTH_REQUIRED: Redirected to login.taobao.com")

        collector.fetch = mock_fetch_auth
        res = collector.run(db, query="test")
        assert res["status"] == "AUTH_REQUIRED"

        health = db.query(CollectorHealth).filter(CollectorHealth.source_code == "GOOFISH").first()
        assert health.status == "AUTH_REQUIRED"
        assert health.auth_status == "LOGIN_REQUIRED"
        assert "login.taobao.com" in health.last_error

        # Simulate CHECKPOINT exception
        def mock_fetch_checkpoint(*args, **kwargs):
            raise RuntimeError("CHECKPOINT: Slide CAPTCHA challenge")

        collector.fetch = mock_fetch_checkpoint
        res2 = collector.run(db, query="test")
        assert res2["status"] == "BLOCKED"

        db.refresh(health)
        assert health.status == "BLOCKED"
        assert health.auth_status == "CHECKPOINT"

    finally:
        db.close()


# ==============================================================================
# 4. API ENDPOINT TESTS
# ==============================================================================

def test_api_collectors_status():
    resp = client.get("/collectors/status")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    sources = [s["source"] for s in data]
    assert "GOOFISH" in sources
    assert "CHOTOT" in sources
    assert "FACEBOOK_MARKETPLACE" in sources
    assert "FACEBOOK_GROUPS" in sources


def test_api_collectors_listings():
    resp = client.get("/collectors/listings?limit=10")
    assert resp.status_code == 200
    listings = resp.json()
    assert isinstance(listings, list)
    if listings:
        l = listings[0]
        assert "id" in l
        assert "raw_title" in l
        assert "raw_price_text" in l
        assert "snapshots_count" in l
