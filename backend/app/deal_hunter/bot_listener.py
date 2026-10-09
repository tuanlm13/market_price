import os
import re
import time
import logging
import threading
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TelegramBotListener:
    """
    Background worker lắng nghe tương tác 2 chiều từ người dùng qua Telegram.
    Hỗ trợ lệnh tìm giá tức thì (vd: 'tìm giá iphone 16 plus', '/find iphone 13').
    """

    def __init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        raw_auth = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.authorized_chat_ids = [c.strip() for c in re.split(r"[,;\s]+", str(raw_auth)) if c.strip()]
        self.authorized_chat_id = self.authorized_chat_ids[0] if self.authorized_chat_ids else ""
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_update_id = 0

    def start(self):
        if not self.bot_token:
            logger.info("TelegramBotListener: Không có TELEGRAM_BOT_TOKEN, bỏ qua worker tương tác.")
            return

        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True, name="TelegramBotListener")
        self.thread.start()
        logger.info("🤖 TelegramBotListener: Đã khởi động background worker tương tác 2 chiều!")

    def stop(self):
        self.running = False

    def _poll_loop(self):
        while self.running:
            try:
                updates = self._get_updates()
                for upd in updates:
                    self._handle_update(upd)
            except Exception as e:
                logger.error(f"Lỗi trong Telegram poll loop: {e}")
                time.sleep(5)
            time.sleep(1)

    def _get_updates(self):
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MarketPriceBot/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    results = data.get("result", [])
                    if results:
                        self.last_update_id = max(r.get("update_id", 0) for r in results)
                    return results
        except Exception:
            pass
        return []

    def _send_message(self, chat_id: str, text: str, reply_markup: Optional[Dict] = None) -> bool:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return True
        except Exception as e:
            logger.error(f"Không thể gửi tin nhắn Telegram: {e}")
            return False

    def _handle_update(self, upd: Dict[str, Any]):
        msg = upd.get("message")
        if not msg:
            return

        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = str(msg.get("text", "")).strip()
        if not text:
            return

        text_lower = text.lower()

        # Kiểm tra lệnh trợ giúp
        if text_lower in ("/start", "/help", "help", "menu"):
            welcome = (
                "👋 <b>Xin chào bạn! Tôi là Market Price Intelligence Bot.</b>\n\n"
                "Tôi có thể quét các sàn và phân tích giá thị trường theo yêu cầu của bạn.\n\n"
                "💡 <b>Cách sử dụng:</b>\n"
                "• Nhắn: <code>tìm giá [tên máy]</code> (VD: <i>tìm giá iphone 16 plus</i>)\n"
                "• Nhắn: <code>giá [tên máy]</code> (VD: <i>giá rtx 4060</i>)\n"
                "• Lệnh tắt: <code>/find [tên máy]</code>\n\n"
                "⚡ Tôi sẽ tự động cào tin từ <b>Facebook Marketplace</b> & <b>Chợ Tốt</b> và gửi bảng phân tích giá ngay cho bạn!"
            )
            self._send_message(chat_id, welcome)
            return

        # Nhận diện nếu người dùng dán kèm link nhóm Facebook cụ thể
        target_group_url = ""
        group_match = re.search(r"https?://(?:www\.)?facebook\.com/groups/[^/\s]+/?", text)
        if group_match:
            target_group_url = group_match.group(0)
            text = text.replace(target_group_url, "").strip(" :;=-")
            text_lower = text.lower()

        # Nhận diện lệnh tìm giá
        keyword = ""
        prefixes = ["tìm giá", "tim gia", "giá", "gia", "tìm", "tim", "/find", "/tim", "/gia"]
        for p in prefixes:
            if text_lower.startswith(p):
                keyword = text[len(p):].strip(" :;=-")
                break

        if not keyword and not text.startswith("/"):
            keyword = text.strip()

        if keyword:
            self._execute_search_and_reply(chat_id, keyword, target_group_url=target_group_url)

    def _execute_search_and_reply(self, chat_id: str, keyword: str, target_group_url: str = ""):
        # 1. Thông báo ngay cho user
        grp_note = f"\n🎯 <i>Đang ưu tiên quét trực tiếp nhóm:</i> <code>{target_group_url}</code>" if target_group_url else ""
        self._send_message(
            chat_id,
            f"🔍 <b>Đang quét thị trường cho:</b> <code>{keyword}</code>{grp_note}\n"
            f"⏳ Đang thu thập tin mới nhất từ <b>Facebook Marketplace</b>, <b>Hội Nhóm Facebook</b> & <b>Chợ Tốt</b>, vui lòng đợi giây lát..."
        )

        try:
            from app.collectors.service import run_collector_job
            from app.normalization.service import process_batch_listings
            from app.normalization.rules.classification_rules import is_relevant_to_keyword
            from database import SessionLocal
            from app.collectors.models import FactRawListing
            from app.normalization.models import FactNormalizedListing
            from sqlalchemy import desc

            # 2. Cào dữ liệu từ cả 3 nguồn (truyền target_group_url nếu có)
            logger.info(f"BotListener: Bắt đầu cào cho từ khóa '{keyword}' trên Marketplace, Groups & Chợ Tốt (group: {target_group_url})")
            run_collector_job("FACEBOOK_MARKETPLACE", query=keyword)
            run_collector_job("FACEBOOK_GROUPS", query=keyword, target_group_url=target_group_url)
            run_collector_job("CHOTOT", query=keyword)

            # 3. Chuẩn hóa dữ liệu
            db = SessionLocal()
            try:
                process_batch_listings(db, limit=40)

                # 4. Ưu tiên lấy từ FactNormalizedListing (đã qua pipeline classification)
                normalized_recent = (
                    db.query(FactNormalizedListing)
                    .filter(
                        FactNormalizedListing.classification == "SELL",
                        FactNormalizedListing.price_valid == True,
                        FactNormalizedListing.normalized_price > 0
                    )
                    .order_by(desc(FactNormalizedListing.normalized_at))
                    .limit(80)
                    .all()
                )

                matched_items = []
                seen_urls = set()

                for norm in normalized_recent:
                    raw = norm.raw_listing
                    if not raw:
                        continue

                    title = raw.raw_title or ""
                    full_text = f"{title} {raw.raw_description or ''}"

                    # FILTER CHÍNH XÁC: Kiểm tra cả tiêu đề và đoạn đầu mô tả
                    if not is_relevant_to_keyword(title, keyword) and not is_relevant_to_keyword(full_text[:280], keyword):
                        continue

                    # Chống trùng URL
                    if raw.url in seen_urls:
                        continue
                    seen_urls.add(raw.url)

                    price_num = float(norm.normalized_price or 0)
                    if price_num < 100_000:
                        continue

                    grp_name = ""
                    if raw.raw_metadata and isinstance(raw.raw_metadata, dict):
                        grp_name = raw.raw_metadata.get("group_name", "")

                    source_str = raw.source.name if raw.source else "Marketplace"
                    if grp_name:
                        source_str = f"Hội nhóm: {grp_name[:35]}"

                    cmt_count = len(raw.comments) if raw.comments else 0
                    matched_items.append({
                        "title": title,
                        "price": price_num,
                        "price_text": raw.raw_price_text,
                        "url": raw.url,
                        "source": source_str,
                        "comment_count": cmt_count
                    })

                # 4b. Fallback: Nếu chưa có kết quả từ normalized, thử raw (nhưng vẫn dùng filter)
                if not matched_items:
                    all_recent = (
                        db.query(FactRawListing)
                        .order_by(desc(FactRawListing.first_seen_at))
                        .limit(60)
                        .all()
                    )
                    for item in all_recent:
                        title = item.raw_title or ""
                        full_item_text = f"{title} {item.raw_description or ''}"
                        if not is_relevant_to_keyword(title, keyword) and not is_relevant_to_keyword(full_item_text[:280], keyword):
                            continue

                        if item.url in seen_urls:
                            continue
                        seen_urls.add(item.url)

                        price_num = 0.0
                        if item.raw_price_text:
                            from app.deal_hunter.comment_appraiser import parse_vietnamese_price
                            price_num = parse_vietnamese_price(item.raw_price_text) or 0.0

                        if price_num < 100_000:
                            continue

                        grp_name = ""
                        if item.raw_metadata and isinstance(item.raw_metadata, dict):
                            grp_name = item.raw_metadata.get("group_name", "")

                        source_str = item.source.name if item.source else "Marketplace"
                        if grp_name:
                            source_str = f"Hội nhóm: {grp_name[:35]}"

                        cmt_count = len(item.comments) if item.comments else 0
                        matched_items.append({
                            "title": title,
                            "price": price_num,
                            "price_text": item.raw_price_text,
                            "url": item.url,
                            "source": source_str,
                            "comment_count": cmt_count
                        })

                if not matched_items:
                    self._send_message(
                        chat_id,
                        f"⚠️ Đã quét các sàn nhưng chưa tìm thấy tin đăng phù hợp cho <b>{keyword}</b>. Bạn vui lòng thử lại từ khóa khác!"
                    )
                    return

                # Sắp xếp theo giá tăng dần
                matched_items.sort(key=lambda x: x["price"])
                prices = [x["price"] for x in matched_items]

                import statistics
                min_price = min(prices)
                max_price = max(prices)
                median_price = statistics.median(prices)
                quick_sell = median_price * 0.92

                # 5. Soạn tin nhắn báo cáo
                top_items_text = ""
                for idx, it in enumerate(matched_items[:5], 1):
                    cmt_badge = f" | 💬 {it['comment_count']} bình luận" if it['comment_count'] > 0 else ""
                    top_items_text += (
                        f"<b>{idx}. {it['title'][:55]}</b>\n"
                        f"   🏷️ Giá: <code>{it['price']:,.0f} đ</code> | 📍 {it['source']}{cmt_badge}\n"
                        f"   🔗 <a href=\"{it['url']}\">Bấm vào đây để mở bài đăng gốc</a>\n\n"
                    )

                report_msg = (
                    f"📊 <b>KẾT QUẢ THỊ TRƯỜNG: {keyword.upper()}</b>\n\n"
                    f"📦 <b>Số bài đăng tìm thấy:</b> {len(matched_items)} bài đăng thực tế\n"
                    f"📉 <b>Giá rẻ nhất:</b> <code>{min_price:,.0f} đ</code>\n"
                    f"🎯 <b>Giá trung vị (Median):</b> <code>{median_price:,.0f} đ</code>\n"
                    f"⚡ <b>Giá thanh khoản nhanh (Quick Sell):</b> <code>{quick_sell:,.0f} đ</code>\n\n"
                    f"🏆 <b>TOP BÀI ĐĂNG TỐT NHẤT (KÈM BÌNH LUẬN):</b>\n\n"
                    f"{top_items_text}"
                    f"💡 <i>Gợi ý: Giá mua sang tay nên thấp hơn 8-10% so với giá shop bán lẻ (ClickBuy, Oneway, Di Động Việt).</i>"
                )

                inline_kb = None
                if matched_items:
                    inline_kb = {
                        "inline_keyboard": [
                            [{"text": "👉 Xem bài đăng rẻ nhất", "url": matched_items[0]["url"]}]
                        ]
                    }

                self._send_message(chat_id, report_msg, reply_markup=inline_kb)

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Lỗi khi xử lý tìm kiếm Telegram: {e}", exc_info=True)
            self._send_message(chat_id, f"❌ Có lỗi xảy ra trong quá trình quét dữ liệu: {e}")

bot_listener = TelegramBotListener()

