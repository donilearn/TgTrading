import os

from google import genai

from config.settings import Settings


class GeminiClient:
    """Gemini — zaxira tahlil va audio/video parser."""

    def __init__(self, settings: Settings) -> None:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
        self._client = genai.Client()
        self._model = settings.gemini_model

    @property
    def client(self) -> genai.Client:
        return self._client

    @property
    def model(self) -> str:
        return self._model
