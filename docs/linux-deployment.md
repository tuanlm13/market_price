# Hướng dẫn Triển khai Linux Production (Linux Home Server Deployment Guide)

Tài liệu này hướng dẫn quy trình triển khai ứng dụng **Market Price Intelligence Platform** lên **Home Server Linux** (Ubuntu 22.04 LTS / Debian 12) chạy 24/7.

---

## 1. Yêu cầu Tiên quyết trên Linux Server

- OS: Linux x86_64 (Ubuntu Server 22.04 LTS hoặc Debian 12 khuyến nghị).
- Docker Engine version 24+ và Docker Compose v2 (`docker compose`).
- Git & SSH access.
- Firewall (UFW): Cho phép các cổng dịch vụ cần thiết (hoặc qua Reverse Proxy Nginx/Caddy nội bộ).

---

## 2. Nguyên tắc Bất biến về Cơ sở Dữ liệu (Strict DB Principle)

> [!CAUTION]
> **TUYỆT ĐỐI KHÔNG COPY DATABASE LOCAL LÊN PRODUCTION!**
> Cơ sở dữ liệu Production là môi trường độc lập hoàn toàn. Khi deploy, hệ thống sẽ:
> 1. Tự động áp dụng các file migration từ thư mục `alembic/versions/`.
> 2. Tự động kích hoạt cơ chế Seed Data chuẩn mực cho Taxonomy từ mã nguồn.

---

## 3. Quy trình Triển khai Từng bước (Step-by-Step Deployment)

### Bước 1: Kết nối SSH và Kéo Mã nguồn Mới nhất
```bash
ssh user@homeserver-ip
cd /opt/market_price

# Kéo commit mới nhất từ Git
git pull origin main
```

### Bước 2: Chuẩn bị Cấu hình Môi trường Production (`.env`)
Đảm bảo file `.env` trên Linux server đã được thiết lập các giá trị mật mã an toàn:
```bash
cp .env.example .env
nano .env
```
Thiết lập:
- `SECRET_KEY`: Khóa bí mật JWT mạnh (tối thiểu 64 ký tự ngẫu nhiên).
- `DATABASE_URL`: `postgresql://tracker:StrongPassword123@db:5432/pricetracker`
- `TZ`: `Asia/Ho_Chi_Minh`

### Bước 3: Build & Khởi động Docker Containers
```bash
# Build lại image với mã nguồn mới nhất
docker compose build

# Khởi chạy toàn bộ stack ngầm
docker compose up -d

# Kiểm tra trạng thái containers
docker compose ps
```

### Bước 4: Chạy Migration CSDL trên Production
Thực thi lệnh Alembic migration bên trong container backend:
```bash
docker compose exec backend alembic upgrade head
```

Lệnh này sẽ bảo đảm toàn bộ các bảng `dim_category`, `dim_brand`, `dim_product`, `dim_variant`, `dim_condition`, `dim_market_segment` được cập nhật đồng bộ với schema mới nhất mà không làm mất bất kỳ dữ liệu cũ nào.

### Bước 5: Kiểm tra Sức khỏe và Xác minh Endpoints (Verification)
```bash
# 1. Kiểm tra healthcheck backend
curl -f http://localhost:8000/health
# Trả về: {"status": "ok"}

# 2. Kiểm tra Taxonomy API
curl -s http://localhost:8000/conditions | grep "New Sealed"
curl -s http://localhost:8000/brands | grep "Apple"
curl -s http://localhost:8000/products | grep "iPhone 16"
curl -s http://localhost:8000/market-segments | grep "APPLE|IPHONE16"

# 3. Kiểm tra log backend
docker compose logs --tail=100 -f backend
```

---

## 4. Bảo đảm Dữ liệu Bền vững & Sao lưu (Persistence & Backups)

### Volume Lưu trữ:
- CSDL PostgreSQL được gắn vào Named Volume `market_price_pgdata` (hoặc mount host path). Rebuild image hoặc restart container sẽ **không làm mất dữ liệu**.

### Cronjob Tự động Sao lưu Hàng ngày:
Thêm cronjob trên máy chủ Linux host:
```bash
crontab -e
```
Thêm dòng sau để tự động sao lưu lúc 02:00 sáng mỗi ngày:
```bash
0 2 * * * docker exec market_price-db-1 pg_dump -U tracker pricetracker | gzip > /var/backups/market_price/db_$(date +\%Y\%m\%d).sql.gz
```
