from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

def get_llm(temperature: float = 0.0):
    """
    Returns a configured Gemini model instance.
    Temperature is 0.0 by default for deterministic code generation.
    """
    return ChatGoogleGenerativeAI(
        model=settings.MODEL_NAME,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
        # Safety settings can be adjusted here if code triggers filters
    )