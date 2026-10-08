from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from app.taxonomy.models import (
    DimCategory, DimBrand, DimProductFamily, DimProduct,
    DimVariant, DimCondition, DimMarketSegment
)
from app.taxonomy.schemas import (
    CategoryOut, BrandOut, ProductFamilyOut, ProductOut,
    ProductDetailOut, VariantOut, ConditionOut, MarketSegmentOut
)

router = APIRouter(tags=["Market Taxonomy"])

# Categories
@router.get("/taxonomy/categories", response_model=List[CategoryOut])
@router.get("/categories/market", response_model=List[CategoryOut])
def get_taxonomy_categories(db: Session = Depends(get_db)):
    return db.query(DimCategory).order_by(DimCategory.name).all()

# Brands
@router.get("/brands", response_model=List[BrandOut])
@router.get("/taxonomy/brands", response_model=List[BrandOut])
def get_brands(db: Session = Depends(get_db)):
    return db.query(DimBrand).order_by(DimBrand.name).all()

# Product Families
@router.get("/product-families", response_model=List[ProductFamilyOut])
@router.get("/taxonomy/product-families", response_model=List[ProductFamilyOut])
def get_product_families(
    category_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(DimProductFamily)
    if category_id:
        query = query.filter(DimProductFamily.category_id == category_id)
    if brand_id:
        query = query.filter(DimProductFamily.brand_id == brand_id)
    return query.order_by(DimProductFamily.name).all()

# Conditions
@router.get("/conditions", response_model=List[ConditionOut])
@router.get("/taxonomy/conditions", response_model=List[ConditionOut])
def get_conditions(db: Session = Depends(get_db)):
    return db.query(DimCondition).order_by(DimCondition.multiplier_weight.desc()).all()

# Variants
@router.get("/variants", response_model=List[VariantOut])
@router.get("/taxonomy/variants", response_model=List[VariantOut])
def get_variants(
    product_id: Optional[int] = Query(None),
    sku: Optional[str] = Query(None),
    canonical_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(DimVariant)
    if product_id:
        query = query.filter(DimVariant.product_id == product_id)
    if sku:
        query = query.filter(DimVariant.sku.ilike(f"%{sku}%"))
    if canonical_id:
        query = query.filter(DimVariant.canonical_id == canonical_id)
    return query.order_by(DimVariant.name).all()

# Market Segments
@router.get("/market-segments", response_model=List[MarketSegmentOut])
@router.get("/taxonomy/market-segments", response_model=List[MarketSegmentOut])
def get_market_segments(
    variant_id: Optional[int] = Query(None),
    condition_code: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(DimMarketSegment)
    if variant_id:
        query = query.filter(DimMarketSegment.variant_id == variant_id)
    if condition_code:
        query = query.join(DimCondition).filter(DimCondition.code == condition_code.upper())
    return query.all()

# Products (Taxonomy)
@router.get("/market/products", response_model=List[ProductOut])
@router.get("/taxonomy/products", response_model=List[ProductOut])
def get_market_products(
    category_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(DimProduct).filter(DimProduct.is_active == True)
    if category_id:
        query = query.filter(DimProduct.category_id == category_id)
    if brand_id:
        query = query.filter(DimProduct.brand_id == brand_id)
    if q:
        query = query.filter(DimProduct.name.ilike(f"%{q}%"))
    return query.order_by(DimProduct.name).all()

# Product Detail (Taxonomy)
@router.get("/taxonomy/products/{product_id}", response_model=ProductDetailOut)
@router.get("/market/products/{product_id}", response_model=ProductDetailOut)
def get_market_product_detail(product_id: int, db: Session = Depends(get_db)):
    prod = db.query(DimProduct).filter(DimProduct.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found in taxonomy")
    return prod
