from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Numeric, Boolean, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import app.taxonomy.models
import app.collectors.models

class DimProductAlias(Base):
    __tablename__ = "dim_product_alias"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("dim_product.id"), nullable=False, index=True)
    alias = Column(String(150), unique=True, nullable=False, index=True)
    locale = Column(String(20), default="vi")  # vi, en, zh, all
    created_at = Column(DateTime, server_default=func.now())

    product = relationship("DimProduct")


class FactNormalizedListing(Base):
    __tablename__ = "fact_normalized_listing"

    id = Column(Integer, primary_key=True, index=True)
    raw_listing_id = Column(Integer, ForeignKey("fact_raw_listing.id"), unique=True, nullable=False, index=True)

    product_id = Column(Integer, ForeignKey("dim_product.id"), nullable=True, index=True)
    variant_id = Column(Integer, ForeignKey("dim_variant.id"), nullable=True, index=True)
    condition_id = Column(Integer, ForeignKey("dim_condition.id"), nullable=True, index=True)
    market_segment_id = Column(Integer, ForeignKey("dim_market_segment.id"), nullable=True, index=True)

    normalized_price = Column(Numeric(14, 2), nullable=True)
    currency = Column(String(20), default="VND")
    price_valid = Column(Boolean, default=True)
    price_validity_reason = Column(String(500), nullable=True)

    normalized_attributes = Column(JSON, default=dict)
    classification = Column(String(50), default="SELL", nullable=False)  # SELL, BUY, WANTED, SERVICE, ACCESSORY, PARTS, SPAM, UNKNOWN

    ai_confidence = Column(Float, default=1.0)
    pipeline_stage = Column(String(50), default="DETERMINISTIC")  # DETERMINISTIC, DICTIONARY, REGEX, FUZZY, AI, MANUAL
    normalization_version = Column(String(50), default="v1.0.0")
    normalized_at = Column(DateTime, server_default=func.now())
    manual_review_required = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    raw_listing = relationship("FactRawListing")
    product = relationship("DimProduct")
    variant = relationship("DimVariant")
    condition = relationship("DimCondition")
    market_segment = relationship("DimMarketSegment")
    audit_logs = relationship("NormalizationAuditLog", back_populates="normalized_listing", cascade="all, delete-orphan")


class FactNormalizedComment(Base):
    __tablename__ = "fact_normalized_comment"

    id = Column(Integer, primary_key=True, index=True)
    raw_comment_id = Column(Integer, ForeignKey("fact_raw_comment.id"), unique=True, nullable=False, index=True)

    classification = Column(String(50), nullable=False)  # NEGOTIATION, SELLER_PRICE, COMPETING_OFFER, SOLD_SIGNAL, PRICE_REFERENCE, WTB, NOISE
    extracted_price = Column(Numeric(14, 2), nullable=True)
    currency = Column(String(20), default="VND")
    ai_confidence = Column(Float, default=1.0)
    normalized_at = Column(DateTime, server_default=func.now())

    raw_comment = relationship("FactRawComment")


class NormalizationAuditLog(Base):
    __tablename__ = "normalization_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    normalized_listing_id = Column(Integer, ForeignKey("fact_normalized_listing.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    corrected_by = Column(String(100), default="manual_reviewer")
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    normalized_listing = relationship("FactNormalizedListing", back_populates="audit_logs")
