import os
import json
import logging
import requests
from typing import Optional, Dict, Any
from app.normalization.providers.base import AIProvider
from app.normalization.schemas import AIListingNormalizationResult, AICommentClassificationResult

logger = logging.getLogger(__name__)

class OpenAICompatibleProvider(AIProvider):
    """
    Adapter for OpenAI, Azure, Groq, DeepSeek, or local Ollama endpoints.
    Configured strictly through environment variables.
    Enforces Pydantic structured output validation.
    """
    provider_name: str = "openai_compatible"

    def __init__(self):
        self.api_key = os.getenv("AI_API_KEY", "")
        self.base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("AI_MODEL", "gpt-4o-mini")
        self.tokens_prompt = 0
        self.tokens_completion = 0
        self.cost_per_1k_prompt = 0.00015
        self.cost_per_1k_completion = 0.00060

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("AI_API_KEY environment variable is not configured.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=25)
        resp.raise_for_status()
        data = resp.json()

        usage = data.get("usage", {})
        self.tokens_prompt += usage.get("prompt_tokens", 0)
        self.tokens_completion += usage.get("completion_tokens", 0)

        raw_content = data["choices"][0]["message"]["content"]
        return json.loads(raw_content)

    def normalize_listing(
        self,
        title: str,
        description: str = "",
        raw_price_text: Optional[str] = None,
        raw_currency: str = "VND"
    ) -> AIListingNormalizationResult:
        system_prompt = (
            "You are an expert e-commerce data normalization engine. "
            "Analyze the listing title and description. Return JSON matching this exact structure: "
            "canonical_product_name (string or null), brand_name (string or null), "
            "variant_attributes (object with storage, ram, color), "
            "condition_code (one of: NEW_SEAL, OPEN_BOX, LIKE_NEW_99, VERY_GOOD_95, GOOD_90, FAIR_80, FOR_PARTS, or null), "
            "classification (one of: SELL, BUY, WANTED, SERVICE, ACCESSORY, PARTS, SPAM, UNKNOWN), "
            "clean_price_amount (float or null), currency (string), "
            "price_valid (boolean), price_validity_reason (string or null if valid), "
            "confidence (float between 0.0 and 1.0), manual_review_required (boolean), reasoning (string)."
        )
        user_prompt = f"Title: {title}\nDescription: {description}\nRaw Price: {raw_price_text}\nCurrency: {raw_currency}"

        parsed_json = self._call_llm(system_prompt, user_prompt)
        # Validate through Pydantic
        return AIListingNormalizationResult(**parsed_json)

    def classify_comment(
        self,
        raw_text: str
    ) -> AICommentClassificationResult:
        system_prompt = (
            "Classify the following e-commerce comment into: "
            "NEGOTIATION, SELLER_PRICE, COMPETING_OFFER, SOLD_SIGNAL, PRICE_REFERENCE, WTB, NOISE. "
            "Return JSON: classification (string), extracted_price (float or null), currency (string), confidence (float)."
        )
        parsed_json = self._call_llm(system_prompt, f"Comment: {raw_text}")
        return AICommentClassificationResult(**parsed_json)

    def get_metrics(self) -> Dict[str, Any]:
        cost = (
            (self.tokens_prompt / 1000.0) * self.cost_per_1k_prompt +
            (self.tokens_completion / 1000.0) * self.cost_per_1k_completion
        )
        return {
            "provider": self.provider_name,
            "model": self.model,
            "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion,
            "cost_usd": round(cost, 5)
        }
