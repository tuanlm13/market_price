import os
import re
import time
import json
import logging
import threading
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, Tuple, Set

from app.normalization.rules.classification_rules import classify_listing_intent, is_junk_listing

logger = logging.getLogger(__name__)

# ============================================================================
# RAM POST DETECTION LOGIC (Bộ lọc nhận diện tin bán RAM)
# ============================================================================
BUY_WANTED_PATTERNS = [
    r"\b(cần mua|tìm mua|mua sll|mua lẻ|ai có|thu mua|mua lại|cần tìm|e tìm|mình tìm|bác nào có|cần cây|cần thanh|tìm thanh|mua ram)\b"
]

DEFECTIVE_RAM_TITLE_PATTERNS = [
    r"\b(ram xác|xác ram|bán xác|rã xác|hàng xác|xác sống|xác chết|thanh lý xác|xác lỗi|xác - lỗi)\b",
    r"(?:^|\W)xác(?:\W|$)",
    r"\b(ram lỗi|bị lỗi|lỗi k nhận|lỗi không nhận|chết ram|hỏng ram)\b",
]

RAM_KEYWORDS = [
    r"\b(ram|ddr5|ddr4|ddr3|pc5|pc4|pc3|pc3l|sodimm|dimm|ecc server)\b"
]

def clean_facebook_text(text: str) -> str:
    """Loại bỏ ký tự rác, zero-width, combining diacritics và các dòng rác từ Facebook."""
    if not text:
        return ""
    # Gỡ bỏ các ký tự ẩn và dấu ghép Unicode của Facebook
    cleaned = re.sub(r"[\u0300-\u036f\u200b-\u200f\ufeff]", "", text)
    lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
    meaningful = []
    for l in lines:
        # Bỏ dòng 1-2 ký tự (chữ cái rác bị ngắt dòng từ Facebook timestamp DOM)
        if len(l) <= 2:
            continue
        # Bỏ các nút bấm giao diện
        if re.match(r"^(thích|bình luận|chia sẻ|xem thêm|gửi tin nhắn|nhắn tin|facebook|quản trị viên|người kiểm duyệt)$", l.lower()):
            continue
        # Bỏ timestamp
        if re.match(r"^\d+\s*(?:giờ|phút|ngày|tháng|tuần)\b", l.lower()):
            continue
        meaningful.append(l)
    return "\n".join(meaningful)

def is_ram_post(title: str, description: str = "") -> Tuple[bool, str]:
    """
    Xác định bài đăng có phải là bài BÁN RAM hay không:
    - User là người mua -> Chỉ thu thập tin từ người BÁN (intent == SELL)
    - Loại bỏ tin cần mua / tìm mua
    - Loại bỏ tin bán ram xác / ram lỗi
    - Loại bỏ tin bán cả chiếc laptop/PC mà RAM chỉ là thông số
    - Loại bỏ tin rác / phụ kiện
    """
    title_lower = (title or "").lower().strip()
    desc_lower = (description or "").lower().strip()
    full_text = f"{title_lower} {desc_lower}".strip()

    # 1. Chặn tin RAM xác, RAM lỗi, rã xác hỏng
    for pat in DEFECTIVE_RAM_TITLE_PATTERNS:
        if re.search(pat, title_lower):
            return False, "DEFECTIVE_OR_PARTS_RAM"

    # 2. Chặn tin rác / phụ kiện khác
    if is_junk_listing(title_lower):
        return False, "JUNK_LISTING"

    # 3. Chặn tin người mua (BUY / WANTED)
    for pat in BUY_WANTED_PATTERNS:
        if re.search(pat, title_lower) or re.search(pat, desc_lower[:120]):
            return False, "BUY_WANTED_POST"

    intent, _ = classify_listing_intent(title, description)
    if intent in ("BUY", "WANTED", "SERVICE", "SPAM", "ACCESSORY"):
        return False, f"INTENT_{intent}"

    # 3. Phải có từ khóa liên quan đến RAM
    has_ram_kw = any(re.search(pat, full_text) for pat in RAM_KEYWORDS)
    if not has_ram_kw:
        return False, "NO_RAM_KEYWORD"

    # 4. Loại trừ trường hợp bán nguyên chiếc laptop / thùng PC
    if re.search(r"\b(laptop|macbook|thinkpad|máy bàn|thùng máy|dàn máy|case máy)\b", title_lower):
        if not re.search(r"\b(ram|thanh ram|kit ram|bán ram|xả ram|pass ram)\b", title_lower[:25]):
            if re.search(r"\b(i3|i5|i7|i9|ryzen|r5|r7|gtx|rtx|fhd|oled|ips|inch)\b", title_lower):
                return False, "WHOLE_LAPTOP_OR_PC"

    # 5. Tiêu đề hoặc mở đầu mô tả phải tập trung vào RAM
    is_ram_focused_title = bool(
        re.search(r"\b(ram|ddr3|ddr4|ddr5|pc3|pc4|pc5|sodimm)\b", title_lower)
        or re.search(r"\b\d+gb\s+(ddr\d|bus\b)", title_lower)
        or re.search(r"\b(kit|thanh)\s+ram\b", title_lower)
    )

    if not is_ram_focused_title:
        if not re.search(r"\b(bán|pass|thanh lý|xả)\s+(?:thanh\s+)?ram\b", desc_lower[:80]):
            return False, "NOT_RAM_FOCUSED"

    return True, "VALID_RAM_SELL"


# ============================================================================
# RAM TELEGRAM NOTIFIER (Gửi thông báo tin bán RAM về Telegram)
# ============================================================================
class RamTelegramNotifier:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        default_chat_id: Optional[str] = None,
        mock_mode: Optional[bool] = None
    ):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN_RAM", "")
        self.default_chat_id = (
            default_chat_id
            or os.environ.get("TELEGRAM_CHAT_ID_RAM")
            or os.environ.get("TELEGRAM_CHAT_ID", "")
        )
        env_mock = os.environ.get("MOCK_TELEGRAM", "false").lower() in ("true", "1", "yes")
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = env_mock or not bool(self.bot_token)

        self.sent_alerts = []
        self._notified_urls: Set[str] = set()

    def format_ram_message(self, item: Dict[str, Any]) -> str:
        title = item.get("title", "Tin bán RAM")
        price = item.get("price_text") or (f"{item['price']:,.0f} đ" if item.get("price") else "Thương lượng")
        group_name = item.get("group_name", "Hội nhóm Facebook")
        
        # Làm sạch nội dung mô tả khỏi các dòng rác Facebook
        raw_desc = item.get("description") or ""
        cleaned_desc = clean_facebook_text(raw_desc)
        lines = [l.strip() for l in cleaned_desc.split("\n") if l.strip()]

        seller_name = item.get("seller_name", "Người bán")
        # Nếu seller_name chung chung mà dòng đầu là tên người (2-4 từ), dùng làm tên người bán
        if seller_name in ("Người bán", "Người bán trên nhóm", "Thành viên nhóm") and lines:
            first_line = lines[0]
            words = first_line.split()
            if 2 <= len(words) <= 4 and not re.search(r"\b(ram|ddr|gb|pc|ssd|hdd|bán|pass|giá|\d)\b", first_line.lower()):
                seller_name = first_line
                cleaned_desc = "\n".join(lines[1:])

        desc_snippet = cleaned_desc[:280] + ("..." if len(cleaned_desc) > 280 else "") if cleaned_desc else "Không có mô tả chi tiết."
        cmt_count = item.get("comment_count", 0)
        url = item.get("url", "#")

        msg = (
            "⚡ <b>PHÁT HIỆN BÀI ĐĂNG BÁN RAM MỚI</b> ⚡\n\n"
            f"📦 <b>Sản phẩm:</b> {title}\n"
            f"🏷️ <b>Giá rao:</b> <code>{price}</code>\n"
            f"👥 <b>Hội nhóm:</b> <b>{group_name}</b>\n"
            f"👤 <b>Người bán:</b> {seller_name}\n"
            f"💬 <b>Bình luận:</b> {cmt_count}\n\n"
            f"📝 <b>Nội dung trích đoạn:</b>\n"
            f"<i>{desc_snippet}</i>\n\n"
            f"🔗 <a href=\"{url}\">👉 BẤM VÀO ĐÂY ĐỂ MỞ BÀI ĐĂNG FACEBOOK</a>"
        )
        return msg

    def send_ram_sale_alert(self, item: Dict[str, Any], chat_id: Optional[str] = None) -> bool:
        target_chat = chat_id or self.default_chat_id
        if not target_chat:
            logger.warning("[RAM Bot] Không có chat_id để gửi alert RAM.")
            return False

        url = item.get("url", "")
        if url and url in self._notified_urls:
            logger.info(f"[RAM Bot] Bài đăng đã được alert trước đó: {url}")
            return False

        message_text = self.format_ram_message(item)

        if self.mock_mode:
            logger.info(f"[MOCK RAM BOT] Gửi alert RAM tới chat_id={target_chat}:\n{message_text}")
            self.sent_alerts.append({"chat_id": target_chat, "text": message_text, "item": item})
            if url:
                self._notified_urls.add(url)
            return True

        success = self._send_telegram_text(message_text, target_chat, item_url=url)
        if success and url:
            self._notified_urls.add(url)
        return success

    def _send_telegram_text(self, text: str, chat_id: str, item_url: str = "") -> bool:
        if not self.bot_token or not chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True  # Tắt preview link để tránh card Facebook lặp lại
        }
        if item_url and str(item_url).startswith("http"):
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": "👉 MỞ BÀI ĐĂNG TRÊN FACEBOOK 📱", "url": item_url}]
                ]
            }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return bool(result.get("ok"))
        except Exception as e:
            logger.error(f"[RAM Bot] Lỗi gửi tin nhắn Telegram: {e}")
            return False


ram_notifier = RamTelegramNotifier()


def notify_if_ram_post(raw_listing: Any, group_name: str = "") -> bool:
    """
    Hook gọi sau khi thu thập một bài đăng từ Facebook Group.
    Tự động kiểm tra và báo về Telegram Bot RAM nếu thỏa mãn.
    """
    title = getattr(raw_listing, "raw_title", "") or ""
    desc = getattr(raw_listing, "raw_description", "") or ""

    is_valid_ram, reason = is_ram_post(title, desc)
    if not is_valid_ram:
        return False

    meta = getattr(raw_listing, "raw_metadata", {}) or {}
    grp = group_name or meta.get("group_name", "Hội nhóm Facebook")
    seller = getattr(raw_listing, "seller_name_raw", None) or "Người bán trên nhóm"
    price_text = getattr(raw_listing, "raw_price_text", None)
    url = getattr(raw_listing, "url", "#")
    comments = getattr(raw_listing, "comments", []) or []

    item_data = {
        "title": title,
        "description": desc,
        "price_text": price_text,
        "group_name": grp,
        "seller_name": seller,
        "comment_count": len(comments),
        "url": url
    }

    return ram_notifier.send_ram_sale_alert(item_data)


# ============================================================================
# RAM TELEGRAM BOT LISTENER (Bot chat 2 chiều chuyên biệt cho RAM)
# ============================================================================
class RamTelegramBotListener:
    """
    Background worker lắng nghe tương tác 2 chiều từ người dùng CHUYÊN VỀ RAM.
    Hỗ trợ tìm kiếm RAM tức thì trên Facebook Groups, Marketplace & Chợ Tốt.
    """
    def __init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN_RAM", "")
        self.authorized_chat_id = os.environ.get("TELEGRAM_CHAT_ID_RAM", os.environ.get("TELEGRAM_CHAT_ID", ""))
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_update_id = 0

    def start(self):
        if not self.bot_token:
            logger.info("RamTelegramBotListener: Không có TELEGRAM_BOT_TOKEN_RAM, bỏ qua worker RAM.")
            return

        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True, name="RamTelegramBotListener")
        self.thread.start()
        logger.info("🤖 RamTelegramBotListener: Đã khởi động bot Telegram chuyên săn RAM!")

    def stop(self):
        self.running = False

    def _poll_loop(self):
        while self.running:
            try:
                updates = self._get_updates()
                for upd in updates:
                    self._handle_update(upd)
            except Exception as e:
                logger.error(f"Lỗi trong RAM Telegram poll loop: {e}")
                time.sleep(5)
            time.sleep(1)

    def _get_updates(self):
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RamPriceBot/1.0"})
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
            "disable_web_page_preview": True
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
            logger.error(f"[RAM Bot] Không thể gửi tin nhắn Telegram: {e}")
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

        # Menu trợ giúp
        if text_lower in ("/start", "/help", "help", "menu"):
            welcome = (
                "👋 <b>Xin chào! Tôi là Trợ Lý Săn RAM (RAM Intelligence Bot).</b>\n\n"
                "Tôi là bot chuyên dụng <b>CHỈ DÀNH RIÊNG CHO RAM</b> (DDR3, DDR4, DDR5, ECC...).\n\n"
                "💡 <b>Tính năng nổi bật:</b>\n"
                "• Tự động thông báo ngay khi có bài đăng <b>BÁN RAM</b> mới trên các Hội Nhóm Facebook.\n"
                "• Lọc sạch 100% tin cần mua, tin rác, chỉ giữ lại người BÁN.\n"
                "• Tìm kiếm giá RAM thị trường tức thì.\n\n"
                "🔍 <b>Cách tra cứu tin bán RAM:</b>\n"
                "• Nhắn: <code>ram ddr5</code> (hoặc chỉ gõ <i>ddr5</i>)\n"
                "• Nhắn: <code>ram ddr4 16gb</code> (hoặc <i>ddr4 3200</i>)\n"
                "• Nhắn: <code>ram laptop 8gb</code>\n"
                "• Lệnh tắt: <code>/find [loại ram]</code>\n\n"
                "⚡ Tôi sẽ tự động quét các <b>Hội nhóm Facebook</b>, <b>Marketplace</b> & <b>Chợ Tốt</b> để tìm người bán ngay cho bạn!"
            )
            self._send_message(chat_id, welcome)
            return

        # Trích xuất keyword tìm kiếm
        keyword = ""
        prefixes = ["tìm giá ram", "tìm ram", "tim ram", "giá ram", "gia ram", "/find", "/tim", "/ram"]
        for p in prefixes:
            if text_lower.startswith(p):
                keyword = text[len(p):].strip(" :;=-")
                break

        if not keyword:
            keyword = text.strip()

        # Đảm bảo ngữ cảnh luôn là RAM
        if keyword:
            self._execute_ram_search_and_reply(chat_id, keyword)

    def _execute_ram_search_and_reply(self, chat_id: str, keyword: str):
        search_query = keyword if "ram" in keyword.lower() else f"ram {keyword}"
        self._send_message(
            chat_id,
            f"🔍 <b>Đang quét các tin BÁN RAM cho:</b> <code>{search_query}</code>\n"
            f"⏳ Đang tìm kiếm trên <b>Hội Nhóm Facebook</b>, <b>Marketplace</b> & <b>Chợ Tốt</b>, vui lòng đợi giây lát..."
        )

        try:
            from app.collectors.service import run_collector_job
            from app.normalization.service import process_batch_listings
            from database import SessionLocal
            from app.collectors.models import FactRawListing
            from app.normalization.models import FactNormalizedListing
            from sqlalchemy import desc

            # Cào dữ liệu theo ngữ cảnh RAM
            run_collector_job(source_code="FACEBOOK_GROUPS", query=search_query)
            run_collector_job(source_code="FACEBOOK_MARKETPLACE", query=search_query)
            run_collector_job(source_code="CHOTOT", query=search_query)

            db = SessionLocal()
            try:
                process_batch_listings(db, limit=40)

                # Tìm các tin thoả mãn is_ram_post
                all_recent = (
                    db.query(FactRawListing)
                    .order_by(desc(FactRawListing.first_seen_at))
                    .limit(100)
                    .all()
                )

                matched_items = []
                seen_urls = set()
                kw_parts = [p.strip().lower() for p in keyword.lower().split() if p.strip()]

                for raw in all_recent:
                    title = raw.raw_title or ""
                    desc_text = raw.raw_description or ""

                    # BẮT BUỘC: Phải là bài đăng BÁN RAM
                    ok, _ = is_ram_post(title, desc_text)
                    if not ok:
                        continue

                    # Khớp từ khóa tìm kiếm
                    title_lower = title.lower()
                    if not any(part in title_lower for part in kw_parts if len(part) >= 3):
                        continue

                    if raw.url in seen_urls:
                        continue
                    seen_urls.add(raw.url)

                    # Phân tích giá
                    from app.deal_hunter.comment_appraiser import parse_vietnamese_price
                    price_num = parse_vietnamese_price(raw.raw_price_text or "") or 0.0

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

                if not matched_items:
                    self._send_message(
                        chat_id,
                        f"⚠️ Hiện tại chưa tìm thấy tin <b>BÁN RAM</b> nào mới khớp với <code>{keyword}</code> trên các nhóm và sàn.\n"
                        f"💡 Tôi sẽ tiếp tục theo dõi các Hội nhóm Facebook và báo ngay cho bạn khi có người đăng bán!"
                    )
                    return

                # Soạn tin nhắn báo cáo danh sách
                top_items_text = ""
                for idx, it in enumerate(matched_items[:5], 1):
                    cmt_badge = f" | 💬 {it['comment_count']} cmt" if it['comment_count'] > 0 else ""
                    price_disp = f"{it['price']:,.0f} đ" if it['price'] > 0 else (it['price_text'] or "Thương lượng")
                    top_items_text += (
                        f"<b>{idx}. {it['title'][:55]}</b>\n"
                        f"   🏷️ Giá: <code>{price_disp}</code> | 📍 {it['source']}{cmt_badge}\n"
                        f"   🔗 <a href=\"{it['url']}\">Bấm vào đây để mở bài đăng gốc</a>\n\n"
                    )

                reply_msg = (
                    f"🎯 <b>TÌM THẤY {len(matched_items)} TIN BÁN RAM CHO:</b> <code>{keyword}</code>\n\n"
                    f"{top_items_text}"
                    f"<i>(Đã loại bỏ các tin cần mua, tin phụ kiện và tin rác)</i>"
                )
                self._send_message(chat_id, reply_msg)

            finally:
                db.close()

        except Exception as e:
            logger.error(f"[RAM Bot] Lỗi quét dữ liệu: {e}", exc_info=True)
            self._send_message(chat_id, f"❌ Có lỗi xảy ra trong quá trình quét dữ liệu RAM: {e}")


ram_bot_listener = RamTelegramBotListener()
