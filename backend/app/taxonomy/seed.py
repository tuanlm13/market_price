import logging
from decimal import Decimal
from sqlalchemy.orm import Session
from app.taxonomy.models import (
    DimCategory, DimBrand, DimProductFamily, DimProduct,
    DimVariant, DimCondition, DimMarketSegment, DimSource
)
from app.taxonomy.conditions import CONDITION_DEFINITIONS
from app.taxonomy.attributes import generate_canonical_id

logger = logging.getLogger(__name__)

def seed_taxonomy_data(db: Session):
    logger.info("Starting Taxonomy & Foundation Seed Data...")

    # 1. Seed Conditions
    condition_map = {}
    for item in CONDITION_DEFINITIONS:
        cond = db.query(DimCondition).filter(DimCondition.code == item["code"]).first()
        if not cond:
            cond = DimCondition(
                code=item["code"],
                name=item["name"],
                grade=item["grade"],
                multiplier_weight=item["multiplier_weight"],
                description=item["description"],
                is_active=True
            )
            db.add(cond)
            db.flush()
        condition_map[item["code"]] = cond

    # 2. Seed Categories
    categories_data = [
        {"code": "SMARTPHONE", "name": "Điện thoại thông minh", "slug": "smartphone", "description": "Thiết bị di động thông minh"},
        {"code": "GPU", "name": "Card đồ họa (VGA)", "slug": "gpu", "description": "Bộ xử lý đồ họa máy tính"},
        {"code": "RAM", "name": "Bộ nhớ trong (RAM)", "slug": "ram", "description": "Bộ nhớ RAM máy tính & máy chủ"}
    ]
    category_map = {}
    for cdata in categories_data:
        cat = db.query(DimCategory).filter(DimCategory.code == cdata["code"]).first()
        if not cat:
            cat = DimCategory(**cdata)
            db.add(cat)
            db.flush()
        category_map[cdata["code"]] = cat

    # 3. Seed Brands
    brands_data = [
        {"code": "APPLE", "name": "Apple", "slug": "apple", "country": "USA"},
        {"code": "MSI", "name": "MSI (Micro-Star International)", "slug": "msi", "country": "Taiwan"},
        {"code": "SAMSUNG", "name": "Samsung Electronics", "slug": "samsung", "country": "South Korea"},
        {"code": "NVIDIA", "name": "NVIDIA", "slug": "nvidia", "country": "USA"}
    ]
    brand_map = {}
    for bdata in brands_data:
        brand = db.query(DimBrand).filter(DimBrand.code == bdata["code"]).first()
        if not brand:
            brand = DimBrand(**bdata)
            db.add(brand)
            db.flush()
        brand_map[bdata["code"]] = brand

    # 4. Seed Product Families
    families_data = [
        {"category_id": category_map["SMARTPHONE"].id, "brand_id": brand_map["APPLE"].id, "name": "iPhone", "slug": "iphone", "description": "Dòng điện thoại cao cấp của Apple"},
        {"category_id": category_map["GPU"].id, "brand_id": brand_map["MSI"].id, "name": "GeForce RTX Gaming", "slug": "geforce-rtx-gaming", "description": "Card đồ họa gaming chuyên dụng"},
        {"category_id": category_map["RAM"].id, "brand_id": brand_map["SAMSUNG"].id, "name": "Server & Workstation Memory", "slug": "server-memory", "description": "RAM máy chủ và máy trạm"}
    ]
    family_map = {}
    for fdata in families_data:
        fam = db.query(DimProductFamily).filter(
            DimProductFamily.brand_id == fdata["brand_id"],
            DimProductFamily.name == fdata["name"]
        ).first()
        if not fam:
            fam = DimProductFamily(**fdata)
            db.add(fam)
            db.flush()
        family_map[fdata["name"]] = fam

    # 5. Seed Products & Variants
    # 5.1 iPhone 16 (128GB & 256GB)
    p_iphone16 = db.query(DimProduct).filter(DimProduct.slug == "iphone-16").first()
    if not p_iphone16:
        p_iphone16 = DimProduct(
            category_id=category_map["SMARTPHONE"].id,
            brand_id=brand_map["APPLE"].id,
            family_id=family_map["iPhone"].id,
            name="iPhone 16",
            slug="iphone-16",
            model_code="A3287",
            base_specs={"chipset": "Apple A18", "screen_size": "6.1 inch OLED", "camera": "48MP Dual Camera"}
        )
        db.add(p_iphone16)
        db.flush()

    # Variants iPhone 16
    v_iphone16_128 = db.query(DimVariant).filter(DimVariant.sku == "IPHONE16-128GB-VNA").first()
    if not v_iphone16_128:
        v_iphone16_128 = DimVariant(
            product_id=p_iphone16.id,
            sku="IPHONE16-128GB-VNA",
            name="iPhone 16 128GB Chính Hãng (VN/A)",
            canonical_id=generate_canonical_id("APPLE", "IPHONE16", "128GB", "VN-A", "BASE"),
            variant_specs={"storage": "128GB", "region": "VN/A", "color": "Black, White, Pink, Teal, Ultramarine"}
        )
        db.add(v_iphone16_128)
        db.flush()

    v_iphone16_256 = db.query(DimVariant).filter(DimVariant.sku == "IPHONE16-256GB-VNA").first()
    if not v_iphone16_256:
        v_iphone16_256 = DimVariant(
            product_id=p_iphone16.id,
            sku="IPHONE16-256GB-VNA",
            name="iPhone 16 256GB Chính Hãng (VN/A)",
            canonical_id=generate_canonical_id("APPLE", "IPHONE16", "256GB", "VN-A", "BASE"),
            variant_specs={"storage": "256GB", "region": "VN/A", "color": "Black, White, Pink, Teal, Ultramarine"}
        )
        db.add(v_iphone16_256)
        db.flush()

    # 5.1.1 iPhone 16 Plus
    p_iphone16_plus = db.query(DimProduct).filter(DimProduct.slug == "iphone-16-plus").first()
    if not p_iphone16_plus:
        p_iphone16_plus = DimProduct(
            category_id=category_map["SMARTPHONE"].id,
            brand_id=brand_map["APPLE"].id,
            family_id=family_map["iPhone"].id,
            name="iPhone 16 Plus",
            slug="iphone-16-plus",
            model_code="A3290",
            base_specs={"chipset": "Apple A18", "screen_size": "6.7 inch OLED", "camera": "48MP Dual Camera"}
        )
        db.add(p_iphone16_plus)
        db.flush()

    v_iphone16_plus_128 = db.query(DimVariant).filter(DimVariant.sku == "IPHONE16-PLUS-128GB-VNA").first()
    if not v_iphone16_plus_128:
        v_iphone16_plus_128 = DimVariant(
            product_id=p_iphone16_plus.id,
            sku="IPHONE16-PLUS-128GB-VNA",
            name="iPhone 16 Plus 128GB Chính Hãng (VN/A)",
            canonical_id=generate_canonical_id("APPLE", "IPHONE16-PLUS", "128GB", "VN-A", "BASE"),
            variant_specs={"storage": "128GB", "region": "VN/A", "color": "Black, White, Pink, Teal, Ultramarine"}
        )
        db.add(v_iphone16_plus_128)
        db.flush()

    # 5.1.2 iPhone 16 Pro Max
    p_iphone16_promax = db.query(DimProduct).filter(DimProduct.slug == "iphone-16-pro-max").first()
    if not p_iphone16_promax:
        p_iphone16_promax = DimProduct(
            category_id=category_map["SMARTPHONE"].id,
            brand_id=brand_map["APPLE"].id,
            family_id=family_map["iPhone"].id,
            name="iPhone 16 Pro Max",
            slug="iphone-16-pro-max",
            model_code="A3296",
            base_specs={"chipset": "Apple A18 Pro", "screen_size": "6.9 inch OLED", "camera": "48MP Triple Camera"}
        )
        db.add(p_iphone16_promax)
        db.flush()

    v_iphone16_promax_256 = db.query(DimVariant).filter(DimVariant.sku == "IPHONE16-PROMAX-256GB-VNA").first()
    if not v_iphone16_promax_256:
        v_iphone16_promax_256 = DimVariant(
            product_id=p_iphone16_promax.id,
            sku="IPHONE16-PROMAX-256GB-VNA",
            name="iPhone 16 Pro Max 256GB Chính Hãng (VN/A)",
            canonical_id=generate_canonical_id("APPLE", "IPHONE16-PROMAX", "256GB", "VN-A", "BASE"),
            variant_specs={"storage": "256GB", "region": "VN/A", "color": "Desert Titanium, Natural Titanium, Black, White"}
        )
        db.add(v_iphone16_promax_256)
        db.flush()

    # 5.2 GPU: RTX 4060 (MSI GeForce RTX 4060 Gaming X 8GB)
    p_rtx4060 = db.query(DimProduct).filter(DimProduct.slug == "msi-geforce-rtx-4060").first()
    if not p_rtx4060:
        p_rtx4060 = DimProduct(
            category_id=category_map["GPU"].id,
            brand_id=brand_map["MSI"].id,
            family_id=family_map["GeForce RTX Gaming"].id,
            name="MSI GeForce RTX 4060",
            slug="msi-geforce-rtx-4060",
            model_code="RTX-4060-GAMING-X-8G",
            base_specs={"architecture": "Ada Lovelace", "cuda_cores": 3072, "bus_width": "128-bit"}
        )
        db.add(p_rtx4060)
        db.flush()

    v_rtx4060_gamingx = db.query(DimVariant).filter(DimVariant.sku == "MSI-RTX4060-GAMING-X-8G").first()
    if not v_rtx4060_gamingx:
        v_rtx4060_gamingx = DimVariant(
            product_id=p_rtx4060.id,
            sku="MSI-RTX4060-GAMING-X-8G",
            name="MSI GeForce RTX 4060 Gaming X 8GB GDDR6",
            canonical_id=generate_canonical_id("MSI", "RTX4060", "8GB", "GAMING-X", "BASE"),
            variant_specs={"vram": "8GB GDDR6", "model_series": "Gaming X", "fans": 2, "tdp": "115W"}
        )
        db.add(v_rtx4060_gamingx)
        db.flush()

    # 5.3 RAM: Samsung DDR4 ECC 32GB 3200 (2Rx4)
    p_ram_samsung = db.query(DimProduct).filter(DimProduct.slug == "samsung-ddr4-ecc-server-ram").first()
    if not p_ram_samsung:
        p_ram_samsung = DimProduct(
            category_id=category_map["RAM"].id,
            brand_id=brand_map["SAMSUNG"].id,
            family_id=family_map["Server & Workstation Memory"].id,
            name="Samsung DDR4 ECC Server RAM",
            slug="samsung-ddr4-ecc-server-ram",
            model_code="M393A4K40EB3-CWE",
            base_specs={"type": "DDR4 RDIMM", "voltage": "1.2V", "pin_count": 288}
        )
        db.add(p_ram_samsung)
        db.flush()

    v_ram_32gb = db.query(DimVariant).filter(DimVariant.sku == "SAMSUNG-DDR4-32GB-ECC-3200-2RX4").first()
    if not v_ram_32gb:
        v_ram_32gb = DimVariant(
            product_id=p_ram_samsung.id,
            sku="SAMSUNG-DDR4-32GB-ECC-3200-2RX4",
            name="Samsung DDR4 ECC REG 32GB 3200MHz 2Rx4 RDIMM",
            canonical_id=generate_canonical_id("SAMSUNG", "DDR4-ECC", "32GB-3200", "2RX4", "BASE"),
            variant_specs={"ddr": "DDR4", "capacity": "32GB", "frequency": "3200MHz", "ecc": True, "rank": "2Rx4", "form_factor": "Server RDIMM"}
        )
        db.add(v_ram_32gb)
        db.flush()

    # 6. Seed Market Segments (Variant + Condition Canonical Identity)
    segments_to_create = [
        # iPhone 16 128GB New Sealed
        {"variant": v_iphone16_128, "cond": condition_map["N0"], "ref_price": Decimal("21990000.00"), "sub": "VN-A"},
        # iPhone 16 128GB Like New (U0)
        {"variant": v_iphone16_128, "cond": condition_map["U0"], "ref_price": Decimal("19500000.00"), "sub": "VN-A"},
        # iPhone 16 256GB New Sealed
        {"variant": v_iphone16_256, "cond": condition_map["N0"], "ref_price": Decimal("24990000.00"), "sub": "VN-A"},
        # RTX 4060 Gaming X New Sealed
        {"variant": v_rtx4060_gamingx, "cond": condition_map["N0"], "ref_price": Decimal("8690000.00"), "sub": "GAMING-X"},
        # RTX 4060 Gaming X Used Good (U1)
        {"variant": v_rtx4060_gamingx, "cond": condition_map["U1"], "ref_price": Decimal("6800000.00"), "sub": "GAMING-X"},
        # Samsung DDR4 ECC 32GB 3200 New
        {"variant": v_ram_32gb, "cond": condition_map["N0"], "ref_price": Decimal("1850000.00"), "sub": "2RX4"},
        # Samsung DDR4 ECC 32GB 3200 Used Good (U1)
        {"variant": v_ram_32gb, "cond": condition_map["U1"], "ref_price": Decimal("1350000.00"), "sub": "2RX4"},
    ]

    for item in segments_to_create:
        c_key = f"{item['variant'].canonical_id.rsplit('|', 1)[0]}|{item['cond'].code}"
        seg = db.query(DimMarketSegment).filter(DimMarketSegment.canonical_key == c_key).first()
        if not seg:
            seg = DimMarketSegment(
                variant_id=item["variant"].id,
                condition_id=item["cond"].id,
                canonical_key=c_key,
                target_price_ref=item["ref_price"]
            )
            db.add(seg)

    # 7. Seed Dim Sources (Marketplaces/Retailers)
    sources_data = [
        {"code": "THEGIOIDIDONG", "name": "Thế Giới Di Động", "domain": "thegioididong.com", "source_type": "retailer"},
        {"code": "FPT_SHOP", "name": "FPT Shop", "domain": "fptshop.com.vn", "source_type": "retailer"},
        {"code": "CELLPHONES", "name": "CellphoneS", "domain": "cellphones.com.vn", "source_type": "retailer"},
        {"code": "SHOPEE_VN", "name": "Shopee Việt Nam", "domain": "shopee.vn", "source_type": "marketplace"},
        {"code": "HAILONG_COMPUTER", "name": "Hải Long Computer", "domain": "hailongcomputer.vn", "source_type": "hardware_store"},
        {"code": "GOOFISH", "name": "Goofish (闲鱼)", "domain": "2.taobao.com", "source_type": "marketplace", "country": "CN"},
        {"code": "CHOTOT", "name": "Chợ Tốt", "domain": "chotot.com", "source_type": "classified", "country": "VN"},
        {"code": "FACEBOOK_MARKETPLACE", "name": "Facebook Marketplace", "domain": "facebook.com/marketplace", "source_type": "marketplace", "country": "VN"},
        {"code": "FACEBOOK_GROUPS", "name": "Facebook Groups", "domain": "facebook.com/groups", "source_type": "community", "country": "VN"}
    ]
    for sdata in sources_data:
        src = db.query(DimSource).filter(DimSource.code == sdata["code"]).first()
        if not src:
            src = DimSource(**sdata)
            db.add(src)

    # 8. Seed Product Aliases
    from app.normalization.models import DimProductAlias
    from app.normalization.rules.alias_matcher import STATIC_ALIASES
    for alias_name, prod_slug in STATIC_ALIASES.items():
        existing_alias = db.query(DimProductAlias).filter(DimProductAlias.alias == alias_name).first()
        if not existing_alias:
            prod = db.query(DimProduct).filter(DimProduct.slug == prod_slug).first()
            if prod:
                locale = "zh" if any(ord(c) > 10000 for c in alias_name) else "vi"
                alias_obj = DimProductAlias(
                    product_id=prod.id,
                    alias=alias_name,
                    locale=locale
                )
                db.add(alias_obj)

    db.commit()
    logger.info("Successfully seeded Taxonomy, Product & Alias data!")
