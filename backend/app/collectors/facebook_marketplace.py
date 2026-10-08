import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

class FacebookMarketplaceCollector(BaseCollector):
    source_code = "FACEBOOK_MARKETPLACE"
    default_interval_minutes = 60
    default_currency = "VND"

    def fetch(self, query: str = "rtx 4060") -> List[Dict[str, Any]]:
        """
        Fetches listings from Facebook Marketplace using persistent profile.
        Limits to 20-30 most recent items.
        Detects login wall or checkpoint and halts gracefully.
        """
        items: List[Dict[str, Any]] = []
        target_url = f"https://www.facebook.com/marketplace/search?query={query}"

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                context = self.launch_browser_context(p)
                page = context.new_page()

                logger.info(f"[{self.source_code}] Navigating to {target_url}")
                page.goto(target_url, timeout=35000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)

                # Check Auth / Checkpoint
                current_url = page.url.lower()
                if "login" in current_url:
                    context.close()
                    raise RuntimeError("AUTH_REQUIRED: Facebook Marketplace login required")
                if "checkpoint" in current_url:
                    context.close()
                    raise RuntimeError("CHECKPOINT: Facebook account checkpoint / verification triggered")

                # Parse listing cards (max 30 items)
                links = page.query_selector_all("a[href*='/marketplace/item/']")
                for idx, a in enumerate(links[:30]):
                    href = a.get_attribute("href") or ""
                    text_content = a.inner_text().strip()

                    if href and text_content:
                        lines = [l.strip() for l in text_content.split("\n") if l.strip()]
                        # Facebook card format usually has: price, title, location
                        price = lines[0] if len(lines) > 0 else ""
                        title = lines[1] if len(lines) > 1 else lines[0]
                        location = lines[2] if len(lines) > 2 else "Vietnam"

                        item_id = href.split("/item/")[1].split("/")[0].split("?")[0]
                        full_url = f"https://www.facebook.com/marketplace/item/{item_id}"

                        # Bóc tách ảnh thật từ bài đăng
                        img_el = a.query_selector("img")
                        img_url = img_el.get_attribute("src") if img_el else ""

                        items.append({
                            "item_id": item_id,
                            "title": title,
                            "price": price,
                            "location": location,
                            "url": full_url,
                            "image_url": img_url
                        })
                context.close()
        except Exception as e:
            if "AUTH_REQUIRED" in str(e) or "CHECKPOINT" in str(e):
                raise
            logger.warning(f"[{self.source_code}] Marketplace scrape encountered issue: {e}")
            raise

        return items

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        Standardizes raw marketplace listings.
        Preserves raw price text and location.
        """
        parsed: List[Dict[str, Any]] = []
        if isinstance(raw_data, list):
            for item in raw_data:
                item_id = str(item.get("item_id") or item.get("id") or "")
                if not item_id:
                    continue

                parsed.append({
                    "source_listing_id": item_id,
                    "url": item.get("url") or f"https://www.facebook.com/marketplace/item/{item_id}",
                    "raw_title": item.get("title", ""),
                    "raw_description": item.get("description", item.get("title", "")),
                    "raw_price_text": item.get("price"),
                    "raw_currency": "VND",
                    "seller_name_raw": item.get("seller", "Facebook User"),
                    "seller_id_raw": str(item.get("seller_id", "")),
                    "location_raw": item.get("location", "Vietnam"),
                    "published_at": item.get("published_at") or datetime.utcnow(),
                    "raw_metadata": {
                        "source_platform": "facebook_marketplace",
                        "image_url": item.get("image_url", ""),
                        "raw_item": item
                    },
                    "comments": []
                })
        return parsed
