from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Numeric, Boolean, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import app.taxonomy.models
import app.collectors.models
import app.normalization.models

class FactDealAppraisal(Base):
    __tablename__ = "fact_deal_appraisal"

    id = Column(Integer, primary_key=True, index=True)
    normalized_listing_id = Column(Integer, ForeignKey("fact_normalized_listing.id"), nullable=False, index=True)

    decision = Column(String(20), nullable=False, index=True)  # BUY, WATCH, SKIP
    market_confidence = Column(Integer, default=50)
    liquidity = Column(Integer, default=50)

    asking_price = Column(Numeric(14, 2), nullable=False)
    acquisition_cost = Column(Numeric(14, 2), nullable=False)
    quick_sell_price = Column(Numeric(14, 2), nullable=False)
    expected_profit = Column(Numeric(14, 2), nullable=False)
    roi = Column(Float, default=0.0)

    discount_vs_median = Column(Float, default=0.0)
    discount_vs_p25 = Column(Float, default=0.0)
    discount_vs_quick_sell = Column(Float, default=0.0)

    market_position = Column(String(50), default="NORMAL")  # VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE
    risks = Column(JSON, default=list)
    ai_reasoning = Column(Text, nullable=True)
    ai_confidence = Column(Float, default=1.0)

    alert_sent = Column(Boolean, default=False, index=True)
    alert_sent_at = Column(DateTime, nullable=True)
    effective_price_source = Column(String(50), default="LISTING")  # LISTING, SELLER_COMMENT, USER_COMMENT

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    normalized_listing = relationship("FactNormalizedListing")
