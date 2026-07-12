from functools import lru_cache

from app.ai.gemini import GeminiProvider
from app.ai.provider import AIProvider


@lru_cache
def get_ai_provider() -> AIProvider:
    return GeminiProvider()
