# Báo cáo Tổng kết Phase 0: Foundation Refactor & Product Taxonomy

**Dự án:** Market Price Intelligence Platform  
**Vị trí:** Senior Software Architect + Senior Data Engineer  
**Trạng thái:** Hoàn thành (Definition of Done Verified)  

---

## 1. Tổng quan Mục tiêu & Kết quả Đạt được

Phase 0 đã chuyển đổi thành công mô hình dữ liệu từ một **Price Tracker cá nhân đơn lẻ** (`devoidx/price-tracker`: Product → URL cố định → Price History) sang một **Nền tảng Market Price Intelligence** vững chắc:

```
dim_category (Category Hierarchy)
   └── dim_brand (Thương hiệu)
         └── dim_product_family (Dòng sản phẩm)
               └── dim_product (Sản phẩm chuẩn hóa)
                     └── dim_variant (Phiên bản cấu hình - SKU)
                           └── dim_condition (Tình trạng phần cứng N0-P0)
                                 └── dim_market_segment (Phân khúc giá thị trường chuẩn)
```

### Tiêu chí Bàn giao (Definition of Done Checklist):
- [x] **Mã nguồn cũ vẫn hoạt động 100%**: Backend endpoints cũ cho user (`/users`, `/alerts`, `/prices`), frontend SPA React tiếp tục chạy mượt mà không bị break.
- [x] **Product Taxonomy hoạt động toàn diện**: Phân cấp 6 tầng Category → Brand → Family → Product → Variant → Condition.
- [x] **Condition Taxonomy chuẩn hóa**: 9 mã tình trạng cố định từ New Sealed (`N0`) đến Parts Only (`P0`).
- [x] **Alembic Migration pass**: Khởi tạo hệ thống quản lý di chuyển CSDL tự động qua Alembic (`8a74f5fad03b_create_dim_taxonomy_tables`).
- [x] **Docker Windows chạy ổn định**: Toàn bộ stack chạy trên Docker Desktop Windows, Hot-reload và Container Healthcheck hoạt động.
- [x] **Docker Linux sẵn sàng**: Cấu hình độc lập môi trường, không phụ thuộc hardcode path.
- [x] **Seed Data hoàn thiện**: Đã nạp thành công iPhone 16 (128GB, 256GB), RTX 4060 Gaming X, Samsung DDR4 ECC 32GB 3200 và 9 Conditions.
- [x] **Taxonomy API hoạt động**: Đầy đủ các endpoint `GET /categories`, `GET /brands`, `GET /products`, `GET /products/{id}`, `GET /variants`, `GET /conditions`, `GET /market-segments`.
- [x] **Bộ Test tự động PASS 100%**: 13/13 tests PyTest vượt qua kiểm tra.
- [x] **Không có Crawler Marketplace / Deal Hunter sớm**: Giữ phạm vi Phase 0 thuần túy về Taxonomy & Foundation Data Model.

---

## 2. Refactor Cấu trúc Dự án (Controlled Modular Refactoring)

Để đảm bảo tính mở rộng cho các phase sau (Data Collection, Normalization, Deal Hunter) mà không làm vỡ các tính năng hiện hữu, backend được mở rộng thành modular architecture:

```
backend/
├── app/
│   ├── taxonomy/
│   │   ├── __init__.py
│   │   ├── models.py       # dim_category, dim_brand, dim_product, dim_variant, dim_condition, dim_market_segment, dim_source
│   │   ├── schemas.py      # Pydantic v2 schemas với ConfigDict
│   │   ├── conditions.py   # Định nghĩa chuẩn hóa 9 mã tình trạng (N0 - P0)
│   │   ├── attributes.py   # Category-specific attributes & Canonical Identity slug generator
│   │   └── seed.py         # Script nạp seed data chuẩn xác cho Phase 0
│   └── routers/
│       ├── __init__.py
│       └── taxonomy.py     # Endpoints RESTful cho Taxonomy & Market Segments
├── alembic/                # Quản lý Database Versioning & Migrations
├── tests/
│   ├── test_baseline.py    # 3 tests bảo vệ chức năng cũ (Health, Login Admin, Regex Scraper)
│   └── test_taxonomy.py    # 10 tests kiểm tra Taxonomy, Attributes, Canonical ID, API
├── main.py                 # FastAPI Application lifespan tự động migrate & seed
├── models.py               # Tái xuất (re-export) models để tương thích ngược hoàn toàn
└── requirements.txt        # Bổ sung pytest, pytest-asyncio
```

---

## 3. Condition Taxonomy (Phân loại Tình trạng Chuẩn hóa)

Hệ thống định nghĩa bảng mã tình trạng `dim_condition` gồm 9 cấp độ khép kín (Enforced Enum & Structured Database Rows), tuyệt đối không dùng chuỗi văn bản tự do:

| Mã | Tên tình trạng | Phân hạng (Grade) | Trọng số định giá (Weight) | Mô tả chi tiết |
| :---: | :--- | :---: | :---: | :--- |
| **N0** | **New Sealed** | `NEW` | **1.00** | Nguyên seal nhà sản xuất, chưa kích hoạt, mới 100% fullbox. |
| **N1** | **New Open Box** | `NEW` | **0.93** | Mới khui hộp kiểm tra, chưa qua sử dụng, đầy đủ phụ kiện zin. |
| **U0** | **Like New** | `USED` | **0.88** | Đẹp 99%, không trầy xước, pin cao, nguyên bản chưa qua sửa chữa. |
| **U1** | **Used Good** | `USED` | **0.80** | Hình thức 95-98%, xước dăm nhẹ không cấn móp, chức năng hoàn hảo. |
| **U2** | **Used Normal** | `USED` | **0.70** | Hình thức 90-95%, cấn nhẹ hoặc trầy nhiều chỗ, chức năng bình thường. |
| **U3** | **Used Fair** | `USED` | **0.60** | Hình thức xấu, có thể ám màn hình nhẹ, hao pin, vẫn dùng được. |
| **R0** | **Repaired** | `REPAIRED` | **0.55** | Đã qua sửa chữa / thay thế linh kiện (thay pin, ép kính, sửa nguồn). |
| **D0** | **Defective** | `DEFECTIVE` | **0.35** | Lỗi 1 hoặc nhiều tính năng (mất FaceID, hỏng cổng xuất hình, sập nguồn). |
| **P0** | **Parts Only** | `PARTS` | **0.15** | Xác máy, vỡ nát, chết nguồn, chỉ bán để rã linh kiện. |

---

## 4. Category-Specific Attributes: Thiết kế Hybrid Schema & Trade-Offs

### Thuộc tính đặc thù theo danh mục:
1. **Smartphone (Điện thoại)**:
   - *Bắt buộc*: `storage` (128GB, 256GB), `region` (VN/A, LL/A, ZA/A).
   - *Mở rộng*: `battery_health` (% pin), `warranty` (bảo hành hãng), `activation_status` (đã/chưa active), `repair_history` (lịch sử sửa chữa), `screen_condition` (tình trạng màn hình).
2. **GPU (Card màn hình)**:
   - *Bắt buộc*: `vram` (8GB GDDR6), `model_series` (Gaming X, Ventus, TUF).
   - *Mở rộng*: `warranty` (hạn bảo hành NPP), `mining_history` (trâu cày coin hay người dùng), `repair_history` (tem void zin), `fullbox` (còn hộp hay mất hộp).
3. **RAM (Bộ nhớ trong)**:
   - *Bắt buộc*: `ddr` (DDR4, DDR5), `capacity` (32GB, 16GB), `frequency` (3200MHz).
   - *Mở rộng*: `ecc` (ECC REG / Non-ECC), `rank` (2Rx4, 1Rx8), `chip` (Samsung B-die, Micron), `form_factor` (Desktop UDIMM / Server RDIMM / Laptop SODIMM).

### Phân tích Trade-Off Kiến trúc:
- **Lựa chọn**: **Normalized Core Columns + PostgreSQL JSONB Attributes**.
- **Ưu điểm**:
  - *Core Columns* (`sku`, `canonical_id`, `product_id`, `is_active`) cho phép đánh B-Tree Index, truy vấn JOIN tốc độ cao và đảm bảo tính toàn vẹn quan hệ (Referential Integrity).
  - *JSONB Attributes* (`variant_specs`, `base_specs`) cung cấp độ linh hoạt tối đa cho từng ngành hàng phần cứng khác nhau mà không cần ALTER TABLE hay tạo hàng chục bảng EAV (Entity-Attribute-Value) cồng kềnh với chi phí JOIN đắt đỏ.
  - Hỗ trợ đánh index GIN trên JSONB khi cần lọc sâu theo thuộc tính con ở các phase sau.

---

## 5. Chuẩn Định danh Canonical Identity (SKU Key)

Mỗi biến thể và phân khúc thị trường được cấp một chuỗi định danh duy nhất (Canonical ID) tuân thủ quy tắc chuẩn:

$$\text{Canonical ID} = \text{BRAND} \mid \text{PRODUCT} \mid \text{SPEC} \mid \text{SUB\_SPEC} \mid \text{CONDITION}$$

### Ví dụ thực tế:
- iPhone 16 128GB VN/A New Sealed: `APPLE|IPHONE16|128GB|VN-A|N0`
- iPhone 16 128GB VN/A Like New: `APPLE|IPHONE16|128GB|VN-A|U0`
- iPhone 16 256GB VN/A New Sealed: `APPLE|IPHONE16|256GB|VN-A|N0`
- RTX 4060 Gaming X 8GB New Sealed: `MSI|RTX4060|8GB|GAMING-X|N0`
- RTX 4060 Gaming X 8GB Used Good: `MSI|RTX4060|8GB|GAMING-X|U1`
- Samsung DDR4 ECC 32GB 3200 New Sealed: `SAMSUNG|DDR4-ECC|32GB-3200|2RX4|N0`
- Samsung DDR4 ECC 32GB 3200 Used Good: `SAMSUNG|DDR4-ECC|32GB-3200|2RX4|U1`

Chuỗi này là cơ sở quan trọng nhất để Phase 1 & Phase 2 gom cụm các tin đăng cào từ nhiều nguồn khác nhau về đúng một sản phẩm chuẩn để tính giá thị trường.

---

## 6. Kết quả Kiểm thử Tự động (Automated Test Execution)

Bộ test suite được cấu hình qua PyTest và chạy trực tiếp trong container:
```text
tests/test_baseline.py::test_health_endpoint PASSED           [  7%]
tests/test_baseline.py::test_clean_price_parser PASSED        [ 15%]
tests/test_baseline.py::test_admin_login_and_auth PASSED      [ 23%]
tests/test_taxonomy.py::test_condition_taxonomy PASSED        [ 30%]
tests/test_taxonomy.py::test_canonical_id_generation PASSED   [ 38%]
tests/test_taxonomy.py::test_category_schema_attributes PASSED[ 46%]
tests/test_taxonomy.py::test_api_get_categories PASSED        [ 53%]
tests/test_taxonomy.py::test_api_get_brands PASSED            [ 61%]
tests/test_taxonomy.py::test_api_get_products PASSED          [ 69%]
tests/test_taxonomy.py::test_api_get_product_detail PASSED    [ 76%]
tests/test_taxonomy.py::test_api_get_variants PASSED          [ 84%]
tests/test_taxonomy.py::test_api_get_conditions PASSED        [ 92%]
tests/test_taxonomy.py::test_api_get_market_segments PASSED   [100%]

======================= 13 passed in 1.63s =======================
```

---

## 7. Lộ trình Chuyển giao sang Phase 1

Phase 0 đã hoàn thành 100% mục tiêu nền móng. Hệ thống sẵn sàng cho **Phase 1: Raw Market Data Collection**:
1. Xây dựng module Collectors cho các sàn thương mại điện tử / diễn đàn (TheGioiDiDong, FPT Shop, CellphoneS, Shopee, VoZ, Facebook Groups).
2. Lưu trữ dữ liệu Raw Listing chưa qua xử lý vào bảng staging.
3. Liên kết URL cào dữ liệu với nguồn `dim_source`.
