import os
import re
import logging
import urllib.request
import urllib.parse
import json
from typing import Dict, Any, Optional
from notifications import NotificationProvider

logger = logging.getLogger(__name__)

class TelegramNotificationProvider(NotificationProvider):
    """
    Telegram Notification Provider kế thừa NotificationProvider chuẩn của hệ thống.
    Hỗ trợ gửi tin nhắn trực tiếp qua Telegram Bot API và mock mode an toàn khi test.
    """
    def __init__(
        self,
        bot_token: Optional[str] = None,
        default_chat_id: Optional[str] = None,
        mock_mode: Optional[bool] = None
    ):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        raw_chat_id = default_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        # Hỗ trợ danh sách chat ID phân cách bằng dấu phẩy, chấm phẩy hoặc khoảng trắng
        self.default_chat_ids = [c.strip() for c in re.split(r"[,;\s]+", str(raw_chat_id)) if c.strip()]
        self.default_chat_id = self.default_chat_ids[0] if self.default_chat_ids else ""
        
        # Nếu chỉ định mock_mode hoặc env MOCK_TELEGRAM=true hoặc không có token -> mock mode
        env_mock = os.environ.get("MOCK_TELEGRAM", "false").lower() in ("true", "1", "yes")
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = env_mock or not bool(self.bot_token)
            
        self.sent_messages = []  # Lưu vết tin nhắn gửi trong mock mode để assert kiểm thử

    def send(self, subject: str, body: str, recipient: str = "") -> bool:
        """Thực thi abstract method send() từ NotificationProvider."""
        target_chats = [recipient] if recipient else self.default_chat_ids
        if not target_chats:
            return False
        text = f"*{subject}*\n\n{body}" if subject else body
        success_any = False
        for cid in target_chats:
            if self._send_telegram_text(text, cid):
                success_any = True
        return success_any

    def send_deal_alert(self, deal_data: Dict[str, Any], chat_id: Optional[str] = None) -> bool:
        """
        Định dạng và gửi thông báo 🚨 DEAL MỚI theo cấu trúc chuẩn tới tất cả chat_id được cấu hình.
        Hỗ trợ:
        - Gửi kèm ảnh thật của sản phẩm (sendPhoto) nếu có image_url.
        - Đính kèm nút bấm (Inline Keyboard) để mở thẳng bài đăng gốc.
        """
        target_chats = [chat_id] if chat_id else self.default_chat_ids
        if not target_chats:
            logger.warning("Không có chat_id nào được cấu hình để gửi deal alert.")
            return False

        message_text = self.format_deal_message(deal_data)
        image_url = deal_data.get("image_url")
        item_url = deal_data.get("url", "#")

        success_any = False
        for target_chat in target_chats:
            # Thử gửi kèm ảnh thật nếu có
            if image_url and str(image_url).startswith("http") and not self.mock_mode:
                photo_sent = self._send_telegram_photo(image_url, message_text, target_chat, item_url)
                if photo_sent:
                    success_any = True
                    continue
                logger.info(f"sendPhoto tới {target_chat} không thành công, tự động chuyển về sendMessage thông thường...")

            # Fallback gửi text kèm inline button
            if self._send_telegram_text(message_text, target_chat, item_url):
                success_any = True

        return success_any

    def _send_telegram_photo(self, photo_url: str, caption: str, chat_id: str, item_url: str) -> bool:
        if not self.bot_token or not chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        # Caption của Telegram tối đa 1024 ký tự
        trimmed_caption = caption[:1020] if len(caption) > 1024 else caption
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": trimmed_caption,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "👉 BẤM ĐỂ MỞ BÀI ĐĂNG GỐC 📱", "url": item_url}]
                ]
            }
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("ok"):
                    logger.info(f"Đã gửi alert ảnh Telegram thành công tới chat_id={chat_id}")
                    return True
        except Exception as e:
            logger.warning(f"Lỗi khi gửi sendPhoto Telegram: {e}")
            return False
        return False

    def _send_telegram_text(self, text: str, chat_id: str, item_url: str = "") -> bool:
        if self.mock_mode:
            logger.info(f"[MOCK TELEGRAM] Gửi tin nhắn tới chat_id={chat_id}:\n{text}")
            self.sent_messages.append({"chat_id": chat_id, "text": text})
            return True

        if not self.bot_token or not chat_id:
            logger.warning("Telegram Bot Token hoặc Chat ID chưa được cấu hình!")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if item_url and item_url.startswith("http"):
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": "👉 BẤM ĐỂ MỞ BÀI ĐĂNG GỐC 📱", "url": item_url}]
                ]
            }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("ok"):
                    logger.info(f"Đã gửi alert Telegram thành công tới chat_id={chat_id}")
                    return True
                else:
                    logger.error(f"Telegram API trả về lỗi: {result}")
                    return False
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if hasattr(e, 'read') else str(e)
            logger.error(f"Telegram API HTTPError {e.code}: {err_body}")
            return False
        except Exception as e:
            logger.error(f"Lỗi khi gửi Telegram alert: {e}")
            return False

    @staticmethod
    def format_currency(val: Any) -> str:
        try:
            return f"{float(val):,.0f} đ".replace(",", ".")
        except (ValueError, TypeError):
            return "N/A"

    def format_deal_message(self, d: Dict[str, Any]) -> str:
        """
        Format tin nhắn HTML cho Telegram:
        🚨 DEAL MỚI
        ...
        """
        roi_pct = f"{float(d.get('roi', 0)) * 100:.1f}%" if d.get('roi') is not None else "N/A"
        
        risks = d.get("risks", [])
        if isinstance(risks, list):
            risk_text = ", ".join(risks) if risks else "Rủi ro thấp / đã kiểm chứng"
        else:
            risk_text = str(risks)

        msg = (
            "🚨 <b>DEAL MỚI PHÁT HIỆN</b>\n\n"
            f"📦 <b>Sản phẩm:</b> {d.get('product_name', 'N/A')}\n"
            f"⚙️ <b>Phiên bản:</b> {d.get('variant_name', 'Tiêu chuẩn')}\n"
            f"✨ <b>Tình trạng:</b> {d.get('condition', 'N/A')}\n\n"
            f"🌐 <b>Nguồn:</b> {d.get('source', 'Chợ Tốt')}\n"
            f"🏷️ <b>Giá rao:</b> <code>{self.format_currency(d.get('asking_price'))}</code>\n"
            f"💵 <b>Giá vốn ước tính:</b> <code>{self.format_currency(d.get('acquisition_cost'))}</code>\n\n"
            f"📊 <b>P10:</b> {self.format_currency(d.get('p10'))}\n"
            f"📉 <b>P25:</b> {self.format_currency(d.get('p25'))}\n"
            f"🎯 <b>Median:</b> {self.format_currency(d.get('median'))}\n"
            f"⚡ <b>Quick Sell:</b> {self.format_currency(d.get('quick_sell_price'))}\n\n"
            f"💰 <b>Lợi nhuận kỳ vọng:</b> <b>{self.format_currency(d.get('expected_profit'))}</b>\n"
            f"📈 <b>ROI dự kiến:</b> <b>{roi_pct}</b>\n\n"
            f"🛡️ <b>Độ tin cậy giá:</b> {d.get('market_confidence', 0)}/100\n"
            f"💧 <b>Thanh khoản:</b> {d.get('liquidity', 0)}/100\n\n"
            f"💡 <b>Lý do:</b> {d.get('reason', 'Giá thấp hơn mốc Quick Sell')}\n"
            f"⚠️ <b>Rủi ro:</b> {risk_text}\n"
            f"🔗 <b>Link:</b> <a href=\"{d.get('url', '#')}\">Xem listing gốc</a>"
        )
        return msg
