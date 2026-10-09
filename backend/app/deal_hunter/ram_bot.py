import os
import re
import time
import json
import html
import logging
import threading
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, Tuple, Set, List
from datetime import datetime, timedelta

from app.normalization.rules.classification_rules import classify_listing_intent, is_junk_listing, extract_facebook_post_id

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


def format_time_ago(dt: Optional[datetime] = None, raw_time_str: str = "") -> str:
    """
    Tạo định dạng thời gian thân thiện cho bài đăng:
    - 08:35 09/10/2026 (cách đây 15 phút)
    - 15 phút trước (08:35 09/10/2026)
    - Vừa xong
    """
    now = datetime.utcnow()
    rel_part = raw_time_str.strip() if raw_time_str else ""

    if not isinstance(dt, datetime):
        dt = None

    if not rel_part and dt:
        delta = now - dt if now >= dt else timedelta(seconds=0)
        secs = int(delta.total_seconds())
        if secs < 90:
            rel_part = "vừa xong"
        elif secs < 3600:
            rel_part = f"cách đây {secs // 60} phút"
        elif secs < 86400:
            rel_part = f"cách đây {secs // 3600} giờ"
        else:
            rel_part = f"cách đây {secs // 86400} ngày"

    time_vn_str = ""
    if dt:
        # Chuyển sang giờ Việt Nam (UTC+7)
        dt_vn = dt + timedelta(hours=7)
        time_vn_str = dt_vn.strftime("%H:%M %d/%m/%Y")

    if rel_part and time_vn_str:
        if not rel_part.lower().startswith("cách đây") and "trước" not in rel_part.lower() and rel_part.lower() != "vừa xong":
            rel_part = f"{rel_part} trước"
        return f"{time_vn_str} ({rel_part})"
    elif rel_part:
        return rel_part
    elif time_vn_str:
        return time_vn_str
    return "Vừa xong"


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

    # 1.1 Chặn profile card / trang cá nhân được gợi ý / follower
    profile_indicators = r"\b(thêm bạn bè|người sáng tạo nội dung|người theo dõi|theo dõi trang|gửi lời mời kết bạn|tin nhắn riêng|xem trang cá nhân|k người theo dõi)\b"
    if re.search(profile_indicators, full_text):
        return False, "PROFILE_OR_USER_CARD"

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

    # 4. Loại trừ trường hợp bán nguyên chiếc laptop / thùng PC / máy đồng bộ
    pc_indicators = r"\b(laptop|macbook|thinkpad|máy bàn|thùng máy|dàn máy|case máy|case pc|cây pc|cây máy|đồng bộ|mini pc|all in one|aio)\b"
    has_cpu_or_gpu = bool(re.search(r"\b(i3|i5|i7|i9|ryzen\s*\d|r[3579]\b|core\s*ultra|gtx\b|rtx\b)\b", title_lower))

    if re.search(pc_indicators, title_lower) or (has_cpu_or_gpu and not title_lower.startswith(("ram", "thanh ram", "kit ram", "bán ram"))):
        if not re.search(r"\b(?:thanh|kit|cây)\s+ram\b", title_lower):
            if has_cpu_or_gpu or re.search(r"\b(main|vga|nguồn|ssd\s*\d|màn\s*hình|hdd\s*\d)\b", title_lower):
                return False, "WHOLE_LAPTOP_OR_PC"

    # 5. Tiêu đề hoặc mở đầu mô tả phải tập trung vào RAM
    is_ram_focused_title = bool(
        re.search(r"\b(ram|ddr3|ddr4|ddr5|pc3|pc4|pc5|sodimm)\b", title_lower)
        or re.search(r"\b\d+gb\s+(?:ddr\d|bus\b)", title_lower)
        or re.search(r"\b(?:kit|thanh)\s+ram\b", title_lower)
    )

    if not is_ram_focused_title:
        # Nếu tiêu đề chưa rõ RAM (ví dụ: tên shop/tên người), kiểm tra 300 ký tự đầu mô tả
        desc_head = desc_lower[:300]
        is_ram_in_desc = bool(
            re.search(r"\b(ram|ddr3|ddr4|ddr5|pc3|pc4|pc5|sodimm)\b", desc_head)
            and (
                re.search(r"\b(bán|pass|thanh lý|xả|giá|kit|thanh|samsung|kingston|corsair|crucial|adata|lexar|gskill|teamgroup)\b", desc_head)
                or re.search(r"\b\d+gb\b", desc_head)
            )
        )
        if not is_ram_in_desc:
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
        raw_chat_ids = (
            default_chat_id
            or os.environ.get("TELEGRAM_CHAT_ID_RAM")
            or os.environ.get("TELEGRAM_CHAT_ID", "")
        )
        # Hỗ trợ danh sách chat ID phân cách bằng dấu phẩy, chấm phẩy hoặc khoảng trắng
        self.default_chat_ids = [c.strip() for c in re.split(r"[,;\s]+", str(raw_chat_ids)) if c.strip()]
        self.default_chat_id = self.default_chat_ids[0] if self.default_chat_ids else ""
        env_mock = os.environ.get("MOCK_TELEGRAM", "false").lower() in ("true", "1", "yes")
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = env_mock or not bool(self.bot_token)

        self.sent_alerts = []
        self._notified_urls: Set[str] = set()
        self._notified_post_ids: Set[str] = set()
        self._load_alerted_cache_from_db()

    def _load_alerted_cache_from_db(self):
        """Khôi phục danh sách URL và Post ID đã alert từ DB khi bot khởi động."""
        try:
            from database import SessionLocal
            from app.collectors.models import FactRawListing
            with SessionLocal() as db:
                alerted = db.query(
                    FactRawListing.source_listing_id,
                    FactRawListing.url,
                    FactRawListing.raw_metadata
                ).filter(
                    FactRawListing.raw_metadata.isnot(None)
                ).all()
                for lid, u, m in alerted:
                    if isinstance(m, dict) and m.get("ram_alerted"):
                        pid = extract_facebook_post_id(u or "", str(lid or ""))
                        if pid:
                            self._notified_post_ids.add(pid)
                        if u:
                            self._notified_urls.add(u)
                            if not any(g in u.lower() for g in ["permalink.php", "photo"]):
                                self._notified_urls.add(u.split("?")[0].rstrip("/"))
        except Exception as e:
            logger.debug(f"[RAM Bot] Không thể load alerted cache từ DB: {e}")

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

        # Bóc tách và định dạng thời gian đăng bài
        posted_at = item.get("published_at") or item.get("first_seen_at")
        raw_time_str = item.get("post_time_text") or item.get("time_text") or ""
        time_display = format_time_ago(posted_at, raw_time_str)

        # Escape toàn bộ ký tự HTML đặc biệt (&, <, >) để tránh lỗi 400 Bad Request từ Telegram HTML parser
        safe_title = html.escape(str(title))
        safe_price = html.escape(str(price))
        safe_group_name = html.escape(str(group_name))
        safe_seller_name = html.escape(str(seller_name))
        safe_time_display = html.escape(str(time_display))
        safe_desc = html.escape(str(desc_snippet))
        safe_url = html.escape(str(url))

        msg = (
            "⚡ <b>PHÁT HIỆN BÀI ĐĂNG BÁN RAM MỚI</b> ⚡\n\n"
            f"📦 <b>Sản phẩm:</b> {safe_title}\n"
            f"🏷️ <b>Giá rao:</b> <code>{safe_price}</code>\n"
            f"👥 <b>Hội nhóm:</b> <b>{safe_group_name}</b>\n"
            f"👤 <b>Người bán:</b> {safe_seller_name}\n"
            f"⏰ <b>Thời gian:</b> {safe_time_display}\n"
            f"💬 <b>Bình luận:</b> {cmt_count}\n\n"
            f"📝 <b>Nội dung trích đoạn:</b>\n"
            f"<i>{safe_desc}</i>\n\n"
            f"🔗 <a href=\"{safe_url}\">👉 BẤM VÀO ĐÂY ĐỂ MỞ BÀI ĐĂNG FACEBOOK</a>"
        )
        return msg

    def send_ram_sale_alert(self, item: Dict[str, Any], chat_id: Optional[str] = None) -> bool:
        target_chats = [chat_id] if chat_id else self.default_chat_ids
        if not target_chats:
            logger.warning("[RAM Bot] Không có chat_id để gửi alert RAM.")
            return False

        url = item.get("url", "")
        post_id = extract_facebook_post_id(url, item.get("post_id", ""))
        clean_url = url.split("?")[0].rstrip("/") if url else ""

        # Kiểm tra theo Post ID duy nhất
        if post_id and post_id in self._notified_post_ids:
            logger.info(f"[RAM Bot] Bài đăng đã alert trước đó theo post_id: {post_id}")
            return False

        if url and url in self._notified_urls:
            logger.info(f"[RAM Bot] Bài đăng đã được alert trước đó theo full URL: {url}")
            return False

        if clean_url and not any(g in clean_url.lower() for g in ["permalink.php", "photo"]) and clean_url in self._notified_urls:
            logger.info(f"[RAM Bot] Bài đăng đã được alert trước đó theo clean URL: {clean_url}")
            return False

        message_text = self.format_ram_message(item)

        if self.mock_mode:
            for t_chat in target_chats:
                logger.info(f"[MOCK RAM BOT] Gửi alert RAM tới chat_id={t_chat}:\n{message_text}")
                self.sent_alerts.append({"chat_id": t_chat, "text": message_text, "item": item})
            if post_id:
                self._notified_post_ids.add(post_id)
            if url:
                self._notified_urls.add(url)
            if clean_url and not any(g in clean_url.lower() for g in ["permalink.php", "photo"]):
                self._notified_urls.add(clean_url)
            return True

        success_any = False
        for t_chat in target_chats:
            if self._send_telegram_text(message_text, t_chat, item_url=url):
                success_any = True

        if success_any:
            if post_id:
                self._notified_post_ids.add(post_id)
            if url:
                self._notified_urls.add(url)
            if clean_url and not any(g in clean_url.lower() for g in ["permalink.php", "photo"]):
                self._notified_urls.add(clean_url)
        return success_any

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
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            if "chat not found" in err_body.lower():
                logger.warning(f"[RAM Bot] Chat ID '{chat_id}' không tồn tại hoặc chưa bấm /start với Bot. Telegram yêu cầu người dùng phải bấm Start bot trước khi nhận tin nhắn.")
                return False

            logger.error(f"[RAM Bot] Lỗi gửi tin nhắn Telegram HTTP {e.code}: {err_body}")
            # Fallback gửi plain-text nếu Telegram không thể parse HTML entities
            if e.code == 400:
                try:
                    plain_text = re.sub(r"<[^>]+>", "", text)
                    fallback_payload = dict(payload)
                    fallback_payload["text"] = plain_text
                    fallback_payload.pop("parse_mode", None)
                    fallback_req = urllib.request.Request(
                        url,
                        data=json.dumps(fallback_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(fallback_req, timeout=12) as fb_resp:
                        res = json.loads(fb_resp.read().decode("utf-8"))
                        return bool(res.get("ok"))
                except Exception as fb_err:
                    logger.error(f"[RAM Bot] Fallback gửi plain text thất bại: {fb_err}")
            return False
        except Exception as e:
            logger.error(f"[RAM Bot] Lỗi gửi tin nhắn Telegram: {e}")
            return False


ram_notifier = RamTelegramNotifier()


def notify_if_ram_post(raw_listing: Any, group_name: str = "") -> bool:
    """
    Hook gọi sau khi thu thập một bài đăng từ Facebook Group hoặc Marketplace.
    Tự động kiểm tra và báo về Telegram Bot RAM nếu thỏa mãn.
    Đảm bảo Persistent Deduplication - không bao giờ gửi lại bài cũ.
    """
    # 1. Kiểm tra cờ đã alert trong DB
    meta = getattr(raw_listing, "raw_metadata", {}) or {}
    if meta.get("ram_alerted"):
        logger.info(f"[RAM Bot] Listing id={getattr(raw_listing, 'id', None)} đã được alert trước đó trong DB.")
        return False

    url = getattr(raw_listing, "url", "#")
    if not url or url == "#" or "/search" in url:
        return False

    title = getattr(raw_listing, "raw_title", "") or ""
    desc = getattr(raw_listing, "raw_description", "") or ""

    is_valid_ram, reason = is_ram_post(title, desc)
    if not is_valid_ram:
        return False

    # 2. Kiểm tra trùng lặp theo Post ID và URL
    post_id = extract_facebook_post_id(url, getattr(raw_listing, "source_listing_id", ""))
    clean_url = url.split("?")[0].rstrip("/")
    listing_id = getattr(raw_listing, "id", None)

    if post_id and post_id in ram_notifier._notified_post_ids:
        logger.info(f"[RAM Bot] Post ID {post_id} đã được alert trong bộ nhớ đệm.")
        return False

    try:
        from database import SessionLocal
        from app.collectors.models import FactRawListing
        with SessionLocal() as db:
            if post_id:
                existing_alerted = db.query(FactRawListing).filter(
                    FactRawListing.id != listing_id,
                    (FactRawListing.source_listing_id == post_id) | (FactRawListing.url.like(f"%{post_id}%"))
                ).first()
                if existing_alerted and (existing_alerted.raw_metadata or {}).get("ram_alerted"):
                    logger.info(f"[RAM Bot] Post ID {post_id} đã được alert trong listing {existing_alerted.id}.")
                    return False
            elif clean_url and not any(g in clean_url.lower() for g in ["permalink.php", "photo"]):
                existing_alerted = db.query(FactRawListing).filter(
                    FactRawListing.url.like(f"{clean_url}%"),
                    FactRawListing.id != listing_id
                ).first()
                if existing_alerted and (existing_alerted.raw_metadata or {}).get("ram_alerted"):
                    logger.info(f"[RAM Bot] URL {clean_url} đã được alert trong listing {existing_alerted.id}.")
                    return False
    except Exception as e_chk:
        logger.debug(f"[RAM Bot] Lỗi kiểm tra trùng lặp DB: {e_chk}")

    grp = group_name or meta.get("group_name", "Hội nhóm Facebook")
    seller = getattr(raw_listing, "seller_name_raw", None) or "Người bán trên nhóm"
    price_text = getattr(raw_listing, "raw_price_text", None)
    comments = getattr(raw_listing, "comments", []) or []

    pub_at = getattr(raw_listing, "published_at", None)
    first_seen = getattr(raw_listing, "first_seen_at", None)
    post_time_text = meta.get("post_time_text", "")

    item_data = {
        "title": title,
        "description": desc,
        "price_text": price_text,
        "group_name": grp,
        "seller_name": seller,
        "comment_count": len(comments),
        "url": url,
        "post_id": post_id,
        "published_at": pub_at,
        "first_seen_at": first_seen,
        "post_time_text": post_time_text
    }

    sent = ram_notifier.send_ram_sale_alert(item_data)
    if sent:
        # Cập nhật cờ ram_alerted vào Database ngay lập tức
        try:
            from database import SessionLocal
            from app.collectors.models import FactRawListing
            from sqlalchemy.orm.attributes import flag_modified
            with SessionLocal() as db:
                db_item = db.query(FactRawListing).filter(FactRawListing.id == listing_id).first()
                if db_item:
                    if not db_item.raw_metadata:
                        db_item.raw_metadata = {}
                    db_item.raw_metadata["ram_alerted"] = True
                    db_item.raw_metadata["ram_alerted_at"] = datetime.utcnow().isoformat()
                    flag_modified(db_item, "raw_metadata")
                    db.commit()
            if hasattr(raw_listing, "raw_metadata"):
                if not raw_listing.raw_metadata:
                    raw_listing.raw_metadata = {}
                raw_listing.raw_metadata["ram_alerted"] = True
        except Exception as e_save:
            logger.error(f"[RAM Bot] Lỗi lưu cờ ram_alerted vào DB: {e_save}")

    return sent


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
        raw_auth = os.environ.get("TELEGRAM_CHAT_ID_RAM", os.environ.get("TELEGRAM_CHAT_ID", ""))
        self.authorized_chat_ids = [c.strip() for c in re.split(r"[,;\s]+", str(raw_auth)) if c.strip()]
        self.authorized_chat_id = self.authorized_chat_ids[0] if self.authorized_chat_ids else ""
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
            from database import SessionLocal
            from app.collectors.models import FactRawListing
            import app.taxonomy.models  # ensure ORM mappers registered
            from app.deal_hunter.comment_appraiser import parse_vietnamese_price
            from sqlalchemy import desc

            # Cào dữ liệu theo ngữ cảnh RAM
            run_collector_job(source_code="FACEBOOK_GROUPS", query=search_query)
            run_collector_job(source_code="FACEBOOK_MARKETPLACE", query=search_query)
            run_collector_job(source_code="CHOTOT", query=search_query)

            db = SessionLocal()
            try:
                # Quét các bài đăng gần đây
                all_recent = (
                    db.query(FactRawListing)
                    .order_by(desc(FactRawListing.first_seen_at))
                    .limit(150)
                    .all()
                )

                seen_urls = set()
                q_tokens = [p.strip().lower() for p in keyword.lower().split() if p.strip()]
                # Các token kỹ thuật quan trọng như ddr3, ddr4, ddr5, 16gb, 8gb, 32gb...
                tech_tokens = [
                    t for t in q_tokens 
                    if re.match(r"^(ddr\d|pc\d|\d+gb|\d+g)$", t)
                ]

                # Phân nhóm theo 3 nguồn chính
                grouped_results: Dict[str, List[Dict[str, Any]]] = {
                    "FACEBOOK_GROUPS": [],
                    "FACEBOOK_MARKETPLACE": [],
                    "CHOTOT": []
                }

                for raw in all_recent:
                    title = raw.raw_title or ""
                    desc_text = raw.raw_description or ""
                    url = raw.url or ""

                    if not url or url in seen_urls:
                        continue

                    # BẮT BUỘC: Phải là bài đăng BÁN RAM hợp lệ
                    ok, _ = is_ram_post(title, desc_text)
                    if not ok:
                        continue

                    full_search_text = f"{title} {desc_text}".lower()

                    # Nếu người dùng tìm phiên bản cụ thể (ví dụ ddr5 hoặc 16gb), bài đăng phải chứa token đó
                    if tech_tokens:
                        has_all_tech = True
                        for tt in tech_tokens:
                            # ddr5 khớp ddr5 hoặc pc5, 16gb khớp 16gb hoặc 16g
                            if tt == "ddr5" and ("ddr5" in full_search_text or "pc5" in full_search_text):
                                continue
                            if tt == "ddr4" and ("ddr4" in full_search_text or "pc4" in full_search_text):
                                continue
                            if tt == "ddr3" and ("ddr3" in full_search_text or "pc3" in full_search_text):
                                continue
                            if tt.endswith("gb") and (tt in full_search_text or tt[:-1] in full_search_text):
                                continue
                            if tt not in full_search_text:
                                has_all_tech = False
                                break
                        if not has_all_tech:
                            continue

                    # Tính điểm khớp từ khóa
                    match_score = 0
                    title_lower = title.lower()
                    for tok in q_tokens:
                        if tok in title_lower:
                            match_score += 4
                        elif tok in full_search_text:
                            match_score += 1
                    for tt in tech_tokens:
                        if tt in title_lower:
                            match_score += 6
                        elif tt in full_search_text:
                            match_score += 3

                    # Xác định nguồn
                    src_code = ""
                    if raw.source and hasattr(raw.source, "code"):
                        src_code = raw.source.code
                    if not src_code:
                        if "facebook.com/groups" in url:
                            src_code = "FACEBOOK_GROUPS"
                        elif "facebook.com/marketplace" in url:
                            src_code = "FACEBOOK_MARKETPLACE"
                        elif "chotot.com" in url:
                            src_code = "CHOTOT"
                        else:
                            src_code = "CHOTOT"

                    if src_code not in grouped_results:
                        grouped_results[src_code] = []

                    seen_urls.add(url)
                    price_num = parse_vietnamese_price(raw.raw_price_text or "") or 0.0

                    grp_name = ""
                    if raw.raw_metadata and isinstance(raw.raw_metadata, dict):
                        grp_name = raw.raw_metadata.get("group_name", "")

                    source_str = "Chợ Tốt"
                    if src_code == "FACEBOOK_GROUPS":
                        source_str = f"Hội nhóm: {grp_name[:30]}" if grp_name else "Hội nhóm Facebook"
                    elif src_code == "FACEBOOK_MARKETPLACE":
                        source_str = "Facebook Marketplace"

                    # Nếu title là tên shop/tên người ngắn mà desc có dòng sản phẩm RAM chi tiết -> tạo display_title đẹp
                    display_title = title
                    if len(title.split()) <= 3 and not re.search(r"\b(ddr|gb|bus)\b", title_lower):
                        for dl in desc_text.split("\n"):
                            dl_clean = dl.strip()
                            if len(dl_clean) >= 10 and re.search(r"\b(ram|ddr\d|kit|\d+gb)\b", dl_clean.lower()):
                                display_title = f"{dl_clean[:55]} ({title})"
                                break

                    cmt_count = len(raw.comments) if raw.comments else 0
                    grouped_results[src_code].append({
                        "title": display_title,
                        "price": price_num,
                        "price_text": raw.raw_price_text,
                        "url": url,
                        "source": source_str,
                        "comment_count": cmt_count,
                        "match_score": match_score,
                        "first_seen_at": raw.first_seen_at
                    })

                # Sắp xếp từng nguồn theo điểm khớp và độ mới
                for sc in grouped_results:
                    grouped_results[sc].sort(
                        key=lambda x: (x["match_score"], x["first_seen_at"] or datetime.min),
                        reverse=True
                    )

                # Chọn kết quả đại diện từ mỗi nguồn (tối đa 2-3 tin/nguồn)
                fb_group_top = grouped_results["FACEBOOK_GROUPS"][:2]
                fb_mp_top = grouped_results["FACEBOOK_MARKETPLACE"][:2]
                chotot_top = grouped_results["CHOTOT"][:2]

                total_matched = len(fb_group_top) + len(fb_mp_top) + len(chotot_top)
                if total_matched == 0:
                    self._send_message(
                        chat_id,
                        f"⚠️ Hiện tại chưa tìm thấy tin <b>BÁN RAM</b> nào mới khớp với <code>{keyword}</code> trên các nhóm và sàn.\n"
                        f"💡 Tôi sẽ tiếp tục theo dõi các Hội nhóm Facebook và báo ngay cho bạn khi có người đăng bán!"
                    )
                    return

                # Soạn tin nhắn kết quả phân theo nhóm nguồn
                sections = []
                item_idx = 1

                def render_section(header: str, items_list: List[Dict[str, Any]]) -> str:
                    nonlocal item_idx
                    if not items_list:
                        return ""
                    text_sec = f"{header}\n"
                    for it in items_list:
                        cmt_badge = f" | 💬 {it['comment_count']} cmt" if it['comment_count'] > 0 else ""
                        price_disp = f"{it['price']:,.0f} đ" if it['price'] > 0 else (it['price_text'] or "Thương lượng")
                        if re.match(r"^\d{3,4}\s*m$", str(price_disp).lower().strip()):
                            price_disp = "Thương lượng"
                        time_badge = f" | ⏰ {format_time_ago(it.get('first_seen_at'))}" if it.get("first_seen_at") else ""
                        text_sec += (
                            f"<b>{item_idx}. {it['title'][:60]}</b>\n"
                            f"   🏷️ Giá: <code>{price_disp}</code> | 📍 {it['source']}{time_badge}{cmt_badge}\n"
                            f"   🔗 <a href=\"{it['url']}\">Bấm vào đây để mở bài đăng gốc</a>\n\n"
                        )
                        item_idx += 1
                    return text_sec

                if fb_group_top:
                    sections.append(render_section("👥 <b>BÀI ĐĂNG TỪ HỘI NHÓM FACEBOOK:</b>", fb_group_top))
                if fb_mp_top:
                    sections.append(render_section("🌐 <b>FACEBOOK MARKETPLACE:</b>", fb_mp_top))
                if chotot_top:
                    sections.append(render_section("🛒 <b>CHỢ TỐT:</b>", chotot_top))

                full_report = "".join(sections)
                reply_msg = (
                    f"🎯 <b>TÌM THẤY {total_matched} TIN BÁN RAM PHÙ HỢP CHO:</b> <code>{keyword}</code>\n\n"
                    f"{full_report}"
                    f"<i>(Đã lọc bỏ tin cần mua, tin linh kiện hỏng/xác và tin rác)</i>"
                )
                self._send_message(chat_id, reply_msg)

            finally:
                db.close()

        except Exception as e:
            logger.error(f"[RAM Bot] Lỗi quét dữ liệu: {e}", exc_info=True)
            self._send_message(chat_id, f"❌ Có lỗi xảy ra trong quá trình quét dữ liệu RAM: {e}")


ram_bot_listener = RamTelegramBotListener()
