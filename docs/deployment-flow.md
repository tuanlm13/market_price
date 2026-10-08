# Strategy & Flow: Development -> Git -> Linux Production Deployment

Tài liệu này quy định quy trình phát triển, đóng gói và triển khai ứng dụng **Market Price Intelligence Platform** từ môi trường **Windows Local** lên **Home Server Linux** chạy 24/7.

---

## 1. Kiến trúc Quy trình Triển khai (Deployment Flow Architecture)

```
+------------------------------------+          +------------------------------------+
|       LOCAL WINDOWS (Dev/Test)     |          |       HOME SERVER LINUX (Prod)     |
| - OS: Windows 11 + Docker Desktop  |          | - OS: Ubuntu Server 22.04 / Debian |
| - IDE: VS Code + Antigravity       |          | - Engine: Docker Engine + Compose  |
| - Config: .env.local               |          | - Config: .env.production          |
| - Docker: docker-compose.override  |          | - Docker: docker-compose.prod.yml  |
+------------------------------------+          +------------------------------------+
                  |                                               ^
                  | 1. Commit & Git Push                          | 2. Git Pull & Up -d
                  v                                               |
+------------------------------------------------------------------------------------+
|                                 GIT REPOSITORY                                     |
|                                 Branch: main                                       |
+------------------------------------------------------------------------------------+
```

---

## 2. Các Bước Triển khai Chi tiết (Step-by-Step Procedure)

### Bước A: Quy trình tại Windows Local (Development & Verification)
1. **Phát triển và Sửa mã nguồn**: Thực hiện chỉnh sửa mã nguồn backend/frontend trên Windows local.
2. **Kiểm thử trên Container Local**:
   ```powershell
   docker compose build
   docker compose up -d
   ```
3. **Xác nhận chức năng**:
   - Truy cập Frontend: `http://localhost:3001`
   - Truy cập API Swagger: `http://localhost:8000/docs`
   - Kiểm tra log container: `docker compose logs -f backend`
4. **Git Commit & Push**:
   ```bash
   git add .
   git commit -m "feat/fix: <mo_ta_thay_doi>"
   git push origin main
   ```

### Bước B: Quy trình tại Home Server Linux (Production Deployment)
1. **Truy cập SSH vào Home Server**:
   ```bash
   ssh user@homeserver-ip
   ```
2. **Kéo mã nguồn mới nhất từ Git**:
   ```bash
   cd /opt/market_price
   git pull origin main
   ```
3. **Build & Restart Container**:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml build
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```
4. **Kiểm tra Sức khỏe Hệ thống (Healthcheck & Logs)**:
   ```bash
   docker compose ps
   curl http://localhost:8000/health
   docker compose logs -f --tail=100 backend
   ```

---

## 3. Chiến lược Phân tách Môi trường (Environment Separation)

Để đảm bảo tính an toàn và bảo mật thông tin nhạy cảm:

### File Cấu hình Environment:
- `.env.example`: Mẫu cấu hình chuẩn (chứa tên biến mẫu, KHÔNG chứa password hay key thật). **Cam kết vào Git**.
- `.env.local`: Cấu hình cho môi trường Dev local Windows (`DATABASE_URL`, `SECRET_KEY` dev, `DEBUG=true`). **KHÔNG commit vào Git**.
- `.env.production`: Cấu hình bảo mật cho môi trường Home Server Linux (`SECRET_KEY` mạnh, `DB_PASSWORD` bảo mật, SMTP credentials thật, Telegram Bot Token). **KHÔNG commit vào Git**.

### Cấu trúc Docker Compose Files:
1. `docker-compose.yml`: File cơ sở định nghĩa cấu trúc 3 services (`db`, `backend`, `frontend`), networks và volume declarations chung.
2. `docker-compose.override.yml`: (Local Windows) Tự động được Compose load ở local. Mount mã nguồn trực tiếp (`./backend:/app`) để hot-reload code không cần rebuild image liên tục.
3. `docker-compose.prod.yml`: (Production Linux) Cấu hình tối ưu cho Production:
   - Tắt volume bind-mount code để chạy image đã compiled/built an toàn.
   - Thêm `restart: always` hoặc `unless-stopped`.
   - Cấu hình Log Rotation (`max-size: 10m`, `max-file: 3`) tránh tràn đĩa Home Server.

---

## 4. Chiến lược Thao tác Lưu trữ Dữ liệu Bền vững (Persistent Data Strategy)

Dữ liệu sản xuất **BẮT BUỘC** phải duy trì bền vững khi container restart hoặc image được rebuild.

### 1. PostgreSQL Database Data:
- Dùng Named Volume `pgdata` hoặc Host Path Mount (vd: `/var/lib/market_price/postgres_data`).
- Volume này được gắn vào `/var/lib/postgresql/data` trong container DB.

### 2. Browser Profiles & Scraper Cache:
- Khi scraper cần duy trì session/cookie với các trang thương mại điện tử, browser profile cần được lưu trữ persistent tại Host volume `/var/lib/market_price/browser_profiles`.

### 3. Automated Backups:
- Thiết lập cronjob hàng ngày trên Linux Home Server để dump PostgreSQL database vào thư mục lưu trữ backup `/var/backups/market_price/`:
  ```bash
  0 2 * * * docker exec market_price-db-1 pg_dump -U tracker pricetracker | gzip > /var/backups/market_price/db_$(date +\%Y\%m\%d).sql.gz
  ```

---

## 5. Quy trình Git & Xử lý Sự cố Khẩn cấp (Git Workflow & Emergency Fix Protocol)

### Luồng Git Chuẩn:
- Branch chính: `main`.
- Windows Local là nơi **duy nhất** thực hiện phát triển tính năng và sửa lỗi chuẩn.
- Linux Home Server chỉ đóng vai trò **Triển khai (Deployment Runtime)**.

### Quy trình Sửa lỗi Khẩn cấp (Emergency Hotfix on Linux):
Trong trường hợp hy hữu cần sửa trực tiếp Hotfix trên Linux Server để cứu hệ thống đang chạy 24/7:
1. Thực hiện sửa đổi trên mã nguồn tại Linux.
2. Kiểm tra hotfix hoạt động ổn định trên container Linux.
3. **BẮT BUỘC** commit và push ngược thay đổi về Git ngay lập tức:
   ```bash
   git add .
   git commit -m "hotfix(prod): <mo_ta_loi_da_sua>"
   git push origin main
   ```
4. Trên Windows Local, thực hiện `git pull origin main` để đồng bộ lại mã nguồn trước khi tiếp tục dev.
