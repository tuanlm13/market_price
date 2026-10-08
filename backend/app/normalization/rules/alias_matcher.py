import re
import difflib
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session
from app.taxonomy.models import DimProduct, DimVariant
from app.normalization.models import DimProductAlias
from app.normalization.rules.classification_rules import classify_listing_intent

# Static maintainable alias seed dictionary for bootstrap / offline speed
STATIC_ALIASES: Dict[str, str] = {
    # iPhone 16 Pro Max
    "iphone 16 pro max": "iphone-16-pro-max",
    "iphone 16 prm": "iphone-16-pro-max",
    "iphone16 pro max": "iphone-16-pro-max",
    "ip16 pro max": "iphone-16-pro-max",
    "ip16 prm": "iphone-16-pro-max",
    "ip 16 prm": "iphone-16-pro-max",
    "苹果16 pro max": "iphone-16-pro-max",
    "apple iphone 16 pro max": "iphone-16-pro-max",

    # iPhone 16 Pro
    "iphone 16 pro": "iphone-16-pro",
    "iphone16 pro": "iphone-16-pro",
    "iphone 16pro": "iphone-16-pro",
    "ip 16 pro": "iphone-16-pro",
    "ip16 pro": "iphone-16-pro",
    "ip16pro": "iphone-16-pro",
    "apple iphone 16 pro": "iphone-16-pro",

    # iPhone 16 Plus
    "iphone 16 plus": "iphone-16-plus",
    "iphone16 plus": "iphone-16-plus",
    "iphone 16plus": "iphone-16-plus",
    "ip 16 plus": "iphone-16-plus",
    "ip16 plus": "iphone-16-plus",
    "ip16plus": "iphone-16-plus",
    "16 plus": "iphone-16-plus",
    "16plus": "iphone-16-plus",
    "apple iphone 16 plus": "iphone-16-plus",

    # iPhone 16 (Standard / Base)
    "iphone 16": "iphone-16",
    "iphone16": "iphone-16",
    "ip 16": "iphone-16",
    "ip16": "iphone-16",
    "苹果16": "iphone-16",
    "apple iphone 16": "iphone-16",

    # RAM Generations
    "ram ddr5": "ram-ddr5",
    "ddr5 ram": "ram-ddr5",
    "ram laptop ddr5": "ram-ddr5",
    "ram pc ddr5": "ram-ddr5",
    "samsung ddr4 ecc server ram": "samsung-ddr4-ecc-server-ram",
    "samsung ddr4 ecc": "samsung-ddr4-ecc-server-ram",
    "ram ddr4": "ram-ddr4",
    "ddr4 ram": "ram-ddr4",
    "ram ddr3": "ram-ddr3",
    "ddr3 ram": "ram-ddr3",

    # RTX 4060
    "rtx 4060": "geforce-rtx-4060",
    "rtx4060": "geforce-rtx-4060",
    "geforce rtx 4060": "geforce-rtx-4060",
    "nvidia rtx 4060": "geforce-rtx-4060",

    # Sony WH-1000XM5
    "wh-1000xm5": "sony-wh-1000xm5",
    "wh1000xm5": "sony-wh-1000xm5",
    "sony xm5": "sony-wh-1000xm5",
    "sony wh-1000xm5": "sony-wh-1000xm5",
}

STORAGE_PATTERNS = [
    (r"\b128\s*gb\b|\b128g\b", "128GB"),
    (r"\b256\s*gb\b|\b256g\b", "256GB"),
    (r"\b512\s*gb\b|\b512g\b", "512GB"),
    (r"\b1\s*tb\b|\b1024\s*gb\b", "1TB"),
    (r"\b4\s*gb\b|\b4g\b", "4GB"),
    (r"\b8\s*gb\b|\b8g\b", "8GB"),
    (r"\b16\s*gb\b|\b16g\b", "16GB"),
    (r"\b32\s*gb\b|\b32g\b", "32GB"),
    (r"\b64\s*gb\b|\b64g\b", "64GB"),
]

COLOR_PATTERNS = [
    (r"\b(desert titanium|sa mạc|desert)\b", "Desert Titanium"),
    (r"\b(natural titanium|titan tự nhiên)\b", "Natural Titanium"),
    (r"\b(black titanium|titan đen|đen|black)\b", "Black"),
    (r"\b(white titanium|titan trắng|trắng|white)\b", "White"),
]

def extract_variant_attributes(text: str) -> Dict[str, Any]:
    """Extracts storage, ram, color from raw text."""
    attrs: Dict[str, Any] = {}
    lower_text = text.lower()

    for pat, val in STORAGE_PATTERNS:
        if re.search(pat, lower_text):
            attrs["storage"] = val
            break

    for pat, val in COLOR_PATTERNS:
        if re.search(pat, lower_text):
            attrs["color"] = val
            break

    return attrs


def is_spec_compatible(product: DimProduct, text: str) -> bool:
    """
    Kiểm tra tính toàn vẹn đặc tả:
    Ngăn chặn tuyệt đối việc gán nhầm:
    - iPhone 16 Base bị match từ tin đăng iPhone 16 Plus / Pro / Pro Max
    - iPhone 16 Plus bị match khi không có từ khóa Plus
    - RAM DDR5 bị match từ tin đăng DDR3 hoặc DDR4
    - RAM DDR3/DDR4 bị match từ tin đăng DDR5
    """
    if not product:
        return False

    slug = (product.slug or "").lower()
    name = (product.name or "").lower()
    text_lower = text.lower()

    # 1. iPhone Model Guard
    if "iphone-16" in slug or "iphone 16" in name:
        # Nếu sản phẩm là iPhone 16 Base (không phải Plus / Pro / Pro Max)
        if slug == "iphone-16" or name == "iphone 16":
            # Tiêu đề tuyệt đối KHÔNG ĐƯỢC chứa Plus, Pro, Max, Mini, PRM
            if re.search(r"\b(plus|\+|pro|max|promax|prm|mini)\b", text_lower):
                return False
            # Cũng không được là model đời khác (vd: iphone 13, 14, 15, 17, 7, 6s)
            if re.search(r"\b(13|14|15|17|18|7|7g|6s|5s|x|xs|xr)\b", text_lower) and not re.search(r"\b(16)\b", text_lower):
                return False

        elif "plus" in slug or "plus" in name:
            # Nếu sản phẩm là iPhone 16 Plus -> BẮT BUỘC phải có Plus hoặc '+'
            if not re.search(r"\b(plus|\+)\b", text_lower):
                return False
            # Không được chứa Pro hoặc Pro Max
            if re.search(r"\b(pro|promax|prm)\b", text_lower):
                return False

        elif "pro-max" in slug or "pro max" in name:
            # Nếu sản phẩm là iPhone 16 Pro Max -> BẮT BUỘC phải có Pro Max / PRM
            if not re.search(r"\b(pro\s*max|prm|promax)\b", text_lower):
                return False

        elif "pro" in slug or "pro" in name:
            # Nếu sản phẩm là iPhone 16 Pro -> BẮT BUỘC có Pro, nhưng KHÔNG ĐƯỢC có Max
            if not re.search(r"\b(pro)\b", text_lower) or re.search(r"\b(max|promax|prm)\b", text_lower):
                return False

    # 2. RAM Generation Guard (DDR3 vs DDR4 vs DDR5)
    is_ram_product = "ram" in slug or "ram" in name or "ddr" in slug or "ddr" in name
    if is_ram_product:
        # Phát hiện thế hệ RAM trong tin đăng
        has_ddr5 = bool(re.search(r"\b(ddr5|pc5)\b", text_lower))
        has_ddr4 = bool(re.search(r"\b(ddr4|pc4)\b", text_lower))
        has_ddr3 = bool(re.search(r"\b(ddr3|pc3|pc3l)\b", text_lower))

        prod_is_ddr5 = "ddr5" in slug or "ddr5" in name
        prod_is_ddr4 = "ddr4" in slug or "ddr4" in name
        prod_is_ddr3 = "ddr3" in slug or "ddr3" in name

        if prod_is_ddr5 and (has_ddr3 or has_ddr4) and not has_ddr5:
            return False
        if prod_is_ddr4 and (has_ddr3 or has_ddr5) and not has_ddr4:
            return False
        if prod_is_ddr3 and (has_ddr4 or has_ddr5) and not has_ddr3:
            return False

    return True


def match_product_and_variant(
    title: str,
    db: Session,
    description: str = ""
) -> Tuple[Optional[DimProduct], Optional[DimVariant], float, str, Dict[str, Any]]:
    """
    Pipeline matching:
    1. Check intent: ACCESSORY, PARTS, SERVICE, SPAM -> Do NOT match to full main device!
    2. Exact / Substring match via DB and static alias dictionary with spec consistency check
    3. Fuzzy match against canonical product names with spec consistency check
    Returns: (product, variant, confidence, pipeline_stage, extracted_attributes)
    """
    full_text = f"{title} {description}".lower()
    attrs = extract_variant_attributes(full_text)

    # 0. CHẶN PHỤ KIỆN VÀ LINH KIỆN HỎNG / DỊCH VỤ NGAY TỪ ĐẦU
    intent, intent_conf = classify_listing_intent(title, description)
    if intent in ("ACCESSORY", "PARTS", "SERVICE", "SPAM", "BUY"):
        # Không được match một chiếc ốp lưng hay xác máy thành sản phẩm điện thoại/PC hoàn chỉnh
        return None, None, 0.0, f"EXCLUDED_{intent}", attrs

    # 1. Check Static Aliases (sorted by longest alias first)
    sorted_aliases = sorted(STATIC_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
    matched_slug = None
    for alias_key, slug in sorted_aliases:
        pattern = r"(?:^|\W)" + re.escape(alias_key) + r"(?:$|\W)"
        if re.search(pattern, full_text):
            # Tìm product trong DB theo slug
            candidate = db.query(DimProduct).filter(DimProduct.slug == slug).first()
            if candidate and is_spec_compatible(candidate, full_text):
                matched_slug = slug
                matched_product = candidate
                var = resolve_variant(matched_product, attrs)
                return matched_product, var, 0.95, "DICTIONARY", attrs

    # 2. Check Database Aliases (dim_product_alias)
    db_aliases = db.query(DimProductAlias).all()
    sorted_db_aliases = sorted(db_aliases, key=lambda a: len(a.alias), reverse=True)
    for a in sorted_db_aliases:
        pattern = r"(?:^|\W)" + re.escape(a.alias.lower()) + r"(?:$|\W)"
        if re.search(pattern, full_text):
            if is_spec_compatible(a.product, full_text):
                matched_product = a.product
                var = resolve_variant(matched_product, attrs)
                return matched_product, var, 0.92, "DICTIONARY", attrs

    # 3. Check Canonical Product Names in DB
    all_products = db.query(DimProduct).filter(DimProduct.is_active == True).all()
    for p in all_products:
        pattern = r"(?:^|\W)" + re.escape(p.name.lower()) + r"(?:$|\W)"
        if re.search(pattern, full_text):
            if is_spec_compatible(p, full_text):
                var = resolve_variant(p, attrs)
                return p, var, 0.90, "DETERMINISTIC", attrs

    # 4. Fuzzy Matching fallback (vẫn phải thỏa mãn is_spec_compatible)
    best_product = None
    best_score = 0.0
    for p in all_products:
        if not is_spec_compatible(p, full_text):
            continue
        score = difflib.SequenceMatcher(None, p.name.lower(), title.lower()).ratio()
        if score > best_score:
            best_score = score
            best_product = p

    if best_product and best_score >= 0.75:
        var = resolve_variant(best_product, attrs)
        return best_product, var, round(best_score, 2), "FUZZY", attrs

    return None, None, 0.0, "UNRESOLVED", attrs


def resolve_variant(product: DimProduct, attrs: Dict[str, Any]) -> Optional[DimVariant]:
    """Matches variant within product based on extracted storage and color."""
    if not product or not product.variants:
        return None

    storage = attrs.get("storage")
    for v in product.variants:
        v_specs = v.variant_specs or {}
        if storage and v_specs.get("storage") == storage:
            return v

    # Fallback to first active variant if available
    return product.variants[0] if product.variants else None

