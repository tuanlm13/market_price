from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class DealAppraisalOutput(BaseModel):
    decision: str = Field(..., description="Quyết định thẩm định: BUY, WATCH, hoặc SKIP")
    confidence: float = Field(..., description="Độ tin cậy của nhận định (0.0 - 1.0)")
    market_position: str = Field(..., description="Vị trí so với thị trường: DEEP_DISCOUNT, BELOW_P25, BELOW_MEDIAN, AT_MEDIAN, ABOVE_MEDIAN")
    asking_price: float = Field(..., description="Giá rao bán (hoặc effective seller price nếu có)")
    acquisition_cost: float = Field(..., description="Tổng giá vốn sau khi cộng chi phí ước tính")
    quick_sell_price: float = Field(..., description="Giá thanh khoản nhanh tham chiếu")
    expected_profit: float = Field(..., description="Lợi nhuận kỳ vọng = Quick sell - Acquisition cost")
    roi: float = Field(..., description="Tỷ suất lợi nhuận trên chi phí vốn")
    discount_vs_median: float = Field(0.0, description="Tỷ lệ giảm giá so với trung vị")
    discount_vs_p25: float = Field(0.0, description="Tỷ lệ giảm giá so với P25")
    discount_vs_quick_sell: float = Field(0.0, description="Tỷ lệ giảm giá so với Quick Sell")
    market_confidence: int = Field(0, description="Độ tin cậy của số liệu thị trường (0-100)")
    liquidity: int = Field(0, description="Chỉ số thanh khoản thị trường (0-100)")
    risks: List[str] = Field(default_factory=list, description="Danh sách rủi ro tiềm ẩn (phụ kiện, ngoại hình, người bán...)")
    reason: str = Field(..., description="Giải thích chi tiết lý do ra quyết định")
    effective_price_source: Optional[str] = Field(None, description="Nguồn gốc giá: LISTING_PRICE hoặc SELLER_COMMENT")
