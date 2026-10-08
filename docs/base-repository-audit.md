# Baseline Repository Audit: `devoidx/price-tracker`

## 1. Tong quan kien truc goc (Base Repository Architecture)

Repository `devoidx/price-tracker` la mot he thong theo doi gia san pham ca nhan (Personal Product Price Tracker) duoc thiet ke theo mo hinh Monolithic micro-services don gian:

```
[ Frontend: React/Vite + Nginx (Port 3001) ]
                  | (HTTP API)
                  v
[ Backend: FastAPI + Playwright + APScheduler (Port 8000) ]
                  | (SQLAlchemy / asyncpg / psycopg2)
                  v
[ Database: PostgreSQL 16 (Port 5432) ]
```

### Chi tiet thanh phan:
1. **Backend (`/backend`)**:
   - **Framework**: FastAPI (`main.py`) quan ly 11 routers RESTful (users, products, prices, alerts, settings, selectors, firefox_sites, push, messages, categories).
   - **ORM & DB Connection**: SQLAlchemy (`models.py`, `database.py`) ke hop voi `psycopg2-binary` cho sync queries va `asyncpg` trong dependency stack.
   - **Web Scraper (`scraper.py`)**: Playwright Python (`sync_playwright`) chay headless Chromium / Firefox quan ly qua context browser dynamic. Chiet xuat gia bang Regex va CSS selectors (`clean_price`).
   - **Scheduler (`scheduler.py`)**: APScheduler `BackgroundScheduler` chay in-process cung FastAPI app lifespan, luu job state vao PostgreSQL qua `SQLAlchemyJobStore`.
   - **Alerts & Notifications (`alerts.py`, `notifications.py`, `push_notifications.py`)**: Kiem tra nguong gia (all_time_low, price_drop, price_decreased) co thoi gian cooldown 24h, gui Email (SMTP/Gmail) va Web Push (pywebpush / VAPID).
   - **Authentication (`auth.py`)**: Password hashing qua `bcrypt` / `passlib` va JWT Bearer token authentication qua `python-jose`.

2. **Frontend (`/frontend`)**:
   - **Framework**: React 18 + Vite (`package.json`).
   - **Routing & State**: React Router DOM, Axios (`api.js`) de call FastAPI backend.
   - **UI Component**: Lucide React icons, Recharts cho bieu do lich su gia.
   - **Production Server**: Multi-stage Docker build voi `nginx:alpine` phuc vu SPA statics va proxy routing.

3. **Database (`backend/db/init.sql`)**:
   - PostgreSQL schema gom cac bang: `users`, `products`, `sources`, `price_history`, `alerts`, `settings`, `known_selectors`, `firefox_sites`, `messages`, `exchange_rates`, `push_subscriptions`, `categories`, `product_categories`.
   - Seed data co san user default `admin` (password: `changeme`).

---

## 2. Bang quyet dinh Audit Module (Module Decision Matrix)

| Current Module | Decision | Reason | Target for Market Intelligence |
| :--- | :--- | :--- | :--- |
| **FastAPI Core** | **KEEP** | Hieu nang cao, ho tro async/await toan dien, tu dong sinh OpenAPI/Swagger docs, de dang mo rộng REST/GraphQL APIs. | Giu nguyen framework core; bo sung middleware logging, rate limiting va multi-tenant context. |
| **PostgreSQL 16** | **KEEP** | Co so du lieu quan he vung chac, ho tro quan ly gia ca theo thoi gian, index hieu qua va dam bao tinh ACID. | Giu nguyen engine DB; mo rong schema cho thi truong (SKU, Brand, Competitor, Retailer, Category Hierarchy). |
| **React / Vite + Nginx** | **KEEP** | React + Vite cho toc do dev build sieu nhanh, Nginx image sieu nhe cho production runtime. | Giu nguyen stack; mo rong UI Dashboard chuyen nghiep voi ma tran so sanh doi thu va analytics chart. |
| **Playwright Python** | **KEEP / MODIFY** | Cong cu scrape dynamic web hien dai nhat, xu ly tot JavaScript rendering, anti-bot bypass tot hon requests/BS4. | Giu Playwright; MODIFY cach khoi tao context (chuyen sang async/pool, ho tro Rotating Proxy, User-Agent rotation, Cookie persistence). |
| **APScheduler** | **KEEP / MODIFY** | Dinh ky scrape hieu qua trong quy mo nho/vừa. Luu job vao Postgres giup hoan tat job sau khi restart container. | MODIFY cach khoi tao de tranh duplicate job execution khi horizontally scale backend container. Huong toi Celery/Redis khi scale lon. |
| **Product Model** | **MODIFY** | Model hien tai chi luu ten san pham ca nhan (`user_id`, `name`), khong co thong tin thi truong. | MODIFY thanh **Market Product Model**: Bo sung SKU, EAN/UPC, Brand, Master Category, Specifications, Target Base Price. |
| **Source Model** | **MODIFY** | Hien tai chi luu URL va CSS selector don gian cho ca nhan. | MODIFY thanh **Competitor / Retailer Source**: Luu Retailer ID, Proxy Profile, Dynamic Parsing Rule, Anti-bot Profile, Scrape Priority. |
| **Price History Model**| **MODIFY** | Chi luu `price`, `currency`, `scraped_at`, `error`. | MODIFY de ho tro normalized price (quy doi theo ty gia chuan), Stock status (In Stock/Out of Stock), Discount %, Seller Name, Shipping fee. |
| **Alert System** | **EXTEND** | Hien tai chi ho tro email SMTP va Web Push don gian cho ca nhan. | EXTEND ho tro Telegram Bot / Discord Webhook notifications, Price Spike/Drop Anomaly alerts, Volatility alerts. |
| **Frontend Dashboard** | **EXTEND** | Dashboard hien tai dang hien thi dang card san pham ca nhan don dieu. | EXTEND thanh Market Price Intelligence Portal: Ma tran gia doi thu, Bieu do bien dong gia thi truong, Filtering theo Brand/Category, Export CSV/Excel. |
| **Database Migrations** | **ADD** | Project hien tai chi dung `init.sql` tho, khong co tool migration versioning (Alembic). | ADD **Alembic Database Migrations** de quan ly schema versioning an toan va khong lam mat du lieu khi deploy production. |

---

## 3. Phanthich Cross-Platform & Anti-Patterns (Windows Local vs Linux Server)

Khi audit codebase, cac diem can chu y de dam bao Docker image va source code chay dong nhat tren ca **Windows Docker Desktop** va **Linux Docker Engine**:

1. **Path Assumption & File Delimiters**:
   - Web scraper hien tai trong `scraper.py` va file paths khong hardcode Windows path (`C:\...`), tuy nhien `docker-compose.yml` dung relative mount `./backend:/app`. Trên Windows Docker Desktop, mount volume nay qua WSL2/virtiofs, tren Linux dung native bind mount.
   - Dam bao tat ca path trong Python luon dung `os.path` hoac `pathlib.Path` voi slash `/`.

2. **Browser Binary Location & Playwright Dependencies**:
   - Container backend dung image base `mcr.microsoft.com/playwright/python:v1.47.0-jammy`. Image nay da dong goi san cac trinh duyệt Chromium va Firefox trong moi truong Linux Ubuntu.
   - **Luu y**: Khong chay Playwright install native tren host Windows, chi dung binary trong Docker container.

3. **CORS & Localhost Binding**:
   - Trong `backend/main.py`:
     ```python
     allow_origins=["http://localhost:3000", "http://localhost:3001", "https://pt.zeolite"]
     ```
   - Chú ý: Khi deploy Linux Home Server, frontend va backend co the truy cap qua IP LAN (vd: `http://192.168.1.x:3001`) hoac domain noi bo. Can cho phep CORS linh hoat qua bien quyet dinh trong `.env` (`CORS_ORIGINS`).

4. **Timezone Configuration**:
   - Trong `scraper.py`, timezone duoc set cung la `Europe/London`.
   - Can chuuan hoa Timezone qua bien `.env` (`TZ=Asia/Ho_Chi_Minh` hoac `UTC`) de du lieu scraper va DB timestamp thong nhat giua Windows va Linux.

5. **Container Service Healthcheck & Startup Dependency**:
   - Trong `docker-compose.yml`, backend phu thuộc vao `db` qua `condition: service_healthy`.
   - Healthcheck `pg_isready -U tracker -d pricetracker` hoat dong tot tren ca Windows va Linux Docker Engine.
