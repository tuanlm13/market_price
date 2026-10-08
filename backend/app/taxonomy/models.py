from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class DimCategory(Base):
    __tablename__ = "dim_category"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("dim_category.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    parent = relationship("DimCategory", remote_side=[id], backref="children")
    product_families = relationship("DimProductFamily", back_populates="category", cascade="all, delete-orphan")
    products = relationship("DimProduct", back_populates="category", cascade="all, delete-orphan")


class DimBrand(Base):
    __tablename__ = "dim_brand"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    country = Column(String(50), nullable=True)
    logo_url = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    product_families = relationship("DimProductFamily", back_populates="brand", cascade="all, delete-orphan")
    products = relationship("DimProduct", back_populates="brand", cascade="all, delete-orphan")


class DimProductFamily(Base):
    __tablename__ = "dim_product_family"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("dim_category.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("dim_brand.id"), nullable=False)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    category = relationship("DimCategory", back_populates="product_families")
    brand = relationship("DimBrand", back_populates="product_families")
    products = relationship("DimProduct", back_populates="family", cascade="all, delete-orphan")


class DimProduct(Base):
    __tablename__ = "dim_product"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("dim_category.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("dim_brand.id"), nullable=False)
    family_id = Column(Integer, ForeignKey("dim_product_family.id"), nullable=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    model_code = Column(String(100), nullable=True)
    base_specs = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    category = relationship("DimCategory", back_populates="products")
    brand = relationship("DimBrand", back_populates="products")
    family = relationship("DimProductFamily", back_populates="products")
    variants = relationship("DimVariant", back_populates="product", cascade="all, delete-orphan")


class DimVariant(Base):
    __tablename__ = "dim_variant"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("dim_product.id"), nullable=False)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    canonical_id = Column(String(200), unique=True, nullable=False, index=True)
    variant_specs = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    product = relationship("DimProduct", back_populates="variants")
    market_segments = relationship("DimMarketSegment", back_populates="variant", cascade="all, delete-orphan")


class DimCondition(Base):
    __tablename__ = "dim_condition"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    grade = Column(String(20), nullable=False)
    multiplier_weight = Column(Numeric(4, 2), default=1.0)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    market_segments = relationship("DimMarketSegment", back_populates="condition")


class DimMarketSegment(Base):
    __tablename__ = "dim_market_segment"

    id = Column(Integer, primary_key=True, index=True)
    variant_id = Column(Integer, ForeignKey("dim_variant.id"), nullable=False)
    condition_id = Column(Integer, ForeignKey("dim_condition.id"), nullable=False)
    canonical_key = Column(String(255), unique=True, nullable=False, index=True)
    target_price_ref = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    variant = relationship("DimVariant", back_populates="market_segments")
    condition = relationship("DimCondition", back_populates="market_segments")


class DimSource(Base):
    __tablename__ = "dim_source"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    domain = Column(String(255), unique=True, nullable=False)
    source_type = Column(String(50), default="e-commerce")  # e-commerce, marketplace, classified, forum
    country = Column(String(10), default="VN")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
