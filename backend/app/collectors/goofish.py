import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

class GoofishCollector(BaseCollector):
    source_code = "GOOFISH"
    default_interval_minutes = 10
    default_currency = "CNY"

    def fetch(self, query: str = "iPhone 16") -> List[Dict[str, Any]]:
        """
        Fetches search results from Goofish (闲鱼).
        Checks for security verification or login redirect.
        """
        items: List[Dict[str, Any]] = []
        target_url = f"https://www.goofish.com/search?q={query}"

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                context = self.launch_browser_context(p)
                page = context.new_page()

                logger.info(f"[{self.source_code}] Navigating to {target_url}")
                page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Anti-bot detection
                content = page.content()
                if "punish" in page.url or "sec.taobao.com" in page.url or "login.taobao.com" in page.url:
                    context.close()
                    raise RuntimeError("AUTH_REQUIRED: Goofish redirect to login / verification page")

                if "nocaptcha" in content or "滑块验证" in content:
                    context.close()
                    raise RuntimeError("CHECKPOINT: Alibaba slide CAPTCHA detected")

                # Extract items
                elements = page.query_selector_all(".feeds-item--card, [class*='feeds-item'], [class*='item-card']")
                for idx, el in enumerate(elements[:25]):
                    title_el = el.query_selector("[class*='title'], h4, p")
                    price_el = el.query_selector("[class*='price'], [class*='amount']")
                    link_el = el.query_selector("a")

                    title = title_el.inner_text().strip() if title_el else ""
                    price = price_el.inner_text().strip() if price_el else ""
                    href = link_el.get_attribute("href") if link_el else ""

                    if title:
                        items.append({
                            "id": f"gf_{idx}_{hash(title) % 10000000}",
                            "title": title,
                            "price": price,
                            "url": f"https://www.goofish.com{href}" if href.startswith("/") else (href or target_url),
                            "seller": "Goofish User",
                            "location": "China"
                        })
                context.close()
        except Exception as e:
            if "AUTH_REQUIRED" in str(e) or "CHECKPOINT" in str(e):
                raise
            logger.warning(f"[{self.source_code}] Live fetch encountered issue: {e}")
            raise

        return items

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        Parses raw Goofish payloads or list of dicts.
        Preserves raw price and content without AI normalization.
        """
        parsed: List[Dict[str, Any]] = []
        if isinstance(raw_data, list):
            for entry in raw_data:
                listing_id = str(entry.get("id") or entry.get("itemId") or "")
                if not listing_id:
                    continue

                parsed.append({
                    "source_listing_id": listing_id,
                    "url": entry.get("url") or f"https://www.goofish.com/item?id={listing_id}",
                    "raw_title": entry.get("title", ""),
                    "raw_description": entry.get("description", entry.get("title", "")),
                    "raw_price_text": entry.get("price"),
                    "raw_currency": "CNY",
                    "seller_name_raw": entry.get("seller") or entry.get("sellerName"),
                    "seller_id_raw": str(entry.get("sellerId", "")),
                    "location_raw": entry.get("location") or entry.get("city", "China"),
                    "published_at": entry.get("published_at") or datetime.utcnow(),
                    "raw_metadata": {
                        "tags": entry.get("tags", []),
                        "source_platform": "goofish",
                        "raw_entry": {k: v for k, v in entry.items() if k not in ("description",)}
                    },
                    "comments": entry.get("comments", [])
                })
        return parsed
