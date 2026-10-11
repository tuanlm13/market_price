import os
import json
import logging
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.collectors.base import BaseCollector
from app.normalization.rules.classification_rules import parse_facebook_time

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

    CACHE_TTL_HOURS = int(os.getenv("FB_GROUPS_CACHE_TTL_HOURS", "12"))

    def load_joined_groups(self, page=None, force_refresh: bool = False) -> List[Dict[str, str]]:
        """
        Tải danh sách các nhóm Facebook tài khoản đã tham gia.
        - Tự động kiểm tra TTL (mặc định 12 giờ).
        - Nếu cache còn hạn và không yêu cầu force_refresh: đọc nhanh từ cache.
        - Nếu cache quá hạn hoặc force_refresh=True (và có page): tự động đồng bộ lại từ https://www.facebook.com/groups/joins/
        """
        cache_file = self._get_cache_path()
        cached_groups = []
        cache_is_fresh = False

        if os.path.exists(cache_file):
            try:
                # Kiểm tra thời gian sửa đổi gần nhất của file cache
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
                cache_age = datetime.now() - mtime
                if cache_age < timedelta(hours=self.CACHE_TTL_HOURS):
                    cache_is_fresh = True
                
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        cached_groups = data
            except Exception as e:
                logger.warning(f"[{self.source_code}] Lỗi đọc cache nhóm: {e}")

        # Nếu cache còn hạn và không bắt buộc làm mới, trả về ngay
        if cached_groups and cache_is_fresh and not force_refresh:
            logger.info(f"[{self.source_code}] Đã nạp {len(cached_groups)} nhóm từ cache (còn hạn, TTL={self.CACHE_TTL_HOURS}h)")
            return cached_groups

        # Nếu có page Playwright thì tự động quét đồng bộ danh sách nhóm mới
        if page:
            logger.info(f"[{self.source_code}] Đang tự động quét/làm mới danh sách nhóm từ /groups/joins/...")
            try:
                page.goto("https://www.facebook.com/groups/joins/", timeout=40000, wait_until="domcontentloaded")
                page.wait_for_timeout(3500)

                curr = page.url.lower()
                if "login" in curr or "checkpoint" in curr:
                    logger.warning(f"[{self.source_code}] Không thể quét /groups/joins/ do chưa đăng nhập hoặc gặp checkpoint")
                    return cached_groups

                # Cuộn trang thích ứng (adaptive scrolling) cho đến khi lấy hết tất cả nhóm
                seen = {}
                last_count = 0
                stable_iterations = 0
                for _ in range(30):
                    links = page.query_selector_all("a[href*='/groups/']")
                    for l in links:
                        href = l.get_attribute("href") or ""
                        text = l.inner_text().strip()
                        if text and len(text) > 3 and not any(x in text.lower() for x in ["xem nhóm", "tạo nhóm", "khám phá", "bảng feed"]):
                            if "/groups/" in href and not any(x in href for x in ["/feed", "/discover", "/create", "/joins", "/category"]):
                                clean_name = text.split("\n")[0].strip()
                                clean_href = href.split("?")[0].strip()
                                if clean_name not in seen and len(clean_name) > 3:
                                    seen[clean_name] = clean_href

                    if len(seen) == last_count and len(seen) > 0:
                        stable_iterations += 1
                        if stable_iterations >= 3:
                            break
                    else:
                        stable_iterations = 0
                    last_count = len(seen)

                    page.mouse.wheel(0, 1800)
                    page.wait_for_timeout(1200)

                group_list = [{"name": k, "url": v} for k, v in seen.items()]
                if group_list:
                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(group_list, f, ensure_ascii=False, indent=2)
                    logger.info(f"[{self.source_code}] Đã tự động cập nhật {len(group_list)} nhóm đã tham gia vào cache")
                    return group_list
            except Exception as e:
                logger.warning(f"[{self.source_code}] Quét nhóm trực tiếp thất bại: {e}")

        # Fallback: Trả về cache cũ nếu quét trực tiếp không thành công
        if cached_groups:
            logger.info(f"[{self.source_code}] Sử dụng cache hiện có ({len(cached_groups)} nhóm)")
            return cached_groups

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

    def _extract_posts_from_page(self, page, default_group_name: str = "", default_group_url: str = "") -> List[Dict[str, Any]]:
        """
        Bóc tách toàn bộ bài đăng từ trang Facebook hiện tại (hỗ trợ cả Search Posts, Groups Feed và Group Internal Search).
        Tự động nhận diện group_name, group_url, post_id, author, giá, thời gian đăng, ảnh và bình luận.
        """
        posts_data = []
        feed = page.query_selector("div[role='feed']")
        post_elements = feed.query_selector_all(":scope > div") if feed else page.query_selector_all("div[role='article']")
        logger.info(f"[{self.source_code}] Tìm thấy {len(post_elements)} phần tử bài đăng trên trang")

        for idx, post in enumerate(post_elements[:25]):
            text_content = post.inner_text().strip()
            lines = [l.strip() for l in text_content.split("\n") if l.strip() and l.strip() != "Facebook"]
            if len(lines) < 2:
                continue

            # Bỏ qua thẻ thành viên / profile card / gợi ý kết bạn
            profile_signals = [
                "thêm bạn bè", "người sáng tạo nội dung", "người theo dõi",
                "theo dõi trang", "xem trang cá nhân", "gửi lời mời", "nhắn tin riêng"
            ]
            if any(sig in text_content.lower() for sig in profile_signals):
                continue

            # Trích xuất nhóm từ link bên trong bài viết
            extracted_group_name = default_group_name
            extracted_group_url = default_group_url
            for a in post.query_selector_all("a[href*='/groups/']"):
                href = a.get_attribute("href") or ""
                if "/user/" in href:
                    continue
                gid_m = re.search(r"/groups/([^/?]+)", href)
                if gid_m:
                    extracted_group_url = f"https://www.facebook.com/groups/{gid_m.group(1)}/"
                    txt = a.inner_text().strip().split("\n")[0]
                    if txt and len(txt) > 2 and not any(x in txt.lower() for x in ["xem thêm", "thích", "bình luận", "chia sẻ", "nhóm"]):
                        extracted_group_name = txt
                    break

            if not extracted_group_name and lines:
                extracted_group_name = lines[0]

            # Bóc tách permalink và post_id chính xác
            post_id = ""
            post_url = ""
            all_links = post.query_selector_all("a")
            for a in all_links:
                href = a.get_attribute("href") or ""
                m = re.search(r"set=(?:gm|pcb)\.(\d+)", href)
                if m:
                    post_id = m.group(1)
                    gid = re.search(r"/groups/([^/?]+)", extracted_group_url)
                    gid_val = gid.group(1) if gid else ""
                    post_url = f"https://www.facebook.com/groups/{gid_val}/posts/{post_id}/" if gid_val else f"https://www.facebook.com/permalink.php?story_fbid={post_id}"
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
                        gid = re.search(r"/groups/([^/?]+)", extracted_group_url)
                        gid_val = gid.group(1) if gid else ""
                        post_url = f"https://www.facebook.com/groups/{gid_val}/posts/{post_id}/" if gid_val else f"https://www.facebook.com/permalink.php?story_fbid={post_id}"
                        break

            if not post_url or not post_id:
                continue

            # Bóc tách người đăng
            author_el = post.query_selector("h2, h3, strong, a[role='link']")
            author = author_el.inner_text().strip() if author_el else lines[0]

            # Bóc tách giá từ bài đăng (hỗ trợ cả 13tr5, 15tr9, 15.500.000, 19.990.000đ, 20,9 tr)
            price_str = "Thương lượng"
            p_mixed = re.search(r'\b(\d+\s*(?:tr|củ|m)[\d.,]+)\b', text_content, re.IGNORECASE)
            if p_mixed:
                price_str = p_mixed.group(1)
            else:
                p_full = re.search(r'(\d{1,3}(?:[.,]\d{3}){1,3}\s*(?:đ|vnd|vnđ)?)', text_content, re.IGNORECASE)
                if p_full:
                    price_str = p_full.group(1)
                else:
                    p_std = re.search(r'(\d+[\d.,]*\s*(?:triệu|tr\b|củ\b|k(?!\s*(?:người|lượt|thành|member|follow|sub|bạn))\b|đ\b|vnd|vnđ|m(?![a-z])))', text_content, re.IGNORECASE)
                    if p_std:
                        price_str = p_std.group(1)

            # Bóc tách thời gian đăng bài
            post_time_text = ""
            extracted_pub_at = None
            time_candidates = post.query_selector_all("a[role='link'], a[href*='/posts/'], a[href*='permalink'], a[href*='set=pcb'], a[href*='set=gm'], a[href*='story_fbid'], abbr, time")
            for tc in time_candidates:
                aria_val = tc.get_attribute("aria-label") or tc.get_attribute("title") or ""
                txt_val = tc.inner_text().strip()
                parsed_dt, parsed_str = parse_facebook_time(raw_text=txt_val, aria_label=aria_val)
                if parsed_dt:
                    extracted_pub_at = parsed_dt
                    post_time_text = parsed_str or aria_val or txt_val
                    break
                elif parsed_str and not post_time_text:
                    post_time_text = parsed_str

            if not extracted_pub_at:
                for l in lines:
                    l_s = l.strip()
                    parsed_dt, parsed_str = parse_facebook_time(raw_text=l_s)
                    if parsed_dt:
                        extracted_pub_at = parsed_dt
                        post_time_text = parsed_str or l_s
                        break
                    elif parsed_str and any(kw in l_s.lower() for kw in ["trước", "vừa xong", "hôm qua", "tháng"]):
                        if not post_time_text:
                            post_time_text = l_s

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

            posts_data.append({
                "post_id": post_id,
                "author": author,
                "group_name": extracted_group_name or "Hội Nhóm Facebook",
                "group_url": extracted_group_url or default_group_url,
                "text": text_content,
                "price": price_str,
                "published_at": extracted_pub_at,
                "post_time_text": post_time_text,
                "url": post_url,
                "image_url": img_url,
                "comments": extracted_comments
            })

        return posts_data

    def fetch(self, query: str = "ram", target_group_url: str = "", **kwargs) -> List[Dict[str, Any]]:
        """
        Thu thập bài viết từ Facebook Groups hoàn toàn tự động:
        1. Target Group: Quét trực tiếp nhóm chỉ định nếu có target_group_url.
        2. Direct Search: Quét trực tiếp qua Facebook Search Posts (tự động bao hàm MỌI nhóm bạn đã tham gia mà không cần cache trước).
        3. Periodic Feed: Quét thẳng https://www.facebook.com/groups/feed/ nếu query rỗng.
        4. Bổ sung: Lấy thêm bài từ 1-2 nhóm chuyên sâu nếu có trong danh sách nhóm đã tham gia.
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

                scrape_targets = []

                if target_group_url and "/groups/" in target_group_url:
                    clean_target = target_group_url.split("?")[0].rstrip("/")
                    encoded_q = urllib.parse.quote(query.strip()) if query else ""
                    tgt_url = f"{clean_target}/search/?q={encoded_q}" if encoded_q else clean_target
                    scrape_targets.append({
                        "name": "Nhóm Chỉ Định",
                        "url": clean_target,
                        "search_url": tgt_url
                    })
                elif query and query.strip():
                    encoded_q = urllib.parse.quote(query.strip())
                    force_refresh = kwargs.get("force_refresh", False)
                    joined_groups = self.load_joined_groups(page=None, force_refresh=force_refresh)
                    relevant = self.get_relevant_joined_groups(query, joined_groups, max_groups=4)

                    # 1. ƯU TIÊN CAO NHẤT: Quét trực tiếp các hội nhóm đã tham gia liên quan nhất (100% bài viết chuẩn trong group)
                    for rg in relevant:
                        r_url = rg.get("url", "").split("?")[0].rstrip("/")
                        if r_url:
                            scrape_targets.append({
                                "name": rg.get("name", "Hội Nhóm Chuyên Sâu"),
                                "url": r_url,
                                "search_url": f"{r_url}/search/?q={encoded_q}"
                            })

                    # 2. Bổ sung: Tìm kiếm toàn cục Facebook Search Posts nếu còn thiếu mục tiêu
                    if len(scrape_targets) < 3:
                        scrape_targets.append({
                            "name": "Facebook Search Posts",
                            "url": "",
                            "search_url": f"https://www.facebook.com/search/posts/?q={encoded_q}"
                        })
                else:
                    # Chế độ theo dõi định kỳ: Bảng tin nhóm thời gian thực
                    scrape_targets.append({
                        "name": "Facebook Groups Feed",
                        "url": "https://www.facebook.com/groups/feed/",
                        "search_url": "https://www.facebook.com/groups/feed/"
                    })

                logger.info(f"[{self.source_code}] Bắt đầu quét {len(scrape_targets)} mục tiêu cho từ khóa '{query}'")

                for target in scrape_targets:
                    search_url = target["search_url"]
                    t_name = target["name"]
                    t_url = target.get("url", "")

                    logger.info(f"[{self.source_code}] Truy cập '{t_name}' tại {search_url}")
                    try:
                        page.goto(search_url, timeout=35000, wait_until="domcontentloaded")
                        page.wait_for_timeout(3500)

                        curr = page.url.lower()
                        if "login" in curr or "checkpoint" in curr:
                            logger.error(f"[{self.source_code}] Cần đăng nhập lại Facebook hoặc gặp Checkpoint")
                            break

                        # Cuộn trang 2-3 lần để tải dữ liệu bài đăng
                        for _ in range(3):
                            page.mouse.wheel(0, 1600)
                            page.wait_for_timeout(1200)

                        # Click tất cả nút "Xem thêm" để mở trọn vẹn mô tả bài đăng
                        page.evaluate("""() => {
                            const seeMores = Array.from(document.querySelectorAll('div[role="button"]'))
                                .filter(el => el.innerText && el.innerText.includes('Xem thêm'));
                            seeMores.forEach(el => el.click());
                        }""")
                        page.wait_for_timeout(1000)

                        extracted = self._extract_posts_from_page(page, default_group_name=t_name, default_group_url=t_url)
                        for itm in extracted:
                            if not any(x.get("post_id") == itm["post_id"] for x in items):
                                items.append(itm)

                    except Exception as e_grp:
                        logger.warning(f"[{self.source_code}] Lỗi khi cào '{t_name}': {e_grp}")
                        continue

                # Đọc bình luận chuyên sâu cho Top 2 bài đăng đầu tiên (nếu có permalink fbid rõ ràng)
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
                published_at = post.get("published_at")

                if not post_time_str or not published_at:
                    for l in text_no_hidden.split("\n"):
                        l_clean = l.strip()
                        if not l_clean or len(l_clean) < 2:
                            continue
                        parsed_dt, parsed_str = parse_facebook_time(raw_text=l_clean)
                        if parsed_dt:
                            if not post_time_str:
                                post_time_str = parsed_str
                            if not published_at:
                                published_at = parsed_dt
                            break

                if not published_at and post_time_str:
                    parsed_dt, _ = parse_facebook_time(raw_text=post_time_str)
                    if parsed_dt:
                        published_at = parsed_dt

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
