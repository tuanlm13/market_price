from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

class ConditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    grade: str
    multiplier_weight: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: bool

class CategoryBase(BaseModel):
    code: str
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None

class CategoryOut(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None

class BrandBase(BaseModel):
    code: str
    name: str
    slug: str
    country: Optional[str] = None
    logo_url: Optional[str] = None

class BrandOut(BrandBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None

class ProductFamilyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    brand_id: int
    name: str
    slug: str
    description: Optional[str] = None

class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    sku: str
    name: str
    canonical_id: str
    variant_specs: Dict[str, Any] = {}
    is_active: bool

class MarketSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    condition_id: int
    canonical_key: str
    target_price_ref: Optional[Decimal] = None
    condition: Optional[ConditionOut] = None
    variant: Optional[VariantOut] = None

class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    category_id: int
    brand_id: int
    family_id: Optional[int] = None
    name: str
    slug: str
    model_code: Optional[str] = None
    base_specs: Dict[str, Any] = {}
    is_active: bool

class ProductDetailOut(ProductOut):
    category: Optional[CategoryOut] = None
    brand: Optional[BrandOut] = None
    family: Optional[ProductFamilyOut] = None
    variants: List[VariantOut] = []
