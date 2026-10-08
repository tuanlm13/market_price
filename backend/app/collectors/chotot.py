import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

class ChoTotCollector(BaseCollector):
    source_code = "CHOTOT"
    default_interval_minutes = 30
    default_currency = "VND"

    def fetch(self, query: str = "iphone 16") -> List[Dict[str, Any]]:
        """
        Fetches listings from Chợ Tốt gateway API or fallback browser.
        Supports query parameter and limits to 30 newest items.
        """
        api_url = f"https://gateway.chotot.com/v1/public/ad-listing?q={query}&limit=30&st=s,k"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Origin": "https://www.chotot.com",
            "Referer": f"https://www.chotot.com/mua-ban?q={query}"
        }

        try:
            resp = requests.get(api_url, headers=headers, timeout=15)
            if resp.status_code == 403:
                raise RuntimeError("CHECKPOINT: ChoTot returned 403 Cloudflare challenge")
            if resp.status_code == 401:
                raise RuntimeError("AUTH_REQUIRED: ChoTot requires authenticated session")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("ads", [])
        except Exception as e:
            if "CHECKPOINT" in str(e) or "AUTH_REQUIRED" in str(e):
                raise
            logger.warning(f"[{self.source_code}] Direct HTTP request failed: {e}. Trying Playwright browser...")

        # Fallback to Playwright browser context
        items = []
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                context = self.launch_browser_context(p)
                page = context.new_page()
                page.goto(f"https://www.chotot.com/mua-ban?q={query}", timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Check checkpoint
                if "challenge" in page.url or "captcha" in page.content().lower():
                    context.close()
                    raise RuntimeError("CHECKPOINT: ChoTot Cloudflare / CAPTCHA challenge detected")

                ad_elements = page.query_selector_all("a[href*='/mua-ban-']")
                for idx, el in enumerate(ad_elements[:30]):
                    href = el.get_attribute("href") or ""
                    title = el.inner_text().strip()
                    if href and title:
                        list_id = href.split("/")[-1].replace(".htm", "")
                        items.append({
                            "list_id": list_id,
                            "subject": title.split("\n")[0],
                            "price_string": title.split("\n")[1] if "\n" in title else "",
                            "url": f"https://www.chotot.com{href}" if href.startswith("/") else href
                        })
                context.close()
        except Exception as e:
            if "CHECKPOINT" in str(e) or "AUTH_REQUIRED" in str(e):
                raise
            logger.error(f"[{self.source_code}] Browser fetch error: {e}")
            raise

        return items

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        Parses raw ads into standardized listing format.
        Preserves raw price, raw title and raw location text.
        """
        parsed: List[Dict[str, Any]] = []
        if isinstance(raw_data, list):
            for ad in raw_data:
                list_id = str(ad.get("list_id") or ad.get("id") or "")
                if not list_id:
                    continue

                price = ad.get("price_string")
                if not price and ad.get("price") is not None:
                    price = f"{ad['price']} đ"

                pub_time = None
                if ad.get("date"):
                    try:
                        pub_time = datetime.fromtimestamp(ad["date"] / 1000.0) if ad["date"] > 10000000000 else datetime.fromtimestamp(ad["date"])
                    except Exception:
                        pass

                parsed.append({
                    "source_listing_id": list_id,
                    "url": ad.get("url") or f"https://www.chotot.com/{list_id}.htm",
                    "raw_title": ad.get("subject", ad.get("title", "")),
                    "raw_description": ad.get("body", ad.get("description", "")),
                    "raw_price_text": price or "Thương lượng",
                    "raw_currency": "VND",
                    "seller_name_raw": ad.get("account_name") or ad.get("seller", "Người bán Chợ Tốt"),
                    "seller_id_raw": str(ad.get("account_id", "")),
                    "location_raw": ad.get("area_name") or ad.get("region_name") or ad.get("location", "Toàn quốc"),
                    "published_at": pub_time or datetime.utcnow(),
                    "raw_metadata": {
                        "category_id": ad.get("category"),
                        "images": ad.get("images", []),
                        "image_url": ad.get("image") or (ad.get("images", [None])[0] if isinstance(ad.get("images"), list) and ad.get("images") else ""),
                        "phone": ad.get("phone_hidden", False),
                        "source_platform": "chotot"
                    },
                    "comments": []
                })
        return parsed
