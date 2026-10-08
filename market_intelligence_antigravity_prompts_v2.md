# Market Price Intelligence / AI Deal Hunter
## Bộ Prompt triển khai bằng Antigravity — Local Windows → Home Server Linux

> Mục tiêu: fork/custom một repo có sẵn để xây dựng hệ thống Market Price Intelligence. Hệ thống thu thập dữ liệu từ Goofish, Chợ Tốt, Facebook Marketplace, Facebook Groups + Comments; chuẩn hóa sản phẩm/tình trạng; xây dữ liệu giá thị trường; sau đó mới đánh giá listing mới và gửi Telegram khi có deal đáng mua.

---

# 0. Bối cảnh triển khai bắt buộc

## Môi trường phát triển

Development chính:

- Windows local
- VS Code + Antigravity
- Docker Desktop
- Docker Compose
- Git
- Browser có thể chạy headed khi cần debug/login
- Source code được chỉnh sửa, build, test tại local trước

Production:

- Home Server Linux chạy 24/7
- Docker Engine
- Docker Compose
- PostgreSQL chạy trong Docker
- Playwright/browser collector chạy trong Docker hoặc worker container phù hợp
- Browser profile, PostgreSQL data, logs và backup phải persistent
- Production không phụ thuộc vào Windows local đang bật

## Flow phát triển / deploy chuẩn

Flow phải được giữ thống nhất trong toàn project:

Windows Local
    ↓
Develop
    ↓
Docker build
    ↓
Automated tests
    ↓
Manual verification
    ↓
Git commit/push
    ↓
Home Server Linux
    ↓
git pull
    ↓
docker compose build
    ↓
database migration
    ↓
docker compose up -d
    ↓
healthcheck
    ↓
production running 24/7

Không copy source thủ công giữa Windows và Linux nếu không cần.

Git repository là source of truth cho code.

Production data KHÔNG lưu trong Git.

Các dữ liệu production sau phải nằm ngoài source code và phải persistent:

- PostgreSQL data
- browser profile/session
- collected raw data nếu lưu file
- backup
- logs cần giữ
- secrets

## Docker-first

Tất cả phase phải ưu tiên chạy bằng Docker từ đầu.

Không được thiết kế một hệ thống chỉ chạy được native Windows rồi về sau mới sửa để chạy Linux.

Yêu cầu:

- Cùng một Dockerfile/Compose architecture chạy được trên Windows Docker Desktop và Linux Docker Engine.
- Không hardcode Windows path như C:\...
- Không hardcode Linux user home.
- Dùng relative path, Docker named volumes hoặc environment variables.
- Không phụ thuộc vào shell script chỉ hoạt động trên một OS nếu không có phương án tương đương.

## Base repository

Base repository ưu tiên:

devoidx/price-tracker

Mục tiêu là FORK/CUSTOM, không viết lại toàn bộ từ đầu.

Giữ và tận dụng tối đa phần phù hợp:

- FastAPI
- PostgreSQL
- SQLAlchemy
- Playwright
- APScheduler
- React/Vite
- Recharts
- Docker
- Auth/Admin nếu dùng được
- Price history
- Error handling
- Existing notification/alert concepts

Tham khảo về kiến trúc/ý tưởng từ:

- PriceIntel
- PriceUniverse
- price-intelligence-api
- các repo price monitoring/intelligence phù hợp khác

Nhưng:

KHÔNG merge code bừa từ nhiều repository.

Chỉ có một codebase chính.

Nguyên tắc:

REUSE → EXTEND → REFACTOR → REPLACE

Chỉ REPLACE khi có lý do kỹ thuật rõ ràng.

## Nguyên tắc business quan trọng

AI KHÔNG được tự phát minh giá thị trường.

AI dùng để:

- hiểu title
- hiểu description
- phân loại sản phẩm
- extract attribute
- phân loại condition
- hiểu comment
- hỗ trợ matching

Giá thị trường phải được tính từ dữ liệu collected.

Không auto-buy.

Không auto-message seller.

Không bypass CAPTCHA.

Không bypass checkpoint.

Không fingerprint spoofing.

Không proxy rotation nhằm né anti-bot.

Nếu source chặn automation:
- dừng collector tương ứng
- log status
- yêu cầu manual intervention

---

# PHASE -1 — Repository Audit, Fork Strategy & Local-to-Server Baseline

```text
Bạn đang đóng vai trò Senior Software Architect + Senior DevOps Engineer.

Tôi muốn xây dựng Market Price Intelligence Platform bằng cách FORK/CUSTOM repository:

devoidx/price-tracker

Không được bắt đầu bằng cách viết lại project từ đầu.

Development:
- Windows local
- Docker Desktop
- VS Code + Antigravity

Production:
- Home Server Linux
- Docker Engine + Docker Compose
- chạy 24/7

Mục tiêu Phase -1:

1. Clone/fork và chạy được repo nguyên bản tại Windows local bằng Docker.
2. Audit architecture.
3. Xác định module nào KEEP / MODIFY / REPLACE / REMOVE / ADD.
4. Thiết kế flow development → Git → deploy Linux.
5. Chưa triển khai business feature mới lớn.

## 1. Audit repository

Scan toàn bộ source liên quan:

backend
frontend
docker
database models
scraper
scheduler
alerts
notifications
auth
configuration
tests

Không sửa lớn trước khi hiểu architecture.

Tạo:

docs/base-repository-audit.md

Trong đó có bảng:

Current Module | Decision | Reason | Target

Ví dụ:

FastAPI | KEEP
PostgreSQL | KEEP
React/Vite | KEEP
Playwright | KEEP/MODIFY
APScheduler | KEEP
Product model | REPLACE/MODIFY
Source model | MODIFY
Price History | MODIFY
Alert system | EXTEND
Frontend dashboard | EXTEND

## 2. Run baseline on Windows local

Phải chạy project nguyên bản bằng Docker Desktop.

Chuẩn hóa command:

docker compose build
docker compose up -d
docker compose ps
docker compose logs

Xác định:

- ports
- volumes
- environment variables
- database migration
- frontend/backend connectivity

Không yêu cầu cài PostgreSQL native trên Windows.

## 3. Cross-platform audit

Kiểm tra source có:

- hardcoded Windows paths
- hardcoded Linux paths
- OS-specific shell dependency
- browser path assumption
- localhost assumptions
- file permission assumptions

Tạo danh sách cần sửa để Docker image chạy được giống nhau trên:

Windows Docker Desktop
Linux Docker Engine

## 4. Production deployment baseline

Thiết kế deployment flow:

LOCAL WINDOWS
→ test
→ Git push

HOME SERVER LINUX
→ git pull
→ docker compose build
→ migration
→ docker compose up -d
→ healthcheck

Tạo:

docs/deployment-flow.md

Không dùng CI/CD phức tạp ở phase này.

Manual deploy qua Git là đủ.

## 5. Environment separation

Thiết kế:

.env.example
.env.local
.env.production

Không commit:

.env
API key
Telegram token
DB password
browser cookie/profile

Docker Compose có thể dùng:
- compose.yml
- compose.override.yml
- compose.prod.yml

hoặc mô hình tương đương đơn giản hơn.

Giải thích lựa chọn.

## 6. Persistent data design

Production phải có persistent storage cho:

- PostgreSQL
- browser profile
- backups
- optional logs
- application data

Production data không nằm trong repository.

Restart container/rebuild image không được mất data.

## 7. Git workflow

Thiết kế flow đơn giản:

main
feature branches nếu cần

Không over-engineer GitFlow.

Mục tiêu:

local Windows là nơi sửa source.

Linux server là nơi deploy, không chỉnh source trực tiếp trên production trừ emergency.

Nếu có emergency fix trên Linux, phải đưa thay đổi về repository ngay sau đó.

## 8. Baseline tests

Chạy các test hiện có.

Ghi lại:

- pass
- fail
- missing
- flaky

Không bắt đầu refactor lớn nếu baseline chưa rõ.

## Output

Tạo:

docs/phase-minus-1-report.md

Bao gồm:

- repo architecture
- modules KEEP/MODIFY/REPLACE
- local Windows run instruction
- Linux deployment strategy
- Docker volume strategy
- environment strategy
- baseline test results
- known technical debt
- migration plan sang Phase 0

Definition of Done:

- Repo base chạy được trên Windows bằng Docker.
- Kiến trúc đã được audit.
- Có kế hoạch custom rõ ràng.
- Có deployment flow Windows → Git → Linux.
- Có persistent-data strategy.
- Chưa triển khai Market Intelligence.
- Chưa rewrite toàn project.
```

---

# PHASE 0 — Foundation Refactor & Product Taxonomy

```text
Bạn đang đóng vai trò Senior Software Architect + Senior Data Engineer.

Phase -1 đã hoàn thành.

Base code là fork của devoidx/price-tracker.

Bây giờ triển khai Phase 0:

FOUNDATION REFACTOR + PRODUCT TAXONOMY.

Không tạo project mới.

Ưu tiên tận dụng code hiện có.

Development trên:
Windows + Docker Desktop.

Sau khi hoàn thành:
phải deploy test được lên Home Server Linux bằng Docker Compose.

## Mục tiêu

Thay đổi data model từ price tracker dạng:

Product
→ fixed URLs/sources
→ price history

sang foundation hỗ trợ:

Canonical Product
→ Product Variant
→ Condition
→ Market Segment
→ nhiều marketplace listing

Phase này chưa crawl marketplace.

## 1. Refactor có kiểm soát

Nếu repo hiện tại monolithic như:

models.py
schemas.py
scraper.py

thì refactor từng bước sang structure dễ mở rộng.

Ví dụ:

backend/app/
  models/
  schemas/
  services/
  taxonomy/
  collectors/
  normalization/
  market/
  notifications/
  routers/

Không refactor tất cả trong một commit lớn nếu không cần.

Trước refactor:
- bổ sung test bảo vệ behavior hiện tại nếu thiếu.

Sau refactor:
- test phải pass.

## 2. Product Taxonomy

Thiết kế:

Category
→ Brand
→ Product Family
→ Product
→ Variant
→ Condition

Ví dụ:

Apple
→ iPhone
→ iPhone 16
→ 128GB
→ VN/A
→ New Sealed

GPU:

RTX 4060
→ MSI
→ Gaming X
→ 8GB
→ Used Good

RAM:

Samsung
→ DDR4
→ ECC
→ 32GB
→ 3200
→ 2Rx4

## 3. Condition taxonomy

Tối thiểu:

N0 = New Sealed
N1 = New Open Box
U0 = Like New
U1 = Used Good
U2 = Used Normal
U3 = Used Fair
R0 = Repaired
D0 = Defective
P0 = Parts Only

Condition phải là structured value.

Không dùng text tự do làm condition chính.

## 4. Category-specific attributes

Smartphone:

storage
region
battery_health
warranty
activation_status
repair_history
screen_condition

GPU:

brand
model
VRAM
warranty
mining_history
repair_history
fullbox

RAM:

brand
DDR
capacity
ECC
frequency
rank
chip
desktop/laptop/server

Thiết kế flexible schema.

Có thể dùng:
normalized core columns
+
JSONB attributes

nhưng phải giải thích trade-off.

## 5. Canonical identity

Thiết kế:

product_id
variant_id
market_segment_id

Ví dụ:

APPLE|IPHONE16|128GB|VN-A|N0

Market segment phải đủ chính xác để sau này tính market price.

## 6. Database

Tận dụng migration system hiện có nếu có.

Nếu chưa có thì chuẩn hóa Alembic.

Tables tối thiểu:

dim_category
dim_brand
dim_product_family
dim_product
dim_variant
dim_condition
dim_source

Không phá dữ liệu cũ nếu có thể migrate.

Nếu cần breaking migration:
document rõ.

## 7. Seed data

Tạo:

iPhone 16 128GB
iPhone 16 256GB
RTX 4060
Samsung DDR4 ECC 32GB 3200

## 8. API

Extend existing FastAPI.

Không tạo backend thứ hai.

API:

GET /categories
GET /brands
GET /products
GET /products/{id}
GET /variants
GET /conditions
GET /market-segments

## 9. Docker local validation

Trên Windows:

docker compose build
docker compose up -d

Migration:

alembic upgrade head
hoặc command tương đương trong container.

Test:

pytest

Frontend/backend hiện hữu không được bị phá nếu vẫn cần.

## 10. Linux deployment verification

Sau khi local pass:

Git push.

Trên Home Server Linux:

git pull

docker compose build

run migration

docker compose up -d

verify health.

Không copy database local lên production.

Production DB riêng.

## Documentation

Tạo:

docs/phase-0-report.md

docs/local-development.md

docs/linux-deployment.md

Definition of Done:

- Existing repo vẫn chạy.
- Taxonomy hoạt động.
- Migration pass.
- Docker Windows chạy được.
- Docker Linux chạy được.
- Seed data hoạt động.
- API hoạt động.
- Không có crawler marketplace.
- Không có Deal Hunter.
```

---

# PHASE 1 — Raw Market Data Collection

```text
Bạn đang đóng vai trò Senior Python Engineer + Data Collection Engineer.

Phase 0 hoàn thành.

Base repository đã có:
- FastAPI
- PostgreSQL
- Playwright infrastructure
- Scheduler
- Docker
- Product Taxonomy

Bây giờ triển khai Phase 1:

RAW MARKET DATA COLLECTION.

Nguồn:

1. Goofish / 闲鱼
2. Chợ Tốt
3. Facebook Marketplace
4. Facebook Groups
5. Facebook Group comments

## Nguyên tắc quan trọng

Không tạo crawler framework thứ hai nếu scraper infrastructure hiện tại có thể extend.

Trước khi code:

review:
- existing scraper.py
- scheduler.py
- Source model
- price history
- error handling

Sau đó chọn:

EXTEND
hoặc
REFACTOR

Phải giải thích.

## Collector architecture

Target:

collectors/
  base.py
  goofish.py
  chotot.py
  facebook_marketplace.py
  facebook_group.py

Mỗi collector implement contract chung.

Ví dụ:

fetch()
parse()
persist()
health()

## Browser strategy

Development local Windows:

- cho phép headed browser để debug
- browser profile nằm trong local development volume/path
- không commit browser profile

Production Linux:

- ưu tiên headless nếu hoạt động ổn
- production browser profile riêng
- persistent volume
- không copy cookie từ Git

Có quy trình manual login riêng nếu source yêu cầu login.

## Anti-bot

Không:

- bypass CAPTCHA
- bypass checkpoint
- proxy rotate nhằm né detection
- fake fingerprint
- auto login spam

Nếu AUTH_REQUIRED / CHECKPOINT:

collector status phải chuyển sang trạng thái tương ứng và dừng.

## Tần suất

Configurable.

Default:

Goofish: 10 phút
Chợ Tốt: 30–60 phút
Marketplace: ~60 phút
FB Groups: 60–120 phút

Facebook chỉ đọc gần nhất.

FB group:
20–30 post gần nhất.

Marketplace:
20–30 listing gần nhất / keyword.

Comments:
giới hạn hợp lý.

## Raw Listing

Tạo hoặc migrate schema:

fact_raw_listing

id
source_id
source_listing_id
url

raw_title
raw_description
raw_price_text
raw_currency

seller_name_raw
seller_id_raw
location_raw

published_at
first_seen_at
last_seen_at

raw_metadata JSONB

crawl_status

created_at
updated_at

Unique:
source + source_listing_id

## Price snapshot

Không overwrite history.

fact_listing_price_snapshot:

listing_id
price_raw
currency
captured_at

## Comments

fact_raw_comment:

source_comment_id
listing_id
author
raw_text
created_at_source
first_seen_at

## Incremental crawling

Newest-first.

Stop khi gặp record đã biết khi logic platform cho phép.

Không crawl lại toàn lịch sử mỗi vòng.

## Deduplication

Nếu item đã tồn tại:

update last_seen_at

Nếu giá đổi:
tạo snapshot.

Nếu description đổi:
lưu history hoặc metadata phù hợp.

## Raw preservation

Không sửa raw content.

Normalization là Phase 2.

## Scheduler

Tận dụng scheduler hiện tại.

Production restart phải không tạo duplicate jobs.

Job config không hardcode.

## Collector Health

API:

GET /collectors/status

Fields:

source
status
last_start
last_success
last_error
items_scanned
items_new
auth_status

## Windows development tests

Parser test dùng fixture/mocked HTML/JSON.

Không bắt test unit phụ thuộc internet.

Có integration test tùy chọn.

## Linux deploy

Sau khi local pass:

git push

server:
git pull
docker compose build
migration
docker compose up -d

Verify:

collectors/status
logs
DB writes
browser profile persistence

## Output

docs/phase-1-report.md

Definition of Done:

- Raw collector architecture hoạt động.
- Data lưu PostgreSQL.
- Không duplicate.
- Có price snapshot.
- Có comment.
- Scheduler chạy.
- Browser profile local/prod tách biệt.
- Windows Docker pass.
- Linux Docker pass.
- Chưa AI normalize.
- Chưa Market Engine.
```

---

# PHASE 2 — AI Product Normalization & Classification

```text
Bạn đang đóng vai trò Senior AI Engineer + Data Engineer.

Phase 1 đã có raw market data.

Bây giờ triển khai:

AI PRODUCT NORMALIZATION & CLASSIFICATION.

Development:
Windows local.

Production:
Home Server Linux.

AI provider có thể là external API hoặc local model trong tương lai.

Không hardcode provider.

## Nguyên tắc

AI không tự tạo market price.

AI chỉ:

- identify product
- extract attributes
- match taxonomy
- classify condition
- detect invalid/fake pricing
- classify comments
- assist semantic duplicate detection

## Pipeline ưu tiên

deterministic rules
→ dictionary
→ regex
→ fuzzy match
→ AI

Không gửi mọi item vào model mạnh.

## AI Provider abstraction

Tạo interface:

AIProvider

Implement provider adapters độc lập.

Config qua env.

Không commit API keys.

Local Windows và Linux production dùng cùng abstraction nhưng key/config riêng.

## Structured output

LLM output phải validate bằng Pydantic.

Không lưu free-text response làm source of truth.

## fact_normalized_listing

raw_listing_id

product_id
variant_id
condition_id
market_segment_id

normalized_price
currency

normalized_attributes JSONB

classification

ai_confidence
normalization_version
normalized_at
manual_review_required

## Classification

SELL
BUY
WANTED
SERVICE
ACCESSORY
PARTS
SPAM
UNKNOWN

## Product aliases

Ví dụ:

iphone16
ip16
苹果16

→ same canonical product

Alias dictionary phải maintainable.

## Condition

Map về taxonomy Phase 0.

Không tự đoán nếu thiếu dữ liệu.

Confidence thấp:
manual_review_required = true.

## Price parsing

Parse:

18tr5
18.5tr
18500k
1.85万
¥5000

Không mất raw value.

## Invalid price

Detect:

1đ
1234đ
giá inbox
deposit only
installment teaser
free
placeholder

Có:

price_valid
price_validity_reason

## Comments

Classify:

NEGOTIATION
SELLER_PRICE
COMPETING_OFFER
SOLD_SIGNAL
PRICE_REFERENCE
WTB
NOISE

## Versioning

normalization_version

Bắt buộc để reprocess data sau này.

## Review queue

API:

GET /normalization/review

Manual correction phải lưu audit.

Không sửa raw source.

## Local development

Có mock AI provider để chạy test không tốn API.

Unit tests không phụ thuộc AI internet.

Integration tests có flag riêng.

## Production deploy

Config AI key bằng .env.production trên Linux.

Không copy .env.local lên server.

Verify:

normalization worker
DB
review API
metrics

## Metrics

rule_only
ai_processed
failed
review_required
avg_confidence
tokens/cost nếu provider có

## Output

docs/phase-2-report.md

Definition of Done:

- Product normalization hoạt động.
- Condition mapping hoạt động.
- AI provider abstraction hoạt động.
- Invalid price filtering hoạt động.
- Comment classification hoạt động.
- Windows Docker pass.
- Linux deploy pass.
- Chưa Market Price Engine.
```

---

# PHASE 3 — Market Price Intelligence Engine

```text
Bạn đang đóng vai trò Senior Data Scientist + Senior Data Engineer.

Đây là CORE BUSINESS phase.

Input đã normalized.

Mục tiêu:

xây bộ dữ liệu phản ánh:

"Thị trường hiện đang chấp nhận mức giá nào cho từng product / variant / condition?"

AI KHÔNG được tự đoán giá.

Giá phải tính từ collected data.

## Market Segment

Mọi statistic tính trên market_segment_id.

Ví dụ:

iPhone 16
128GB
VN/A
New Sealed

Không trộn:

256GB
Used
Defective
Open Box

## Sources

- Chợ Tốt
- Facebook Marketplace
- Facebook Groups
- Goofish

Goofish phải convert thành landed cost VN trước khi so sánh.

## Goofish landed cost

landed_cost =
product_price_cny * exchange_rate
+ china_shipping
+ buying_fee
+ china_to_vietnam_shipping
+ risk_buffer

Tất cả configurable.

## Cleaning

Exclude khỏi market calculation nếu:

fake price
deposit-only
duplicate
wrong condition
low confidence
parts-only khác segment
obvious outlier

Không xóa raw/normalized record.

Lưu exclusion reason.

## Statistics

Theo segment:

sample_count

min
p05
p10
p25
median
p75
p90
p95
max

Mean chỉ supplemental.

## Per-source statistics

Chợ Tốt
Marketplace
FB Groups
Goofish landed

Tính riêng:

sample
P25
Median
P75

## Time windows

24h
7d
30d
90d

## fact_market_daily

date
market_segment_id
sample_count

p05
p10
p25
median
p75
p90
p95

fair_price
quick_sell_price
low_market_price
high_market_price

market_confidence
liquidity_score

trend_7d
trend_30d

calculation_version

## Fair Price

Deterministic.

Ví dụ weighted median.

Không dùng LLM-generated number.

## Quick Sell Price

Phase đầu:

conservative percentile.

Sau khi đủ data:

ước lượng dựa trên:

price
→ time_to_disappear

Nhưng không mặc định disappearance = sold.

## Sold signal

confirmed:
seller says sold
platform sold status

probable:
sold comment
price reduction + disappearance

unknown:
listing disappears

Tạo sold_confidence.

## Liquidity

Dựa trên:

listing turnover
new listing frequency
time_to_disappear
sold signals

Output 0–100.

## Market Confidence

Dựa trên:

sample size
source diversity
normalization confidence
recency
condition match

Không gọi confidence cao khi sample nhỏ.

## Market zones

VERY_CHEAP
CHEAP
NORMAL
EXPENSIVE
VERY_EXPENSIVE

Starting:

< P10 VERY_CHEAP
P10–P25 CHEAP
P25–P75 NORMAL
P75–P90 EXPENSIVE
> P90 VERY_EXPENSIVE

Configurable.

## API

GET /market/{segment_id}
GET /market/{segment_id}/history
GET /market/{segment_id}/sources
GET /market/search

## Explainability

Response phải có:

data_period
included_samples
excluded_samples
source_count
calculation_version

## Local Windows

Dùng seed + imported fixture data để test Market Engine.

Không phụ thuộc crawler live để chạy unit tests.

## Production Linux

Sau deploy:

recalculate market facts từ production data.

Không copy local market statistics vào production.

## Tests

percentile
outlier
small sample
source diversity
stale data
Goofish landed cost
trend
quick sell
confidence

## Output

docs/phase-3-report.md

Definition of Done:

Query:

iPhone 16 128GB New Sealed

trả:

P10
P25
Median
P75
P90
Fair
Quick Sell
Confidence
Liquidity
Trend
Source Comparison

Windows test pass.
Linux production calculation pass.

Chưa Deal Hunter.
```

---

# PHASE 4 — Extend Existing Dashboard

```text
Bạn đang đóng vai trò Senior Full Stack Engineer + Data Visualization Engineer.

Không tạo frontend mới nếu React/Vite hiện tại có thể extend.

Tận dụng:

React/Vite
existing auth
existing layout
existing chart library
existing API client

Mục tiêu:

Market Intelligence Dashboard.

## Screen 1 — Market Overview

Filter:

Category
Brand
Product
Variant
Condition

Show:

Sample
P10
P25
Median
P75
P90
Fair Price
Quick Sell Price
Confidence
Liquidity
Trend

## Screen 2 — Price Distribution

Histogram:

price bucket
listing count

Filter source.

## Screen 3 — Source Comparison

Table:

Source
Samples
P25
Median
P75

Bar chart median by source.

## Screen 4 — Trend

Line:

Date
P25
Median
P75
Quick Sell

7d / 30d / 90d.

## Screen 5 — Raw Listings

Table:

Source
Title
Normalized product
Condition
Price
First seen
Last seen
Status
Confidence

Link original listing.

Pagination bắt buộc.

## Screen 6 — Product Explorer

Category
→ Brand
→ Model
→ Variant
→ Condition

## Screen 7 — Data Quality / Operations

normalization failures
review queue
invalid prices
outliers
collector last scan
market confidence

## Development

Chạy full stack trên Windows Docker Desktop.

Không yêu cầu npm/node native ngoài container nếu architecture hỗ trợ.

Nếu frontend dev hot reload cần native workflow:
document rõ nhưng production vẫn Docker.

## Production

Build production frontend image.

Deploy Linux bằng:

git pull
docker compose build
docker compose up -d

Không copy dist bằng tay nếu không cần.

## Output

docs/phase-4-report.md

Definition of Done:

Search:

iPhone 16 / 128GB / New Sealed

và nhìn được:

- current market
- price distribution
- sources
- trend
- quick sell
- raw evidence

Windows Docker pass.
Linux production pass.

Chưa Telegram Deal Hunter.
```

---

# PHASE 5 — AI Deal Hunter + Telegram

```text
Bạn đang đóng vai trò Senior AI Engineer + Marketplace Analytics Engineer.

Market Intelligence Engine đã đủ tin cậy.

Bây giờ triển khai:

NEW LISTING APPRAISAL + TELEGRAM.

Không tạo benchmark bằng LLM.

## Flow

NEW LISTING
→ normalize
→ identify market_segment
→ Market API query
→ deterministic math
→ condition/risk analysis
→ AI explanation if needed
→ BUY / WATCH / SKIP
→ Telegram nếu đạt threshold

## Market inputs

P10
P25
Median
Fair Price
Quick Sell
Confidence
Liquidity

## Calculation

discount_vs_median
discount_vs_p25
discount_vs_quick_sell

expected_profit =
quick_sell_price - acquisition_cost

ROI =
expected_profit / acquisition_cost

Goofish:
acquisition_cost = landed cost.

VN sources:
asking price + configured cost buffer.

## Rule engine first

BUY nếu thỏa:

market_confidence
min_profit
min_roi
acceptable condition

Threshold configurable per category.

Không hardcode mọi category chung một mức.

## AI Appraisal

Chỉ gọi deep AI cho candidate có tiềm năng.

AI nhận:

listing
attributes
condition
market data
comments
images nếu có

Output structured:

decision
confidence
market_position
asking_price
quick_sell_price
expected_profit
roi
risks
reason

AI không được sửa market numbers.

## Facebook comments

Nếu seller:

"12tr2 lấy nhanh"

có thể tạo effective seller price.

Nếu user khác:

"em có con này 11tr8"

có thể tạo candidate phụ nếu đủ thông tin.

## Telegram

Extend notification/alert infrastructure hiện có nếu phù hợp.

Không tạo hệ thống notification song song không cần thiết.

Thêm:

TelegramNotificationProvider

Message:

🚨 DEAL MỚI

Product
Variant
Condition

Source
Asking Price

P10
P25
Median
Quick Sell

Expected Profit
ROI

Confidence
Liquidity

Reason
Risk
URL

## Dedup

Không alert lại cùng listing.

Alert lại nếu:

significant price drop
new effective price
important condition change

## Local development

Dùng Telegram test bot/chat riêng nếu cần.

Không commit token.

Mock notification trong unit tests.

## Linux production

Token production nằm trong .env.production.

Verify:

Telegram connectivity
alert worker
dedup
logs

## Output

docs/phase-5-report.md

Definition of Done:

Listing mới:

normalize
→ market lookup
→ calculation
→ appraisal
→ Telegram khi đáng mua

Windows test pass.
Linux deploy pass.

Không auto-buy.
Không auto-message seller.
```

---

# PHASE 6 — Production Hardening & Operations

```text
Bạn đang đóng vai trò Senior DevOps Engineer + SRE.

Hệ thống chạy production trên Home Server Linux 24/7.

Development vẫn thực hiện trên Windows local.

Mục tiêu:

production ổn định, update dễ, không mất data.

## Docker Compose production

Tách rõ:

development config
production config

Production services có thể gồm:

frontend
backend
worker/scheduler
collector
postgres

Không dùng Kubernetes.

Redis chỉ thêm nếu thật sự cần.

## Restart policy

restart: unless-stopped

Collector lỗi không làm toàn stack chết.

## Persistent volumes

Bắt buộc:

PostgreSQL
browser profiles
backup
application data

Không bind source code production vào container nếu không cần.

## Database migration deploy flow

Chuẩn hóa deploy:

git pull

docker compose build

docker compose run --rm backend alembic upgrade head

docker compose up -d

healthcheck

Có rollback guidance.

## Update flow

Mọi update:

1. Code trên Windows.
2. Docker local test.
3. pytest.
4. UI verification.
5. Git push.
6. Server git pull.
7. Build.
8. Migration.
9. Restart.
10. Health check.
11. Log verification.

Không sửa production trực tiếp như workflow bình thường.

## Backup

PostgreSQL backup tự động.

Retention configurable.

Ví dụ:

7 daily
4 weekly

Có restore test/document.

## Browser session

Production profile riêng.

Nếu expired:

AUTH_REQUIRED.

Có documented manual re-login procedure.

Không tự spam login.

## Job locking

Không chạy duplicate job khi previous run chưa xong.

Có:

lock
timeout
limited retry

## Health

API health:

backend
database
scheduler
collectors
AI provider
Telegram

## Error notification

Telegram system alerts:

collector failure
AUTH_REQUIRED
database error
disk > threshold
backup fail
market job fail

Tách khỏi deal notifications nếu có thể.

## Disk

Monitor:

DB
logs
browser cache
backup

Log rotation.

## Security

Secrets chỉ ở server/local .env.

Không commit.

Chỉ expose port cần thiết.

Dashboard nội bộ có auth.

Nếu chỉ dùng LAN:
document firewall/port strategy.

## Server reboot

Sau reboot:

Docker tự start.
Services tự start.
Scheduler không duplicate.
Browser profile còn.
DB còn.

## Monitoring nhẹ

Không bắt buộc Prometheus/Grafana.

Ưu tiên lightweight status dashboard/API trước.

## Production docs

Tạo:

docs/production.md
docs/backup-restore.md
docs/deployment-runbook.md
docs/troubleshooting.md

## Definition of Done

- Windows local dev flow ổn định.
- Linux deploy flow ổn định.
- Rebuild không mất DB.
- Rebuild không mất browser profile.
- Server reboot tự hồi phục.
- Backup hoạt động.
- Restore có tài liệu.
- Health status đầy đủ.
- Error Telegram hoạt động.
```

---

# Deployment Flow Chuẩn Dùng Xuyên Suốt Dự Án

## Local Windows

```bash
git pull

docker compose build
docker compose up -d

docker compose ps
docker compose logs

docker compose exec backend pytest
```

Nếu migration mới:

```bash
docker compose exec backend alembic upgrade head
```

Sau khi verify:

```text
commit
push
```

## Home Server Linux

```bash
cd /path/to/project

git pull

docker compose build

docker compose run --rm backend alembic upgrade head

docker compose up -d

docker compose ps

docker compose logs --tail=200
```

Sau đó verify health endpoint và dashboard.

## Nguyên tắc dữ liệu

LOCAL DB:
chỉ dùng development/test.

PRODUCTION DB:
chỉ nằm ở Home Server.

Không đồng bộ production DB về local bằng Git.

Nếu cần debug bằng production data:
export snapshot có kiểm soát và sanitize nếu cần.

Browser profile:

Local và Production tách biệt.

Không dùng chung một profile qua Git.

---

# Thứ tự triển khai

Phase -1
→ Repo Audit + Docker baseline

Phase 0
→ Foundation + Taxonomy

Phase 1
→ Raw Data Collection

Phase 2
→ AI Normalization

Phase 3
→ Market Intelligence Engine

STOP & REVIEW DATA QUALITY

Phase 4
→ Dashboard

Phase 5
→ Deal Hunter + Telegram

Phase 6
→ Production Hardening

---

# Gate quan trọng nhất

Không triển khai Phase 5 nếu hệ thống chưa trả lời đáng tin câu hỏi:

“iPhone 16 128GB New Sealed hiện thị trường đang bao nhiêu?”

với dữ liệu:

- sample count
- source count
- P10
- P25
- Median
- P75
- P90
- Fair Price
- Quick Sell Price
- Market Confidence
- Liquidity
- 7d/30d trend
- raw listings tham chiếu

Nếu chưa trả lời tốt:

quay lại cải thiện:

Taxonomy
→ Normalization
→ Data Quality
→ Market Engine

Không dùng AI để che lấp dữ liệu kém chất lượng.
