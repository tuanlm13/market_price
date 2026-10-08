# Hướng dẫn Phát triển Local trên Windows (Local Development Guide)

Tài liệu này hướng dẫn quy trình làm việc trên máy phát triển cá nhân sử dụng **Windows 11 + Docker Desktop + VS Code / Antigravity**.

---

## 1. Yêu cầu Tiên quyết (Prerequisites)

- Windows 10/11 có bật WSL2.
- Docker Desktop đang chạy (Engine Linux).
- Git.
- Port khả dụng trên máy host:
  - `8000` (FastAPI Backend)
  - `3001` (React Frontend Nginx)
  - `5432` (PostgreSQL Database)

---

## 2. Khởi động Toàn bộ Hệ thống qua Docker Compose

Tại thư mục gốc dự án:

```powershell
# 1. Tạo file môi trường nếu chưa có
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 2. Build và khởi động toàn bộ containers
docker compose build
docker compose up -d

# 3. Kiểm tra trạng thái containers
docker compose ps
```

Kết quả mong đợi:
```text
NAME                      IMAGE                   STATUS
market_price-backend-1    market_price-backend    Up (Port 8000->8000)
market_price-db-1         postgres:16             Up (healthy, Port 5432->5432)
market_price-frontend-1   market_price-frontend   Up (Port 3001->80)
```

---

## 3. Quản lý Database Migrations với Alembic

Khi có bất kỳ thay đổi nào trong model Taxonomy hoặc Database:

```powershell
# Tạo file migration tự động mới
docker exec market_price-backend-1 alembic revision --autogenerate -m "mo_ta_thay_doi"

# Áp dụng migration lên Database
docker exec market_price-backend-1 alembic upgrade head

# Kiểm tra lịch sử migration hiện tại
docker exec market_price-backend-1 alembic current
```

---

## 4. Chạy Bộ Kiểm thử Tự động (Running Tests)

Chạy bộ test PyTest trực tiếp bên trong container:

```powershell
# Chạy toàn bộ test suite
docker exec -e PYTHONPATH=/app market_price-backend-1 pytest -v

# Chạy riêng bộ test baseline
docker exec -e PYTHONPATH=/app market_price-backend-1 pytest -v tests/test_baseline.py

# Chạy riêng bộ test taxonomy
docker exec -e PYTHONPATH=/app market_price-backend-1 pytest -v tests/test_taxonomy.py
```

---

## 5. Truy cập & Kiểm tra Trực quan

- **Frontend Web UI**: [http://localhost:3001](http://localhost:3001)
- **FastAPI Interactive Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Healthcheck Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

### Test nhanh các Endpoint Taxonomy qua PowerShell:

```powershell
# Lấy danh sách 9 điều kiện phần cứng
Invoke-RestMethod -Uri "http://localhost:8000/conditions"

# Lấy danh sách danh mục (Smartphones, GPUs, RAMs)
Invoke-RestMethod -Uri "http://localhost:8000/categories"

# Lấy danh sách thương hiệu (Apple, MSI, Samsung, NVIDIA)
Invoke-RestMethod -Uri "http://localhost:8000/brands"

# Lấy danh sách sản phẩm & biến thể chuẩn
Invoke-RestMethod -Uri "http://localhost:8000/products"
Invoke-RestMethod -Uri "http://localhost:8000/variants"

# Lấy danh sách phân khúc thị trường (Market Segments)
Invoke-RestMethod -Uri "http://localhost:8000/market-segments"
```

---

## 6. Truy cập PostgreSQL Database Trực tiếp

Kết nối qua CLI của container:

```powershell
docker exec -it market_price-db-1 psql -U tracker -d pricetracker
```

Xem danh sách các bảng taxonomy:
```sql
\dt dim_*
SELECT code, name, grade, multiplier_weight FROM dim_condition;
SELECT sku, canonical_id FROM dim_variant;
```
