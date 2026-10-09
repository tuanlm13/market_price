import os
import json
import logging
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

class FacebookGroupCollector(BaseCollector):
    source_code = "FACEBOOK_GROUPS"
    default_interval_minutes = 60
    default_currency = "VND"

    # Từ điển ánh xạ ngữ cảnh sản phẩm -> từ khóa tìm kiếm nhóm liên quan
    TOPIC_SYNONYMS = {
        "ram": ["ram", "linh kiện", "pc", "laptop", "máy tính", "ổ cứng", "ssd", "hdd", "ddr", "phần cứng"],
        "laptop": ["laptop", "pc", "máy tính", "linh kiện", "dell", "thinkpad", "macbook"],
        "dji": ["dji", "pocket", "action cam", "action", "osmo", "camera", "gopro", "insta360", "flycam", "quay phim", "luna"],
        "pocket": ["pocket", "dji", "action cam", "action", "osmo", "camera", "gopro", "insta360", "luna"],
        "osmo": ["osmo", "pocket", "dji", "action cam", "action", "camera", "gopro", "insta360"],
        "iphone": ["iphone", "apple", "ipad", "macbook", "ios", "điện thoại", "smartphone"],
        "robot": ["robot", "hút bụi", "lau nhà", "ecovacs", "roborock", "dreame", "tineco", "mova"],
        "sạc": ["sạc", "pin", "anker", "cuktech", "ugreen", "shargeek", "dự phòng", "cáp"],
        "sac": ["sạc", "pin", "anker", "cuktech", "ugreen", "shargeek", "dự phòng"],
        "tai nghe": ["tai nghe", "true wireless", "airpods", "earbuds", "headphone", "audio"],
        "máy ảnh": ["máy ảnh", "camera", "lens", "ống kính", "sony", "canon", "fujifilm"],
    }

    def _get_cache_path(self) -> str:
        candidates = [
            os.path.join(self.browser_profiles_base, "joined_groups_cache.json"),
            "/app/browser_profiles/joined_groups_cache.json",
            "/app/joined_groups_cache.json",
            os.path.join(os.getcwd(), "backend", "joined_groups_cache.json"),
            os.path.join(os.getcwd(), "joined_groups_cache.json"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return candidates[0]

    def load_joined_groups(self, page=None) -> List[Dict[str, str]]:
        """
        Tải danh sách các nhóm Facebook tài khoản đã tham gia.
        Ưu tiên đọc từ cache; nếu chưa có thì quét trực tiếp từ https://www.facebook.com/groups/joins/
        """
        cache_file = self._get_cache_path()
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    groups = json.load(f)
                    if isinstance(groups, list) and len(groups) > 0:
                        logger.info(f"[{self.source_code}] Đã nạp {len(groups)} nhóm đã tham gia từ cache {cache_file}")
                        return groups
            except Exception as e:
                logger.warning(f"[{self.source_code}] Lỗi đọc cache nhóm: {e}")

        # Nếu có page Playwright đang mở thì quét tự động
        if page:
            logger.info(f"[{self.source_code}] Đang quét danh sách nhóm đã tham gia từ /groups/joins/...")
            try:
                page.goto("https://www.facebook.com/groups/joins/", timeout=40000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
                for _ in range(4):
                    page.mouse.wheel(0, 1500)
                    page.wait_for_timeout(1000)

                links = page.query_selector_all("a[href*='/groups/']")
                seen = {}
                for l in links:
                    href = l.get_attribute("href") or ""
                    text = l.inner_text().strip()
                    if text and len(text) > 3 and not any(x in text.lower() for x in ["xem nhóm", "tạo nhóm", "khám phá", "bảng feed"]):
                        if "/groups/" in href and not any(x in href for x in ["/feed", "/discover", "/create", "/joins", "/category"]):
                            clean_name = text.split("\n")[0].strip()
                            clean_href = href.split("?")[0].strip()
                            if clean_name not in seen and len(clean_name) > 3:
                                seen[clean_name] = clean_href

                group_list = [{"name": k, "url": v} for k, v in seen.items()]
                if group_list:
                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(group_list, f, ensure_ascii=False, indent=2)
                    logger.info(f"[{self.source_code}] Đã lưu {len(group_list)} nhóm đã tham gia vào cache")
                    return group_list
            except Exception as e:
                logger.warning(f"[{self.source_code}] Quét nhóm trực tiếp thất bại: {e}")

        return []

    def get_relevant_joined_groups(self, query: str, joined_groups: List[Dict[str, str]], max_groups: int = 3) -> List[Dict[str, str]]:
        """
        Phân tích từ khóa tìm kiếm và lọc ra các hội nhóm đã tham gia phù hợp nhất.
        Ví dụ:
        - 'ram laptop' -> Hội mua bán RAM, ổ cứng SSD, HDD, LK PC Mới & Cũ...
        - 'dji pocket 3' -> Hội Mua Bán Action Cam Việt Nam (DJI Pocket 3...)...
        """
        if not joined_groups:
            return []

        q_lower = query.lower().strip()
        tokens = [t for t in re.split(r"\s+", q_lower) if len(t) >= 2]

        # Mở rộng từ khóa tìm kiếm theo từ điển
        expanded_terms = set(tokens)
        for t in tokens:
            for k, syns in self.TOPIC_SYNONYMS.items():
                if t in k or k in t:
                    expanded_terms.update(syns)

        scored_groups = []
        for g in joined_groups:
            g_name = g.get("name", "")
            g_name_lower = g_name.lower()
            score = 0

            # 1. Khớp từ khóa trực tiếp
            for t in tokens:
                if t in g_name_lower:
                    score += 15

            # 2. Khớp từ đồng nghĩa / lĩnh vực liên quan
            for term in expanded_terms:
                if term in g_name_lower:
                    score += 5

            # 2.1 Ưu tiên cực cao cho các dòng thiết bị đặc thù (pocket, action cam, rtx, thinkpad, robot...)
            spec_keywords = ["pocket", "action cam", "action camera", "rtx", "thinkpad", "macbook", "ecovacs", "roborock", "cuktech"]
            for sk in spec_keywords:
                if sk in q_lower and sk in g_name_lower:
                    score += 30

            # 3. Ưu tiên các nhóm mua bán, chợ, thanh lý
            trade_keywords = ["mua bán", "chợ", "thanh lý", "trao đổi", "giao lưu", "deal"]
            if any(tk in g_name_lower for tk in trade_keywords):
                score += 5

            if score > 0:
                scored_groups.append((score, g))

        scored_groups.sort(key=lambda x: x[0], reverse=True)
        relevant = [x[1] for x in scored_groups[:max_groups]]

        # Fallback nếu không có nhóm chuyên biệt: lấy các nhóm chợ linh kiện / công nghệ chung
        if not relevant:
            fallback_groups = [
                g for g in joined_groups 
                if any(w in g.get("name", "").lower() for w in ["chợ", "mua bán", "công nghệ", "máy tính", "tin học", "it"])
            ]
            relevant = fallback_groups[:max_groups]

        return relevant

    def _read_post_comments(self, page, group_id: str, post_id: str) -> List[Dict[str, Any]]:
        """
        Mở bài viết trực tiếp qua permalink để đọc bình luận của các thành viên.
        Bóc tách người bình luận, nội dung comment (giá chốt, fix giá, cảnh báo phốt...).
        """
        comments: List[Dict[str, Any]] = []
        permalink_url = f"https://www.facebook.com/permalink.php?story_fbid={post_id}&id={group_id}"
        
        try:
            logger.info(f"[{self.source_code}] Đang đọc bình luận từ permalink: {permalink_url}")
            page.goto(permalink_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Cuộn xuống nhẹ để kích hoạt tải comment
            page.mouse.wheel(0, 800)
            page.wait_for_timeout(1500)

            main_text = page.inner_text("body")
            if "Chưa có bình luận nào" in main_text:
                return []

            lines = [l.strip() for l in main_text.split("\n") if l.strip() and l.strip() != "Facebook"]

            # Tìm vị trí bắt đầu phần bình luận (sau nội dung bài đăng)
            comment_start_idx = -1
            for idx, line in enumerate(lines):
                if any(kw in line.lower() for kw in ["bình luận dưới tên", "viết bình luận", "phù hợp nhất", "tất cả bình luận"]):
                    comment_start_idx = idx + 1
                    break

            if comment_start_idx != -1 and comment_start_idx < len(lines):
                comment_lines = lines[comment_start_idx:]
                current_author = ""
                for line in comment_lines[:25]:
                    # Bỏ qua các nhãn hệ thống
                    if any(x in line.lower() for x in ["thích", "phản hồi", "chia sẻ", "người liên hệ", "đang hoạt động", "nhà quảng cáo"]):
                        continue
                    if not current_author and len(line) < 35 and not line.isdigit():
                        current_author = line
                    elif current_author:
                        comments.append({
                            "source_comment_id": f"fb_{group_id}_{post_id}_c{len(comments)}",
                            "author": current_author,
                            "raw_text": line,
                            "created_at_source": datetime.utcnow()
                        })
                        current_author = ""
        except Exception as e:
            logger.debug(f"[{self.source_code}] Đọc bình luận permalink bỏ qua do: {e}")

        return comments

    def fetch(self, query: str = "ram", target_group_url: str = "", **kwargs) -> List[Dict[str, Any]]:
        """
        Tìm kiếm trên các hội nhóm Facebook đã tham gia liên quan đến từ khóa và đọc bình luận.
        Hỗ trợ chỉ định quét trực tiếp một nhóm cụ thể qua target_group_url hoặc truyền kèm URL trong query.
        """
        items: List[Dict[str, Any]] = []

        # Tự động trích xuất group URL nếu người dùng dán kèm link nhóm vào trong query
        group_url_match = re.search(r"https?://(?:www\.)?facebook\.com/groups/[^/\s]+/?", query)
        if group_url_match and not target_group_url:
            target_group_url = group_url_match.group(0)
            query = query.replace(target_group_url, "").strip(" :;=-")
            if not query:
                query = "pocket"

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                context = self.launch_browser_context(p)
                page = context.new_page()

                # 1. Tải danh sách nhóm đã tham gia
                joined_groups = self.load_joined_groups(page=page)
                
                # 2. Lọc các nhóm liên quan đến từ khóa (tăng lên 6 nhóm để đa dạng nguồn tin)
                target_groups = self.get_relevant_joined_groups(query, joined_groups, max_groups=6)

                # Nếu có nhóm chỉ định cụ thể, ưu tiên đưa lên đầu tiên
                if target_group_url and "/groups/" in target_group_url:
                    clean_target = target_group_url.split("?")[0].rstrip("/")
                    tg_name = "Nhóm Được Chỉ Định"
                    found_in_cache = False
                    for jg in joined_groups:
                        if clean_target in jg.get("url", "") or jg.get("url", "").rstrip("/") == clean_target:
                            tg_name = jg.get("name", tg_name)
                            found_in_cache = True
                            break
                    target_obj = {"name": tg_name, "url": clean_target}
                    target_groups = [target_obj] + [g for g in target_groups if clean_target not in g.get("url", "")]
                    
                    # Nếu nhóm mới chưa có trong cache joined_groups, tự động bổ sung vào cache
                    if not found_in_cache:
                        joined_groups.append(target_obj)
                        cache_file = self._get_cache_path()
                        try:
                            with open(cache_file, "w", encoding="utf-8") as f:
                                json.dump(joined_groups, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass

                if not target_groups:
                    logger.warning(f"[{self.source_code}] Không tìm thấy nhóm đã tham gia phù hợp cho '{query}'")
                    # Fallback tìm kiếm chung trên Search Posts toàn Facebook
                    encoded_q = urllib.parse.quote(query.strip())
                    target_groups = [{"name": "Facebook Search Posts", "url": f"https://www.facebook.com/search/posts?q={encoded_q}"}]

                logger.info(f"[{self.source_code}] Sẽ quét {len(target_groups)} nhóm cho từ khóa '{query}': {[g['name'] for g in target_groups]}")

                # 3. Quét từng nhóm liên quan
                for group in target_groups:
                    group_name = group.get("name", "Hội Nhóm Facebook")
                    group_url = group.get("url", "")
                    
                    if "/search/posts" in group_url:
                        search_url = group_url
                    else:
                        encoded_q = urllib.parse.quote(query.strip())
                        clean_url = group_url.split("?")[0].rstrip("/")
                        search_url = f"{clean_url}/search/?q={encoded_q}"

                    logger.info(f"[{self.source_code}] Truy cập nhóm: '{group_name}' tại {search_url}")
                    try:
                        page.goto(search_url, timeout=35000, wait_until="domcontentloaded")
                        page.wait_for_timeout(3500)

                        # Check Auth / Checkpoint
                        curr = page.url.lower()
                        if "login" in curr or "checkpoint" in curr:
                            logger.error(f"[{self.source_code}] Cần đăng nhập lại Facebook hoặc gặp Checkpoint")
                            break

                        # Cuộn trang 2 lần để kích hoạt tải các bài đăng mới hơn
                        for _ in range(2):
                            page.mouse.wheel(0, 1600)
                            page.wait_for_timeout(1200)

                        # Click tất cả nút "Xem thêm" để mở trọn vẹn mô tả bài đăng
                        page.evaluate("""() => {
                            const seeMores = Array.from(document.querySelectorAll('div[role="button"]'))
                                .filter(el => el.innerText && el.innerText.includes('Xem thêm'));
                            seeMores.forEach(el => el.click());
                        }""")
                        page.wait_for_timeout(1000)

                        feed = page.query_selector("div[role='feed']")
                        post_elements = feed.query_selector_all(":scope > div") if feed else page.query_selector_all("div[role='article']")

                        logger.info(f"[{self.source_code}] Tìm thấy {len(post_elements)} bài đăng trong nhóm '{group_name}'")

                        # Bóc tách từng bài đăng
                        for idx, post in enumerate(post_elements[:20]):
                            text_content = post.inner_text().strip()
                            lines = [l.strip() for l in text_content.split("\n") if l.strip() and l.strip() != "Facebook"]
                            if len(lines) < 2:
                                continue

                            # 1. BỎ QUA nếu là Thẻ thành viên / Profile Card / Gợi ý kết bạn
                            profile_signals = [
                                "thêm bạn bè", "người sáng tạo nội dung", "người theo dõi",
                                "theo dõi trang", "xem trang cá nhân", "gửi lời mời", "nhắn tin riêng"
                            ]
                            if any(sig in text_content.lower() for sig in profile_signals):
                                continue

                            # Bóc tách permalink và post_id chính xác (BẮT BUỘC có permalink tới bài đăng)
                            post_id = ""
                            post_url = ""
                            all_links = post.query_selector_all("a")
                            for a in all_links:
                                href = a.get_attribute("href") or ""
                                m = re.search(r"set=(?:gm|pcb)\.(\d+)", href)
                                if m:
                                    post_id = m.group(1)
                                    gid_match = re.search(r"/groups/([^/?]+)", group_url)
                                    gid = gid_match.group(1) if gid_match else ""
                                    post_url = f"https://www.facebook.com/groups/{gid}/posts/{post_id}/" if gid else f"https://www.facebook.com/permalink.php?story_fbid={post_id}"
                                    break
                                elif "/posts/" in href or "/permalink/" in href:
                                    clean_h = href.split("?")[0]
                                    post_url = f"https://www.facebook.com{clean_h}" if clean_h.startswith("/") else clean_h
                                    id_m = re.search(r"/posts/(\d+)", post_url)
                                    if id_m:
                                        post_id = id_m.group(1)
                                    break
                                elif "story_fbid=" in href or "fbid=" in href:
                                    id_m = re.search(r"(?:story_fbid|fbid)=(\d+)", href)
                                    if id_m:
                                        post_id = id_m.group(1)
                                        gid_match = re.search(r"/groups/([^/?]+)", group_url)
                                        gid = gid_match.group(1) if gid_match else ""
                                        post_url = f"https://www.facebook.com/groups/{gid}/posts/{post_id}/" if gid else f"https://www.facebook.com/permalink.php?story_fbid={post_id}"
                                        break

                            # BẮT BUỘC: Nếu không lấy được permalink bài viết (ví dụ banner, menu...) -> BỎ QUA
                            if not post_url or not post_id or post_url == search_url:
                                continue

                            # Bóc tách người đăng
                            author_el = post.query_selector("h2, h3, strong, a[role='link']")
                            author = author_el.inner_text().strip() if author_el else lines[0]

                            # Bóc tách giá từ bài đăng (tránh nhầm MHz thành m hoặc K người theo dõi)
                            price_match = re.search(r"(\d+[\d.,]*\s*(?:triệu|tr\b|củ\b|k(?!\s*(?:người|lượt|thành|member|follow|sub|bạn))\b|đ\b|vnd|vnđ|m(?![a-z])))", text_content, re.IGNORECASE)
                            price_str = price_match.group(1) if price_match else "Thương lượng"

                            # Bóc tách thời gian đăng bài
                            post_time_text = ""
                            time_link = post.query_selector("span[id] a[role='link'], a[href*='/posts/'] span, a[href*='permalink'] span, abbr")
                            if time_link:
                                aria_t = time_link.get_attribute("aria-label") or time_link.inner_text().strip()
                                if aria_t and any(w in aria_t.lower() for w in ["phút", "giờ", "ngày", "vừa xong", "hôm qua", "tháng"]):
                                    post_time_text = aria_t

                            if not post_time_text:
                                for l in lines:
                                    l_s = l.strip()
                                    if re.search(r"^(?:\d+\s*(?:phút|giờ|ngày|tuần|tháng)(?:\s*trước)?|vừa xong|hôm qua\s*lúc\s*\d+:\d+)$", l_s.lower()):
                                        post_time_text = l_s
                                        break
                                    m_rel = re.search(r"\b(\d+\s*(?:phút|giờ|ngày|tuần)\s*trước|vừa xong)\b", l_s.lower())
                                    if m_rel:
                                        post_time_text = m_rel.group(1)
                                        break

                            # Bóc tách ảnh sản phẩm
                            img_el = post.query_selector("img[src*='fbcdn']")
                            img_url = img_el.get_attribute("src") if img_el else ""

                            # Bóc tách bình luận ngay trên bài viết (nếu hiển thị)
                            extracted_comments = []
                            cmt_elements = post.query_selector_all("ul li, div[role='article']")
                            for c_idx, c_el in enumerate(cmt_elements[:8]):
                                c_txt = c_el.inner_text().strip()
                                if len(c_txt) > 3 and "Facebook" not in c_txt:
                                    extracted_comments.append({
                                        "source_comment_id": f"{post_id}_c{c_idx}",
                                        "author": c_txt.split("\n")[0] if "\n" in c_txt else "Thành viên nhóm",
                                        "raw_text": c_txt,
                                        "created_at_source": datetime.utcnow()
                                    })

                            items.append({
                                "post_id": post_id,
                                "author": author,
                                "group_name": group_name,
                                "group_url": group_url,
                                "text": text_content,
                                "price": price_str,
                                "post_time_text": post_time_text,
                                "url": post_url,
                                "image_url": img_url,
                                "comments": extracted_comments
                            })

                    except Exception as e_grp:
                        logger.warning(f"[{self.source_code}] Lỗi khi cào nhóm '{group_name}': {e_grp}")
                        continue

                # 4. Đọc bình luận chuyên sâu cho Top 2 bài đăng đầu tiên (nếu có permalink fbid rõ ràng)
                for item in items[:2]:
                    if not item.get("comments") and item.get("post_id") and item["post_id"].isdigit():
                        gid_match = re.search(r"/groups/([^/?]+)", item.get("group_url", ""))
                        if gid_match:
                            deep_comments = self._read_post_comments(page, gid_match.group(1), item["post_id"])
                            if deep_comments:
                                item["comments"] = deep_comments

                context.close()
        except Exception as e:
            if "AUTH_REQUIRED" in str(e) or "CHECKPOINT" in str(e):
                raise
            logger.warning(f"[{self.source_code}] fetch encountered issue: {e}")

        logger.info(f"[{self.source_code}] Hoàn thành cào được {len(items)} bài viết từ các hội nhóm liên quan.")
        return items

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        Chuẩn hóa bài viết từ các Group Facebook thành listing structure kèm danh sách bình luận.
        """
        parsed: List[Dict[str, Any]] = []
        if isinstance(raw_data, list):
            for post in raw_data:
                post_id = str(post.get("post_id") or post.get("id") or "")
                if not post_id:
                    continue

                full_text = post.get("text", "")
                # Gỡ bỏ các ký tự ẩn / combining diacritics chống cào dữ liệu của Facebook
                text_no_hidden = re.sub(r"[\u0300-\u036f\u200b-\u200f\ufeff]", "", full_text)
                clean_lines = [
                    l.strip() for l in text_no_hidden.split("\n")
                    if l.strip() and len(l.strip()) > 2
                    and not l.strip().lower().startswith("facebook") 
                    and l.strip() not in ("·", "Xem thêm", "Thích", "Chia sẻ", "Bình luận", "Gửi tin nhắn")
                    and not re.match(r"^\d+\s*(?:giờ|phút|ngày|tháng|tuần)\b", l.strip().lower())
                ]
                
                # Tìm dòng tiêu đề có nghĩa (ưu tiên dòng chứa thông số hoặc tên sản phẩm)
                title = ""
                for l in clean_lines:
                    if len(l) >= 8 and not l.isdigit():
                        if re.search(r"\b(ram|ddr|gb|pc|laptop|ssd|hdd|vga|rtx|gtx|bán|pass|thanh lý)\b", l.lower()):
                            title = l[:150]
                            break
                if not title:
                    for l in clean_lines:
                        if len(l) >= 10 and not l.isdigit():
                            title = l[:150]
                            break
                if not title:
                    title = clean_lines[0][:150] if clean_lines else f"{post.get('author', 'Bài đăng')} - {post.get('price', 'Thương lượng')}"

                # Bóc tách thời gian đăng bài
                post_time_str = post.get("post_time_text", "")
                if not post_time_str:
                    for l in text_no_hidden.split("\n"):
                        l_clean = l.strip()
                        if re.search(r"^(?:\d+\s*(?:phút|giờ|ngày|tuần|tháng)(?:\s*trước)?|vừa xong|hôm qua\s*lúc\s*\d+:\d+)$", l_clean.lower()):
                            post_time_str = l_clean
                            break
                        m_rel = re.search(r"\b(\d+\s*(?:phút|giờ|ngày|tuần)\s*trước|vừa xong)\b", l_clean.lower())
                        if m_rel:
                            post_time_str = m_rel.group(1)
                            break

                published_at = post.get("published_at")
                if not published_at:
                    published_at = datetime.utcnow()
                    if post_time_str:
                        pt_low = post_time_str.lower()
                        m_m = re.search(r"(\d+)\s*phút", pt_low)
                        m_h = re.search(r"(\d+)\s*giờ", pt_low)
                        m_d = re.search(r"(\d+)\s*ngày", pt_low)
                        if m_m:
                            published_at = datetime.utcnow() - timedelta(minutes=int(m_m.group(1)))
                        elif m_h:
                            published_at = datetime.utcnow() - timedelta(hours=int(m_h.group(1)))
                        elif m_d:
                            published_at = datetime.utcnow() - timedelta(days=int(m_d.group(1)))

                parsed.append({
                    "source_listing_id": post_id,
                    "url": post.get("url") or f"https://www.facebook.com/groups/post/{post_id}",
                    "raw_title": title,
                    "raw_description": "\n".join(clean_lines) if clean_lines else full_text,
                    "raw_price_text": post.get("price", "Thương lượng"),
                    "raw_currency": "VND",
                    "seller_name_raw": post.get("author", "Thành viên nhóm"),
                    "seller_id_raw": str(post.get("author_id", "")),
                    "location_raw": post.get("location", "Toàn quốc"),
                    "published_at": published_at,
                    "raw_metadata": {
                        "source_platform": "facebook_groups",
                        "group_name": post.get("group_name", "Hội Nhóm Mua Bán"),
                        "group_url": post.get("group_url", ""),
                        "image_url": post.get("image_url", ""),
                        "post_time_text": post_time_str,
                        "comment_count": len(post.get("comments", []))
                    },
                    "comments": post.get("comments", [])
                })
        return parsed
