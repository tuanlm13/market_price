from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class FactRawListing(Base):
    __tablename__ = "fact_raw_listing"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("dim_source.id"), nullable=False, index=True)
    source_listing_id = Column(String(255), nullable=False, index=True)
    url = Column(Text, nullable=False)

    raw_title = Column(Text, nullable=False)
    raw_description = Column(Text, nullable=True)
    raw_price_text = Column(String(100), nullable=True)
    raw_currency = Column(String(20), default="VND")

    seller_name_raw = Column(String(255), nullable=True)
    seller_id_raw = Column(String(255), nullable=True)
    location_raw = Column(String(255), nullable=True)

    published_at = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, server_default=func.now())
    last_seen_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    raw_metadata = Column(JSON, default=dict)
    crawl_status = Column(String(50), default="RAW_CAPTURED")  # RAW_CAPTURED, NORMALIZED, IGNORED

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("source_id", "source_listing_id", name="uq_fact_raw_listing_source_item"),
    )

    source = relationship("DimSource")
    price_snapshots = relationship("FactListingPriceSnapshot", back_populates="listing", cascade="all, delete-orphan")
    comments = relationship("FactRawComment", back_populates="listing", cascade="all, delete-orphan")


class FactListingPriceSnapshot(Base):
    __tablename__ = "fact_listing_price_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("fact_raw_listing.id"), nullable=False, index=True)
    price_raw = Column(String(100), nullable=False)
    currency = Column(String(20), default="VND")
    captured_at = Column(DateTime, server_default=func.now(), index=True)

    listing = relationship("FactRawListing", back_populates="price_snapshots")


class FactRawComment(Base):
    __tablename__ = "fact_raw_comment"

    id = Column(Integer, primary_key=True, index=True)
    source_comment_id = Column(String(255), nullable=False, index=True)
    listing_id = Column(Integer, ForeignKey("fact_raw_listing.id"), nullable=False, index=True)
    author = Column(String(255), nullable=True)
    raw_text = Column(Text, nullable=False)
    created_at_source = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, server_default=func.now())

    listing = relationship("FactRawListing", back_populates="comments")


class CollectorHealth(Base):
    __tablename__ = "collector_health"

    id = Column(Integer, primary_key=True, index=True)
    source_code = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(50), default="IDLE")  # IDLE, RUNNING, SUCCESS, ERROR, AUTH_REQUIRED, BLOCKED
    last_start = Column(DateTime, nullable=True)
    last_success = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    items_scanned = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    auth_status = Column(String(50), default="OK")  # OK, LOGIN_REQUIRED, CHECKPOINT, EXPIRED
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
