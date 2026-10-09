import os
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from playwright.sync_api import sync_playwright, BrowserContext
from app.taxonomy.models import DimSource
from app.collectors.models import (
    FactRawListing, FactListingPriceSnapshot, FactRawComment, CollectorHealth
)

logger = logging.getLogger(__name__)

class BaseCollector(ABC):
    source_code: str = "BASE"
    default_interval_minutes: int = 30
    default_currency: str = "VND"

    def __init__(self, headless: Optional[bool] = None):
        # Allow headed mode on local Windows via env BROWSER_HEADLESS=false
        env_headless = os.getenv("BROWSER_HEADLESS", "").lower()
        if headless is not None:
            self.headless = headless
        elif env_headless in ("false", "0", "no"):
            self.headless = False
        else:
            self.headless = True

        self.browser_profiles_base = os.getenv("BROWSER_PROFILES_DIR", "/app/browser_profiles")
        os.makedirs(self.browser_profile_path, exist_ok=True)

    @property
    def browser_profile_path(self) -> str:
        return os.path.join(self.browser_profiles_base, self.source_code.lower())

    def get_source_record(self, db: Session) -> DimSource:
        src = db.query(DimSource).filter(DimSource.code == self.source_code).first()
        if not src:
            raise ValueError(f"Source with code '{self.source_code}' not found in dim_source")
        return src

    def update_health(
        self,
        db: Session,
        status: str,
        items_scanned: int = 0,
        items_new: int = 0,
        error: Optional[str] = None,
        auth_status: str = "OK"
    ) -> CollectorHealth:
        health = db.query(CollectorHealth).filter(CollectorHealth.source_code == self.source_code).first()
        if not health:
            health = CollectorHealth(source_code=self.source_code)
            db.add(health)
            db.flush()

        health.status = status
        health.auth_status = auth_status
        health.updated_at = datetime.utcnow()

        if status == "RUNNING":
            health.last_start = datetime.utcnow()
        elif status == "SUCCESS":
            health.last_success = datetime.utcnow()
            health.last_error = None
            health.items_scanned = items_scanned
            health.items_new = items_new
        elif status in ("ERROR", "AUTH_REQUIRED", "BLOCKED"):
            health.last_error = error

        db.commit()
        db.refresh(health)
        return health

    def launch_browser_context(self, playwright_instance) -> BrowserContext:
        """
        Creates persistent context to preserve cookies and session state.
        Uses realistic desktop viewport and headers.
        """
        logger.info(f"[{self.source_code}] Launching browser (headless={self.headless}, profile={self.browser_profile_path})")
        context = playwright_instance.chromium.launch_persistent_context(
            user_data_dir=self.browser_profile_path,
            headless=self.headless,
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="vi-VN" if self.default_currency == "VND" else "zh-CN",
            timezone_id="Asia/Ho_Chi_Minh" if self.default_currency == "VND" else "Asia/Shanghai"
        )

        # Tự động nạp cookies.json nếu người dùng xuất từ extension Cookie-Editor
        cookie_file = os.path.join(self.browser_profile_path, "cookies.json")
        if not os.path.exists(cookie_file):
            cookie_file = os.path.join(self.browser_profiles_base, f"cookies_{self.source_code.lower()}.json")
        if not os.path.exists(cookie_file):
            cookie_file = os.path.join(self.browser_profiles_base, "facebook_cookies.json")

        if os.path.exists(cookie_file):
            try:
                import json
                with open(cookie_file, "r", encoding="utf-8") as f:
                    cookies_data = json.load(f)
                    # Chuẩn hóa format cookies cho Playwright
                    formatted_cookies = []
                    for c in cookies_data:
                        cookie_entry = {
                            "name": c.get("name"),
                            "value": c.get("value"),
                            "domain": c.get("domain", ".facebook.com"),
                            "path": c.get("path", "/"),
                        }
                        if c.get("sameSite") and c.get("sameSite").capitalize() in ("Strict", "Lax", "None"):
                            cookie_entry["sameSite"] = c.get("sameSite").capitalize()
                        if c.get("secure") is not None:
                            cookie_entry["secure"] = bool(c.get("secure"))
                        formatted_cookies.append(cookie_entry)
                    context.add_cookies(formatted_cookies)
                    logger.info(f"[{self.source_code}] Đã nạp thành công {len(formatted_cookies)} cookies từ {cookie_file}")
            except Exception as e:
                logger.warning(f"[{self.source_code}] Không thể nạp cookies từ file {cookie_file}: {e}")

        return context

    @abstractmethod
    def fetch(self, query: str = "") -> List[Dict[str, Any]]:
        """Fetch raw listings or items from the source."""
        pass

    @abstractmethod
    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Parse raw payloads into structured listing dictionaries."""
        pass

    def persist(self, parsed_items: List[Dict[str, Any]], db: Session) -> Dict[str, int]:
        """
        Persists raw listings with:
        - Deduplication (unique by source_id + source_listing_id)
        - Update last_seen_at for existing items
        - Price snapshot recording if price changes or item is new
        - Preservation of raw content without AI modification
        - Comment persistence
        """
        source = self.get_source_record(db)
        items_scanned = len(parsed_items)
        items_new = 0
        items_updated = 0
        comments_saved = 0

        for item in parsed_items:
            source_listing_id = str(item["source_listing_id"]).strip()
            existing = (
                db.query(FactRawListing)
                .filter(
                    FactRawListing.source_id == source.id,
                    FactRawListing.source_listing_id == source_listing_id
                )
                .first()
            )

            raw_price = item.get("raw_price_text")
            currency = item.get("raw_currency", self.default_currency)

            if existing:
                existing.last_seen_at = datetime.utcnow()
                existing.url = item.get("url", existing.url)

                # Check if price changed
                if raw_price and raw_price != existing.raw_price_text:
                    snapshot = FactListingPriceSnapshot(
                        listing_id=existing.id,
                        price_raw=raw_price,
                        currency=currency
                    )
                    db.add(snapshot)
                    existing.raw_price_text = raw_price

                # Check if description or metadata updated
                if item.get("raw_description"):
                    existing.raw_description = item["raw_description"]
                if item.get("raw_metadata"):
                    existing.raw_metadata = {**existing.raw_metadata, **item["raw_metadata"]}

                target_listing_id = existing.id
                items_updated += 1
            else:
                new_listing = FactRawListing(
                    source_id=source.id,
                    source_listing_id=source_listing_id,
                    url=item.get("url", ""),
                    raw_title=item.get("raw_title", ""),
                    raw_description=item.get("raw_description", ""),
                    raw_price_text=raw_price,
                    raw_currency=currency,
                    seller_name_raw=item.get("seller_name_raw"),
                    seller_id_raw=item.get("seller_id_raw"),
                    location_raw=item.get("location_raw"),
                    published_at=item.get("published_at"),
                    raw_metadata=item.get("raw_metadata", {}),
                    crawl_status="RAW_CAPTURED"
                )
                db.add(new_listing)
                db.flush()

                # Add initial price snapshot
                if raw_price:
                    snapshot = FactListingPriceSnapshot(
                        listing_id=new_listing.id,
                        price_raw=raw_price,
                        currency=currency
                    )
                    db.add(snapshot)

                target_listing_id = new_listing.id
                items_new += 1

                # Tự động gửi thông báo đến Bot RAM Telegram nếu là bài đăng bán RAM từ Group FB hoặc Marketplace
                if source.code in ("FACEBOOK_GROUPS", "FACEBOOK_MARKETPLACE"):
                    try:
                        from app.deal_hunter.ram_bot import notify_if_ram_post
                        grp_name = (new_listing.raw_metadata or {}).get("group_name", "")
                        if not grp_name and source.code == "FACEBOOK_MARKETPLACE":
                            grp_name = "Facebook Marketplace"
                        notify_if_ram_post(new_listing, group_name=grp_name)
                    except Exception as ex:
                        logger.debug(f"Lỗi gửi thông báo RAM bot: {ex}")

            # Persist comments if present
            comments = item.get("comments", [])
            for c in comments:
                cid = str(c.get("source_comment_id", "")).strip()
                if not cid:
                    continue
                exists_comment = (
                    db.query(FactRawComment)
                    .filter(
                        FactRawComment.listing_id == target_listing_id,
                        FactRawComment.source_comment_id == cid
                    )
                    .first()
                )
                if not exists_comment:
                    new_comment = FactRawComment(
                        source_comment_id=cid,
                        listing_id=target_listing_id,
                        author=c.get("author"),
                        raw_text=c.get("raw_text", ""),
                        created_at_source=c.get("created_at_source")
                    )
                    db.add(new_comment)
                    comments_saved += 1

        db.commit()
        return {
            "scanned": items_scanned,
            "new": items_new,
            "updated": items_updated,
            "comments": comments_saved
        }

    def run(self, db: Session, query: str = "", **kwargs) -> Dict[str, Any]:
        """Lifecycle method: update health, fetch, parse, persist."""
        self.update_health(db, status="RUNNING")
        try:
            raw_data = self.fetch(query, **kwargs)
            parsed_items = self.parse(raw_data)
            stats = self.persist(parsed_items, db)
            self.update_health(
                db,
                status="SUCCESS",
                items_scanned=stats["scanned"],
                items_new=stats["new"],
                auth_status="OK"
            )
            return {"status": "SUCCESS", "stats": stats}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{self.source_code}] Collector failed: {error_msg}", exc_info=True)
            auth_status = "LOGIN_REQUIRED" if "AUTH_REQUIRED" in error_msg else (
                "CHECKPOINT" if "CHECKPOINT" in error_msg else "OK"
            )
            col_status = "AUTH_REQUIRED" if "AUTH_REQUIRED" in error_msg else (
                "BLOCKED" if "CHECKPOINT" in error_msg else "ERROR"
            )
            self.update_health(
                db,
                status=col_status,
                error=error_msg,
                auth_status=auth_status
            )
            return {"status": col_status, "error": error_msg}
