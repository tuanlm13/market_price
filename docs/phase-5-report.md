# BÁO CÁO NGHIỆM THU PHASE 5: NEW LISTING APPRAISAL + TELEGRAM DEAL HUNTER

> **Dự án:** Market Price Intelligence Platform (Forked & Custom từ `devoidx/price-tracker`)  
> **Giai đoạn:** Phase 5 – New Listing Appraisal + Telegram Alert (AI Deal Hunter)  
> **Thời điểm hoàn thành:** 2026-10-07  
> **Trạng thái:** ✅ **HOÀN THÀNH TOÀN DIỆN (PASS ALL 49/49 TESTS TRÊN WINDOWS DOCKER & SẴN SÀNG LINUX DEPLOY)**

---

## 1. TỔNG QUAN KIẾN TRÚC & NGUYÊN TẮC THIẾT KẾ

### 1.1. Luồng Nghiệp vụ (End-to-End Pipeline Flow)
Toàn bộ luồng thẩm định listing mới và cảnh báo vận hành theo quy trình khép kín:

```
NEW LISTING (Cào từ Chợ Tốt / FB / Goofish)
       │
       ▼
Normalize & Identify Market Segment (Canonical Product + Variant + Condition)
       │
       ▼
Market API Query (P10, P25, Median, Fair Price, Quick Sell, Confidence, Liquidity)
       │
       ▼
Deterministic Financial Math (Acquisition Cost, Landed Cost, Expected Profit, ROI, Discounts)
       │
       ▼
Rule Engine First (Configurable Per-Category: min_profit, min_roi, acceptable_conditions)
       ├───► Không đạt / Lỗ ───► Decision = SKIP (Dừng sớm, không tốn LLM token)
       │
       ▼
Candidate Tiềm Năng (BUY / WATCH)
       │
       ▼
Condition & Risk Analysis / Deep AI Explanation (Phân tích rủi ro mô tả, người bán, comments)
       │  * Ràng buộc: AI TUYỆT ĐỐI KHÔNG ĐƯỢC sửa số liệu thị trường (Market numbers)
       ▼
Deduplication Engine (Chặn spam alert cùng 1 listing)
       ├───► Đã alert & giá không đổi / giảm < 5% ───► Bỏ qua (Dedup)
       └───► Listing mới HOẶC giá giảm >= 5% HOẶC có giá seller comment mới
             │
             ▼
Telegram Notification Provider (Gửi alert Telegram với cấu trúc 🚨 DEAL MỚI)
             │
             ▼
Lưu vết FactDealAppraisal (audit trail, alert status, thời gian)
```

### 1.2. Các Nguyên Tắc Cốt Lõi
1. **Không tạo benchmark bằng LLM:** Số liệu thị trường (P10, P25, Median, Fair Price, Quick Sell, Confidence, Liquidity) được tính toán 100% bằng thuật toán toán học thống kê deterministic từ Phase 4.
2. **AI không sửa số liệu:** AI chỉ đánh giá rủi ro định tính và đưa ra lời giải thích đầu tư, tuyệt đối không chỉnh sửa số liệu tài chính hay giá trị thị trường.
3. **Rule Engine First:** Sàng lọc trước bằng bộ quy tắc cứng, chỉ gọi Deep AI cho các ứng viên thực sự tiềm năng giúp tiết kiệm chi phí token và giảm độ trễ.
4. **Không tạo hệ thống notification song song:** Kế thừa trực tiếp `NotificationProvider` hiện có từ `backend/notifications.py`.
5. **An toàn bảo mật:** Tuyệt đối không commit Bot Token Telegram hay Secret Key vào repository; hỗ trợ Mock Provider trong unit test và phát triển local.
6. **Không auto-buy / Không auto-message seller:** Hệ thống đóng vai trò hỗ trợ ra quyết định (Decision Support Intelligence), cung cấp thông tin và đường dẫn để chuyên viên review và thực hiện giao dịch thủ công.

---

## 2. CHI TIẾT CÁC MODULE TRIỂN KHAI

### 2.1. Cấu hình Ngưỡng Linh Hoạt theo Danh Mục ([`thresholds.py`](file:///c:/Users/tuanlm2/Documents/market_price/backend/app/deal_hunter/thresholds.py))
Không hardcode một mức ngưỡng chung cho toàn bộ sản phẩm. Mỗi danh mục có đặc thù biên lợi nhuận, chi phí đệm và tiêu chuẩn rủi ro khác nhau:

| Danh mục | Min Profit (VND) | Min ROI | Min Confidence | Min Liquidity | Tình trạng chấp nhận | Buffer VN | Landed Goofish Multiplier + Buffer |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **SMARTPHONE** | 500.000 đ | 10% | 50 | 40 | LIKE_NEW, EXCELLENT, GOOD, FAIR | 60.000 đ | 1.06x + 150.000 đ |
| **GPU** | 700.000 đ | 12% | 50 | 35 | LIKE_NEW, EXCELLENT, GOOD *(loại FAIR)* | 80.000 đ | 1.08x + 200.000 đ |
| **RAM** | 150.000 đ | 18% | 40 | 30 | LIKE_NEW, EXCELLENT, GOOD, FAIR | 30.000 đ | 1.05x + 50.000 đ |
| **LAPTOP** | 1.000.000 đ | 12% | 50 | 35 | LIKE_NEW, EXCELLENT, GOOD | 100.000 đ | 1.08x + 250.000 đ |
| **DEFAULT** | 400.000 đ | 12% | 45 | 35 | LIKE_NEW, EXCELLENT, GOOD, FAIR | 50.000 đ | 1.07x + 100.000 đ |

### 2.2. Deterministic Financial Math ([`calculator.py`](file:///c:/Users/tuanlm2/Documents/market_price/backend/app/deal_hunter/calculator.py))
- **Giá vốn (Acquisition Cost):**
  - **Nguồn VN (Chợ Tốt, Facebook):** $\text{acquisition\_cost} = \text{asking\_price} + \text{vn\_cost\_buffer}$.
  - **Nguồn Goofish (Nhập khẩu TQ):** $\text{acquisition\_cost} = \text{asking\_price} \times \text{multiplier} + \text{fixed\_shipping\_buffer}$.
- **Lợi nhuận kỳ vọng (Expected Profit):**
  $$\text{expected\_profit} = \text{quick\_sell\_price} - \text{acquisition\_cost}$$
- **Tỷ suất sinh lời (ROI):**
  $$\text{ROI} = \frac{\text{expected\_profit}}{\text{acquisition\_cost}}$$
- **Tỷ lệ chiết khấu so với thị trường:**
  $$\text{discount\_vs\_median} = \frac{\text{median} - \text{asking\_price}}{\text{median}}$$
  $$\text{discount\_vs\_p25} = \frac{\text{p25} - \text{asking\_price}}{\text{p25}}$$
  $$\text{discount\_vs\_quick\_sell} = \frac{\text{quick\_sell\_price} - \text{asking\_price}}{\text{quick\_sell\_price}}$$
- **Phân vị thị trường (Market Position):** `DEEP_DISCOUNT` ($\le P10$), `BELOW_P25` ($\le P25$), `BELOW_MEDIAN` ($\le \text{Median}$), `AT_MEDIAN`, `ABOVE_MEDIAN`.

### 2.3. Bóc Tách Giá & Bình Luận Facebook ([`comment_appraiser.py`](file:///c:/Users/tuanlm2/Documents/market_price/backend/app/deal_hunter/comment_appraiser.py))
- Parser regex chuyên sâu xử lý mọi biến thể ngôn ngữ giao dịch thực tế tại Việt Nam:
  - `"12tr2 lấy nhanh"` $\rightarrow 12.200.000$ đ.
  - `"11m8 bay gấp"` $\rightarrow 11.800.000$ đ.
  - `"fix 12.5tr"` / `"12,5 củ"` $\rightarrow 12.500.000$ đ.
  - `"850k không bớt"` $\rightarrow 850.000$ đ.
  - `"12.200.000 đ"` $\rightarrow 12.200.000$ đ.
- **Phân tích ngữ cảnh bình luận:**
  - Nếu **người bán** bình luận giảm giá (hoặc chứa từ khóa chốt giá nhanh: *"lấy nhanh"*, *"bay nhanh"*, *"fix"*, *"giảm còn"*): trích xuất thành **`effective_seller_price`** để thẩm định theo giá chốt mới.
  - Nếu **thành viên khác** chào bán ké (*"ké em có con này 11tr8"*, *"mình có cây tương tự 11m"*): tự động nhận diện và trích xuất thành danh sách **`sub_candidates`** độc lập.

### 2.4. Telegram Notification Provider ([`telegram_provider.py`](file:///c:/Users/tuanlm2/Documents/market_price/backend/app/deal_hunter/telegram_provider.py))
Kế thừa trực tiếp `NotificationProvider`:
- Tích hợp Telegram Bot API chính thức (`/sendMessage`).
- Hỗ trợ **Mock Mode** khi biến môi trường `MOCK_TELEGRAM=true` hoặc khi chưa cấu hình token $\rightarrow$ đảm bảo unit test và CI chạy offline an toàn 100%.
- Định dạng tin nhắn chuẩn HTML chuyên nghiệp:
```
🚨 DEAL MỚI PHÁT HIỆN

📦 Sản phẩm: iPhone 13 128GB
⚙️ Phiên bản: 128GB VN/A
✨ Tình trạng: LIKE_NEW (99%)

🌐 Nguồn: Chợ Tốt
🏷️ Giá rao: 10.500.000 đ
💵 Giá vốn ước tính: 10.560.000 đ

📊 P10: 11.500.000 đ
📉 P25: 12.000.000 đ
🎯 Median: 12.800.000 đ
⚡ Quick Sell: 11.800.000 đ

💰 Lợi nhuận kỳ vọng: 1.240.000 đ
📈 ROI dự kiến: 11.7%

🛡️ Độ tin cậy giá: 92/100
💧 Thanh khoản: 85/100

💡 Lý do: Kèo thơm thử nghiệm: Giá rẻ hơn P10 thị trường 1tr đ.
⚠️ Rủi ro: Rủi ro thấp / đã kiểm chứng
🔗 Link: Xem listing gốc
```

### 2.5. Cơ Chế Chống Trùng Lặp Cảnh Báo (Deduplication Engine)
Trong [`service.py`](file:///c:/Users/tuanlm2/Documents/market_price/backend/app/deal_hunter/service.py):
- Nếu listing **chưa từng gửi alert**: Gửi cảnh báo ngay khi `decision == "BUY"`.
- Nếu listing **đã từng gửi alert thành công trước đó**:
  - **Mặc định:** KHÔNG alert lại (chống spam bot).
  - **Ngoại lệ cho phép alert lại:**
    1. Giá giảm đáng kể $\ge 5\%$ so với giá đã alert lần trước ($\text{new\_price} \le \text{prev\_price} \times 0.95$).
    2. Người bán comment giảm giá mới thấp hơn (`effective_price_source == "SELLER_COMMENT"`).
    3. Tình trạng máy được cập nhật quan trọng.

### 2.6. Bảng Dữ Liệu Lịch Sử Thẩm Định ([`FactDealAppraisal`](file:///c:/Users/tuanlm2/Documents/market_price/backend/app/deal_hunter/models.py))
Đã tạo bảng và migration Alembic `44142d43fd19`:
- Lưu toàn bộ lịch sử thẩm định: `decision`, `asking_price`, `acquisition_cost`, `quick_sell_price`, `expected_profit`, `roi`, `discounts`, `market_position`, `risks`, `ai_reasoning`, `alert_sent`, `alert_sent_at`, `effective_price_source`.
- Index tối ưu hóa truy vấn: `decision`, `alert_sent`, `normalized_listing_id`.

---

## 3. DANH SÁCH REST API ENDPOINTS

Router: [`/deals`](file:///c:/Users/tuanlm2/Documents/market_price/backend/app/routers/deal_hunter.py)

| Endpoint | Method | Chức năng | Input / Params | Output |
| :--- | :---: | :--- | :--- | :--- |
| `/deals/hunt` | `POST` | Kích hoạt quét hàng loạt các tin mới chưa thẩm định | `limit: int = 50` | `{status: "success", summary: {scanned, buys, watches, skips, alerts_sent}}` |
| `/deals/appraise/{listing_id}` | `POST` | Thẩm định chi tiết 1 tin cụ thể | `listing_id: int`, `force_alert: bool` | Toàn bộ kết quả thẩm định, rủi ro, quyết định và trạng thái gửi alert |
| `/deals` | `GET` | Lấy danh sách cơ hội đầu tư | `decision: BUY\|WATCH\|SKIP`, `limit`, `skip` | Danh sách phân trang kèm đầy đủ chỉ số tài chính |
| `/deals/stats` | `GET` | Thống kê số lượng cơ hội và alerts | Không | `{total_appraisals, buy_count, watch_count, skip_count, alerts_sent}` |
| `/deals/test-telegram` | `POST` | Kiểm tra kết nối Telegram và định dạng tin nhắn mẫu | `chat_id: Optional[str]` | `{status, mock_mode, chat_id_used}` |

---

## 4. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG (AUTOMATED TEST VERIFICATION)

Hệ thống đã bổ sung bộ kiểm thử chuyên biệt [`backend/tests/test_deal_hunter.py`](file:///c:/Users/tuanlm2/Documents/market_price/backend/tests/test_deal_hunter.py) và chạy trên Docker container:

```bash
docker exec market_price-backend-1 pytest -v
```

### Kết quả chi tiết:
- **Tổng số tests:** **49/49 PASSED (100%)**
- **Thời gian chạy:** 2.37 giây
- **Chi tiết từng nhóm test:**
  - `tests/test_deal_hunter.py`: **8/8 PASSED**
    - `test_category_thresholds`: Kiểm tra cấu hình per-category.
    - `test_calculator_acquisition_cost`: Tính giá vốn nội địa vs Landed cost Goofish.
    - `test_calculator_financial_metrics`: Tính profit, ROI, discounts, phân vị.
    - `test_vietnamese_price_parsing`: Bóc tách giá tiếng Việt phức tạp.
    - `test_comment_appraisal_effective_price_and_sub_candidates`: Phân tích comment.
    - `test_deal_appraiser_decision_flow`: Kiểm thử luồng BUY, WATCH, SKIP và rủi ro.
    - `test_telegram_provider_mock_and_message_format`: Kiểm tra message Telegram và mock.
    - `test_deduplication_price_drop_rule`: Kiểm tra chống spam và ngưỡng giảm $\ge 5\%$.
  - `tests/test_market.py`: **9/9 PASSED**
  - `tests/test_collectors.py`: **9/9 PASSED**
  - `tests/test_normalization.py`: **10/10 PASSED**
  - `tests/test_taxonomy.py`: **10/10 PASSED**
  - `tests/test_baseline.py`: **3/3 PASSED**

---

## 5. HƯỚNG DẪN TRIỂN KHAI VÀ VẬN HÀNH

### 5.1. Môi trường Local Development (Windows)
1. Trong file `.env` local, thiết lập:
   ```env
   MOCK_TELEGRAM=true
   ```
2. Unit tests chạy hoàn toàn offline không phụ thuộc internet và không cần bot token thật:
   ```powershell
   docker exec market_price-backend-1 pytest -v tests/test_deal_hunter.py
   ```
3. Nếu muốn nhận tin nhắn thử nghiệm trên Telegram thật trong quá trình phát triển local:
   - Tạo bot qua [@BotFather](https://t.me/BotFather) để lấy `BOT_TOKEN`.
   - Lấy Chat ID của bạn (hoặc Group ID) qua [@userinfobot](https://t.me/userinfobot).
   - Đặt vào `.env`:
     ```env
     TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
     TELEGRAM_CHAT_ID=987654321
     MOCK_TELEGRAM=false
     ```
   - Gọi test:
     ```powershell
     curl -X POST http://localhost:8000/deals/test-telegram
     ```

### 5.2. Môi trường Home Server Linux Production
1. Cập nhật file `.env.production` trên Linux server (không commit vào Git):
   ```env
   TELEGRAM_BOT_TOKEN=<production_bot_token>
   TELEGRAM_CHAT_ID=<production_group_channel_id>
   MOCK_TELEGRAM=false
   ```
2. Khởi chạy và kiểm tra:
   ```bash
   docker compose -f docker-compose.yml up -d
   docker compose logs -f backend
   ```
3. Kiểm tra định kỳ:
   - `scheduler` đã tự động nạp job `run_deal_hunter_job` định kỳ mỗi **10 phút** để tự động quét toàn bộ tin mới và bắn alert Telegram.
   - Quản trị viên có thể xem lịch sử cơ hội bất kỳ lúc nào qua endpoint `GET /deals?decision=BUY`.

---

## 6. ĐÁNH GIÁ DEFINITION OF DONE (DOD)

| Tiêu chuẩn nghiệm thu | Trạng thái | Minh chứng |
| :--- | :---: | :--- |
| **New Listing $\rightarrow$ Normalize $\rightarrow$ Market API** | ✅ Đạt | Tích hợp đồng bộ từ `FactNormalizedListing` sang `get_market_analytics` |
| **Deterministic Math (Profit, ROI, Discounts)** | ✅ Đạt | Công thức toán chuẩn xác trong `calculator.py`, kiểm thử bởi unit test |
| **Landed Cost Goofish & Cost Buffer VN** | ✅ Đạt | `calculate_acquisition_cost` phân tách rõ ràng theo nguồn tin |
| **Rule Engine First + Ngưỡng theo Category** | ✅ Đạt | Cấu hình độc lập trong `thresholds.py`, dừng sớm nếu lỗ không tốn LLM |
| **Deep AI Appraisal & Không sửa Market numbers** | ✅ Đạt | Phân tích rủi ro trong `appraiser.py`, toàn bộ số liệu giữ nguyên từ math |
| **Xử lý bình luận Facebook (Seller price & Sub-candidate)** | ✅ Đạt | Bóc tách regex linh hoạt tiếng Việt trong `comment_appraiser.py` |
| **Telegram Notification Provider** | ✅ Đạt | Kế thừa `NotificationProvider`, format HTML chuẩn `🚨 DEAL MỚI` |
| **Deduplication Engine** | ✅ Đạt | Chống trùng lặp, chỉ alert lại khi giá giảm $\ge 5\%$ hoặc có giá seller mới |
| **Bảo mật Credentials** | ✅ Đạt | Không commit token vào Git; template `.env.example` chuẩn mực |
| **Không Auto-Buy / Auto-Message Seller** | ✅ Đạt | Hệ thống phân tích thụ động và hỗ trợ quyết định |
| **Windows Test & Linux Deploy Readiness** | ✅ Đạt | **49/49 tests PASS**, Docker container backend & database đồng bộ |
