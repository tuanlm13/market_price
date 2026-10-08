import os
import json
import logging
import requests
from typing import Optional, Dict, Any
from app.normalization.providers.base import AIProvider
from app.normalization.schemas import AIListingNormalizationResult, AICommentClassificationResult

logger = logging.getLogger(__name__)

class GeminiProvider(AIProvider):
    """
    Adapter for Google Gemini API.
    Configured via GEMINI_API_KEY / AI_API_KEY.
    Enforces Pydantic structured output validation.
    """
    provider_name: str = "gemini"

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", os.getenv("AI_API_KEY", ""))
        self.model = os.getenv("GEMINI_MODEL", os.getenv("AI_MODEL", "gemini-3.1-flash-lite"))
        self.tokens_prompt = 0
        self.tokens_completion = 0

    def _call_gemini(self, system_instruction: str, user_prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY or AI_API_KEY is not configured.")

        candidate_models = [self.model, "gemini-3.1-flash-lite", "gemini-flash-latest"]
        last_error = None

        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": f"System: {system_instruction}\n\nUser: {user_prompt}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1
                }
            }

            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_out = candidates[0]["content"]["parts"][0]["text"].strip()
                        if text_out.startswith("```"):
                            text_out = text_out.split("\n", 1)[1]
                            if text_out.endswith("```"):
                                text_out = text_out.rsplit("```", 1)[0]
                        return json.loads(text_out.strip())
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Không nhận được phản hồi hợp lệ từ Gemini API.")

    def normalize_listing(
        self,
        title: str,
        description: str = "",
        raw_price_text: Optional[str] = None,
        raw_currency: str = "VND"
    ) -> AIListingNormalizationResult:
        sys = (
            "You are an expert product data normalization engine. Return a JSON object with: "
            "canonical_product_name, brand_name, variant_attributes, condition_code, "
            "classification (SELL, BUY, WANTED, SERVICE, ACCESSORY, PARTS, SPAM, UNKNOWN), "
            "clean_price_amount, currency, price_valid, price_validity_reason, confidence, manual_review_required, reasoning."
        )
        user = f"Title: {title}\nDescription: {description}\nPrice: {raw_price_text}\nCurrency: {raw_currency}"
        res = self._call_gemini(sys, user)
        return AIListingNormalizationResult(**res)

    def classify_comment(
        self,
        raw_text: str
    ) -> AICommentClassificationResult:
        sys = (
            "Classify comment into NEGOTIATION, SELLER_PRICE, COMPETING_OFFER, SOLD_SIGNAL, PRICE_REFERENCE, WTB, NOISE. "
            "Return JSON with: classification, extracted_price, currency, confidence."
        )
        res = self._call_gemini(sys, f"Comment: {raw_text}")
        return AICommentClassificationResult(**res)
