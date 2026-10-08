import logging
from typing import Dict, Any, List, Optional
from .thresholds import get_category_threshold, CategoryThreshold
from .calculator import calculate_acquisition_cost, calculate_financial_metrics
from .schemas import DealAppraisalOutput

logger = logging.getLogger(__name__)

class DealAppraiser:
    """
    Core Appraisal Engine:
    - Rule engine first (deterministic filtering).
    - Deep AI analysis chỉ dành cho candidate có tiềm năng (BUY / WATCH).
    - AI không được sửa số liệu market numbers.
    """

    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider

    def appraise(
        self,
        listing_data: Dict[str, Any],
        market_stats: Dict[str, Any],
        category_code: Optional[str] = None,
        effective_price: Optional[float] = None,
        effective_price_source: str = "LISTING_PRICE",
        comments: Optional[List[Dict[str, Any]]] = None
    ) -> DealAppraisalOutput:
        # 1. Xác định threshold phù hợp theo Category
        threshold = get_category_threshold(category_code)

        # 2. Xác định giá đánh giá (Ưu tiên effective price nếu người bán đã giảm trong comment)
        raw_asking_price = float(listing_data.get("asking_price") or listing_data.get("price") or 0.0)
        asking_price = float(effective_price) if effective_price is not None and effective_price > 0 else raw_asking_price

        source = listing_data.get("source", "")
        condition = (listing_data.get("condition") or "UNKNOWN").upper().strip()

        # 3. Tính toán chi phí vốn & các chỉ số tài chính chuẩn xác
        acquisition_cost = calculate_acquisition_cost(source, asking_price, threshold)
        fin = calculate_financial_metrics(asking_price, acquisition_cost, market_stats)

        confidence = int(market_stats.get("confidence") or 0)
        liquidity = int(market_stats.get("liquidity") or 0)

        title = listing_data.get("title", "")
        desc = listing_data.get("description", "")
        desc_lower = f"{title} {desc}".lower()

        # 4. ANOMALY & RISK PRE-CHECKS (Giá ảo, trả góp, phụ kiện)
        import re
        from app.normalization.rules.classification_rules import is_junk_listing
        is_installment = bool(re.search(r"\b(trả góp|trả trước|đưa trước|chỉ từ|góp từ|góp 0%|góp qua cccd|hồ sơ duyệt|nợ xấu|góp chỉ)\b", desc_lower))
        is_accessory_or_parts = (
            is_junk_listing(title)
            or bool(re.search(r"\b(ốp lưng|ốp|case|cường lực|bao da|xác máy|rã xác|hộp rỗng|box rỗng)\b", desc_lower))
        )
        
        # Deep discount anomaly: Rẻ hơn 55% so với median hoặc rẻ hơn 50% so với Quick Sell là bất thường
        is_deep_discount_anomaly = False
        median_price = float(market_stats.get("median") or 0.0)
        qs_price = float(market_stats.get("quick_sell_price") or 0.0)
        if median_price > 0 and (median_price - asking_price) / median_price >= 0.55:
            is_deep_discount_anomaly = True
        elif qs_price > 0 and asking_price < qs_price * 0.45:
            is_deep_discount_anomaly = True

        initial_risks: List[str] = []
        if is_installment:
            initial_risks.append("Cảnh báo hình thức: Bài đăng chứa dấu hiệu trả góp/trả trước")
        if is_accessory_or_parts:
            initial_risks.append("Cảnh báo nội dung: Bài đăng chứa từ khóa phụ kiện hoặc xác máy lỗi")
        if is_deep_discount_anomaly:
            initial_risks.append("CẢNH BÁO GIÁ ẢO: Giá rao rẻ hơn 55% so với thị trường. Nghi vấn trả góp/trả trước hoặc phụ kiện/xác.")

        # 5. RULE ENGINE
        is_acceptable_condition = condition in threshold.acceptable_conditions
        meets_profit = fin["expected_profit"] >= threshold.min_profit
        meets_roi = fin["roi"] >= threshold.min_roi
        meets_confidence = confidence >= threshold.min_confidence

        preliminary_decision = "SKIP"

        if not is_acceptable_condition:
            initial_risks.append(f"Tình trạng máy '{condition}' không nằm trong tiêu chuẩn thu mua an toàn")

        if confidence < threshold.min_confidence:
            initial_risks.append(f"Độ tin cậy dữ liệu thị trường thấp ({confidence}/{threshold.min_confidence})")

        if fin["expected_profit"] < 0:
            initial_risks.append("Giá vốn cao hơn mốc Quick Sell (Lỗ dự kiến)")

        # Nếu có dấu hiệu giá ảo, trả góp hoặc phụ kiện -> BẮT BUỘC SKIP
        if is_installment or is_accessory_or_parts or is_deep_discount_anomaly:
            preliminary_decision = "SKIP"
        elif is_acceptable_condition and meets_profit and meets_roi and meets_confidence:
            preliminary_decision = "BUY"
        elif is_acceptable_condition and fin["expected_profit"] > 0 and fin["roi"] >= (threshold.min_roi * 0.6):
            preliminary_decision = "WATCH"
        else:
            preliminary_decision = "SKIP"

        # 6. Nếu preliminary là SKIP: Trả về kết quả ngay, không gọi LLM để tiết kiệm chi phí
        if preliminary_decision == "SKIP":
            if is_installment:
                reason = f"Bỏ qua: Phát hiện chiêu trò trả góp/trả trước (giá rao {asking_price:,.0f} đ chỉ là tiền cọc/đưa trước)."
            elif is_accessory_or_parts:
                reason = f"Bỏ qua: Phát hiện bài đăng là phụ kiện (ốp lưng/sạc...) hoặc linh kiện xác máy hỏng."
            elif is_deep_discount_anomaly:
                reason = (
                    f"Bỏ qua: Giá thấp bất thường ({asking_price:,.0f} đ rẻ hơn 55% so với thị trường Median {median_price:,.0f} đ). "
                    f"Rủi ro rất cao là giá trả góp/trả trước, phụ kiện hoặc lừa đảo cọc."
                )
            else:
                reason = (
                    f"Bỏ qua: Không đạt tiêu chí đầu tư. "
                    f"Lợi nhuận kỳ vọng: {fin['expected_profit']:,.0f} đ (ngưỡng min: {threshold.min_profit:,.0f} đ), "
                    f"ROI: {fin['roi']*100:.1f}% (ngưỡng min: {threshold.min_roi*100:.1f}%)."
                )

            return DealAppraisalOutput(
                decision="SKIP",
                confidence=0.90,
                market_position=fin["market_position"],
                asking_price=asking_price,
                acquisition_cost=acquisition_cost,
                quick_sell_price=fin["quick_sell_price"],
                expected_profit=fin["expected_profit"],
                roi=fin["roi"],
                discount_vs_median=fin["discount_vs_median"],
                discount_vs_p25=fin["discount_vs_p25"],
                discount_vs_quick_sell=fin["discount_vs_quick_sell"],
                market_confidence=confidence,
                liquidity=liquidity,
                risks=initial_risks,
                reason=reason,
                effective_price_source=effective_price_source
            )

        # 7. CANDIDATE TIỀM NĂNG (BUY / WATCH): Thực hiện Condition & Risk Analysis / AI Explanation
        final_decision = preliminary_decision
        ai_confidence = 0.85
        reason = ""
        risks = list(initial_risks)

        # Risk scan từ nội dung bài đăng
        if any(w in desc_lower for w in ["icloud", "mất vân", "mất face", "ám màn", "màn sọc", "ép kính", "thay vỏ"]):
            risks.append("Mô tả chứa rủi ro phần cứng/phần mềm (màn hình/FaceID/linh kiện)")
            if final_decision == "BUY":
                final_decision = "WATCH"

        if any(w in desc_lower for w in ["chuyển khoản trước", "cọc trước", "ship cod không cọc"]):
            risks.append("Cảnh báo giao dịch: Yêu cầu cọc/chuyển khoản trước")

        if not risks:
            risks.append("Không phát hiện rủi ro bất thường từ mô tả")

        # Tạo giải thích chuyên sâu (AI Explanation)
        discount_desc = f"thấp hơn P25 {fin['discount_vs_p25']*100:.1f}%" if fin['discount_vs_p25'] > 0 else f"chiết khấu {fin['discount_vs_median']*100:.1f}% so với Median"
        effective_note = f" (Giá cập nhật từ người bán: {asking_price:,.0f} đ)" if effective_price_source == "SELLER_COMMENT" else ""

        if final_decision == "BUY":
            reason = (
                f"Kèo thơm đáng mua: Giá rao {asking_price:,.0f} đ{effective_note} {discount_desc}. "
                f"Dự kiến chốt lời nhanh {fin['expected_profit']:,.0f} đ (ROI {fin['roi']*100:.1f}%) "
                f"với giá Quick Sell {fin['quick_sell_price']:,.0f} đ. "
                f"Độ thanh khoản {liquidity}/100."
            )
        else:
            reason = (
                f"Theo dõi thêm: Giá rao {asking_price:,.0f} đ{effective_note} có biên lợi nhuận {fin['expected_profit']:,.0f} đ (ROI {fin['roi']*100:.1f}%), "
                f"nhưng rủi ro hoặc chênh lệch chưa tối ưu để chốt ngay."
            )

        return DealAppraisalOutput(
            decision=final_decision,
            confidence=ai_confidence,
            market_position=fin["market_position"],
            asking_price=asking_price,
            acquisition_cost=acquisition_cost,
            quick_sell_price=fin["quick_sell_price"],
            expected_profit=fin["expected_profit"],
            roi=fin["roi"],
            discount_vs_median=fin["discount_vs_median"],
            discount_vs_p25=fin["discount_vs_p25"],
            discount_vs_quick_sell=fin["discount_vs_quick_sell"],
            market_confidence=confidence,
            liquidity=liquidity,
            risks=risks,
            reason=reason,
            effective_price_source=effective_price_source
        )
