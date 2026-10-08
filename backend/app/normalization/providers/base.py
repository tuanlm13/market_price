from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.normalization.schemas import AIListingNormalizationResult, AICommentClassificationResult

class AIProvider(ABC):
    """
    Abstract AI Provider Interface.
    Decouples LLM implementations (OpenAI, Gemini, Local models, Mock) from the normalization pipeline.
    All providers MUST return Pydantic-validated structured results.
    """
    provider_name: str = "base"

    @abstractmethod
    def normalize_listing(
        self,
        title: str,
        description: str = "",
        raw_price_text: Optional[str] = None,
        raw_currency: str = "VND"
    ) -> AIListingNormalizationResult:
        """Extracts product identity, attributes, condition, intent, and price validity."""
        pass

    @abstractmethod
    def classify_comment(
        self,
        raw_text: str
    ) -> AICommentClassificationResult:
        """Classifies comment intent and extracts referenced prices."""
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """Returns provider metrics such as token count, costs, or call stats."""
        return {
            "provider": self.provider_name,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "cost_usd": 0.0
        }
