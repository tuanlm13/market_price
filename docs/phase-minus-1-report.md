# Báo cáo Tổng kết Phase -1: Audit & Baseline Setup

**Dự án:** Market Price Intelligence Platform (Forked from `devoidx/price-tracker`)  
**Môi trường:** Windows Local (Docker Desktop) & Linux Home Server 24/7  
**Tác giả:** Senior Software Architect & Senior DevOps Engineer  

---

## 1. Tổng quan Phase -1 & Mục tiêu Đã Đạt Được

Mục tiêu chính của Phase -1 là thiết lập nền móng vững chắc cho dự án bằng cách **FORK/CUSTOMIZE** repository `devoidx/price-tracker`, **KHÔNG** viết lại từ đầu (Rewrite from scratch), đồng thời chuẩn hóa quy trình phát triển từ Windows local lên Linux Home Server.

### Kết quả đạt được (Definition of Done Checklist):
- [x] Clone & Audit toàn bộ mã nguồn repo nguyên bản `devoidx/price-tracker`.
- [x] Đánh giá kiến trúc hiện tại và lập bảng quyết định **KEEP / MODIFY / REPLACE / REMOVE / ADD**.
- [x] Thiết lập và chạy thử nghiệm Baseline thành công trên Windows Local bằng Docker Desktop.
- [x] Xây dựng quy trình triển khai chuẩn **Windows Local -> Git -> Linux Home Server**.
- [x] Đã thiết kế chiến lược **Persistent Data** (DB PostgreSQL, Browser profiles, Backups).
- [x] Đã thiết kế chiến lược **Environment Separation** (`.env.example`, `.env.local`, `.env.production`).
- [x] Xác định nợ kỹ thuật (Technical Debt) và lập lộ trình chuyển giao sang Phase 0.

---

## 2. Kiến trúc Mã nguồn Gốc (Base Repository Architecture)

Hệ thống nguyên bản được thiết kế theo kiến trúc 3-tier containerized:

1. **Frontend Tier (`/frontend`)**:
   - React 18 + Vite SPA, Axios client (`api.js`), Recharts visualization.
   - Nginx Alpine làm web server production và reverse proxy.
2. **Backend Tier (`/backend`)**:
   - FastAPI Python 3.10+ quản lý 11 REST endpoints.
   - Playwright Python (`sync_playwright`) quét giá qua headless Chromium/Firefox.
   - APScheduler (`BackgroundScheduler`) lưu trữ job state trong DB PostgreSQL.
   - Email SMTP / Web Push (VAPID) gửi cảnh báo.
3. **Database Tier (`PostgreSQL 16`)**:
   - Lưu trữ người dùng, sản phẩm, nguồn crawler, lịch sử giá, cảnh báo và cài đặt.

---

## 3. Bảng Quyết định Kiến trúc Module (Module Architecture Decisions)

| Current Module | Decision | Reason | Target Strategy |
| :--- | :--- | :--- | :--- |
| **FastAPI Core** | **KEEP** | Khung API chuẩn, async/await hiệu năng cao, tự động sinh OpenAPI spec. | Giữ nguyên core; bổ sung logging, rate limiting và multi-tenant capabilities. |
| **PostgreSQL 16** | **KEEP** | Hệ quản trị CSDL quan hệ tin cậy, hỗ trợ ACID và đánh chỉ mục tốt cho lịch sử giá. | Giữ nguyên DB engine; nâng cấp schema từ tracker cá nhân sang Market Intelligence. |
| **React / Vite + Nginx** | **KEEP** | React UI linh hoạt, Vite build siêu nhanh, Nginx tối ưu phân phối static SPA. | Giữ nguyên stack UI; mở rộng Dashboard với so sánh đối thủ và bộ lọc thị trường. |
| **Playwright Python** | **KEEP / MODIFY** | Giải pháp cào dữ liệu web động (JS rendered) hiện đại và mạnh mẽ nhất. | Giữ Playwright; chuyển sang async context pool, hỗ trợ Rotating Proxy và Cookie session. |
| **APScheduler** | **KEEP / MODIFY** | Đơn giản, tự động khôi phục job từ PostgreSQL sau khi restart container. | Giữ nguyên cho Phase 0; chuẩn bị chuyển sang Celery + Redis khi mở rộng quy mô crawler lớn. |
| **Product Model** | **MODIFY** | Model hiện tại chỉ lưu tên sản phẩm cá nhân. | Nâng cấp thành **Market Product Model**: bổ sung SKU, Brand, EAN/UPC, Category Tree. |
| **Source Model** | **MODIFY** | Hiện tại chỉ lưu 1 URL và 1 CSS selector cơ bản. | Nâng cấp thành **Competitor Source Model**: lưu Retailer ID, Proxy rule, Parsing Strategy. |
| **Price History Model**| **MODIFY** | Chi lưu thông tin giá cơ bản. | Nâng cấp để lưu Normalized Price (quy đổi ngoại tệ), Tình trạng tồn kho (Stock), Chiết khấu. |
| **Alert System** | **EXTEND** | Chỉ hỗ trợ Email SMTP và Push notification cơ bản. | Mở rộng hỗ trợ Telegram Bot Webhook, Discord Webhook, Cảnh báo bất thường giá (Anomaly Drop/Spike). |
| **Frontend Dashboard** | **EXTEND** | Giao diện danh sách sản phẩm đơn giản. | Mở rộng thành Market Price Intelligence Portal: Ma trận giá đối thủ, Báo cáo biến động. |
| **Database Migrations** | **ADD** | Thiếu công cụ quản lý versioning schema (hiện tại dùng script SQL thô `init.sql`). | Bổ sung **Alembic Database Migrations** để migrate DB an toàn trên production. |

---

## 4. Hướng dẫn Chạy Baseline trên Windows Local

### Đòi hỏi môi trường:
- Windows 11 + Docker Desktop (WSL2 Engine active)
- Git

### Các bước khởi chạy:
1. **Chuẩn bị file cấu hình môi trường**:
   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```
2. **Build và khởi chạy các Docker containers**:
   ```powershell
   docker compose build
   docker compose up -d
   ```
3. **Kiểm tra trạng thái hệ thống**:
   ```powershell
   docker compose ps
   docker compose logs -f
   ```
4. **Địa chỉ truy cập**:
   - **Frontend UI**: [http://localhost:3001](http://localhost:3001)
   - **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Healthcheck**: [http://localhost:8000/health](http://localhost:8000/health)
   - **Database Postgres**: `localhost:5432` (User: `tracker`, Pass: `tracker`, DB: `pricetracker`)

---

## 5. Chiến lược Triển khai Production (Linux Home Server)

Chi tiết quy trình triển khai được tài liệu hóa tại [`docs/deployment-flow.md`](file:///c:/Users/tuanlm2/Documents/market_price/docs/deployment-flow.md):

1. **Phát triển tại Windows Local**: Thử nghiệm và kiểm thử tính năng trên Docker Desktop local.
2. **Git Commit & Push**: Đẩy mã nguồn chuẩn lên nhánh `main` trên Git server.
3. **Pull & Up tại Home Server Linux**:
   - Kết nối SSH vào Linux Home Server.
   - Chạy `git pull origin main`.
   - Thực thi `docker compose build` và `docker compose up -d`.
4. **Chiến lược Khẩn cấp (Emergency Hotfix)**:
   - Nếu sửa khẩn cấp trên Linux Server, bắt buộc phải `git commit` và `git push` về Git ngay sau đó.
   - Ngay lập tức thực hiện `git pull` trên Windows Local để tránh lệch mã nguồn.

---

## 6. Chiến lược Dữ liệu Bền vững (Persistent Data Strategy)

Dữ liệu sản xuất không được phép nằm trong container hay bị mất khi rebuild image:

- **PostgreSQL Volume**: Đăng ký Named Volume `pgdata` gắn vào `/var/lib/postgresql/data`. Trên Linux Home Server có thể bind mount trực tiếp vào thư mục an toàn `/var/lib/market_price/postgres_data`.
- **Browser Profiles / Session Storage**: Gắn volume `/app/browser_profiles` để duy trì session cookie và tránh bị các trang web chặn khi quét lại.
- **Tự động Backup CSDL**: Thiết lập Cronjob sao lưu định kỳ hàng ngày trên Linux Home Server ra thư mục lưu trữ ngoài `/var/backups/market_price/`.

---

## 7. Chiến lược Phân tách Môi trường & Git

- **Git Branches**: Giữ cấu trúc đơn giản với nhánh `main`. Không làm phức tạp hóa GitFlow ở giai đoạn này.
- **Environment Files**:
  - `.env.example`: Lưu mẫu biến môi trường (commit vào Git).
  - `.env.local`: Cấu hình dev trên Windows (tự tạo, không commit).
  - `.env.production`: Cấu hình thật trên Linux Home Server (bảo mật tuyệt đối, không commit).
- **Docker Compose Files**:
  - `docker-compose.yml`: File gốc chứa cấu hình cơ bản.
  - `docker-compose.override.yml`: Cấu hình mount source code cho Windows local dev.
  - `docker-compose.prod.yml`: Cấu hình tối ưu log rotation và restart policy cho Linux Home Server.

---

## 8. Kết quả Kiểm thử Baseline & Nợ Kỹ thuật (Technical Debt)

### Kết quả Kiểm thử Baseline Hiện tại:
- **Test suite nguyên bản**: Chưa có bộ unit test / integration test tự động (thiếu thư mục `tests/`).
- **Khởi động Containers**: Cả 3 container (`frontend`, `backend`, `db`) khởi động thành công và liên kết chính xác qua Docker Network.
- **Kết nối CSDL**: Backend kết nối thành công tới Postgres DB, tự động khởi tạo bảng qua `init.sql`.

### Nợ Kỹ thuật (Technical Debt) Phát hiện từ Repo Gốc:
1. **Thiếu Alembic Migration**: CSDL dựa hoàn toàn vào `init.sql` lúc khởi tạo ban đầu, gây khó khăn khi thay đổi schema sau này.
2. **Mã nguồn Backend Đơn khối trong Scraper**: `scraper.py` dùng `sync_playwright` khởi tạo browser đồng bộ cho mỗi request, có nguy cơ gây nghẽn tài nguyên CPU/RAM khi quét nhiều trang cùng lúc.
3. **APScheduler chạy In-Process**: Trực tiếp chạy cùng tiến trình Uvicorn FastAPI. Nếu mở rộng backend thành nhiều container (multi-workers), scheduler sẽ bị trùng lặp job.
4. **Báo cáo lỗi Scraper còn sơ khai**: Chưa lưu trữ thông tin chi tiết về DOM snapshot hay lý do thất bại cụ thể khi bị Cloudflare / Bot Detector chặn.

---

## 9. Kế hoạch Lộ trình Chuyển sang Phase 0

Phase 0 sẽ tập trung chuẩn hóa hạ tầng kỹ thuật và chuẩn bị Schema cho Market Intelligence:

1. **Bổ sung Alembic Database Migration** cho Backend FastAPI.
2. **Tối ưu hóa Playwright Scraper Engine**: Đưa vào Proxy rotation, User-Agent pool và async context handling.
3. **Thiết kế Schema Market Price Intelligence**:
   - Model `MarketProduct` (Brand, SKU, EAN/UPC, Category Tree).
   - Model `CompetitorSource` (Retailer info, Dynamic selector rules).
   - Model `MarketPriceRecord` (Base price, Currency conversion, Stock status).
4. **Bổ sung Unit Tests Baseline**: Xây dựng bộ test suite ban đầu cho FastAPI Routers và Scraper logic qua PyTest.
