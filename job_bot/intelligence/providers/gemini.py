import httpx
from job_bot.intelligence.providers.base import LLMProvider


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str = "gemini-1.5-flash", api_key: str = "", **kwargs):
        self.model = model
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def generate(self, prompt: str, system: str | None = None) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            contents = []
            if system:
                contents.append({"role": "user", "parts": [{"text": system}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})
            resp = await client.post(
                f"{self.base_url}/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json={"contents": contents},
            )
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                return parts[0].get("text", "") if parts else ""
            return ""

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/models/text-embedding-004:embedContent",
                params={"key": self.api_key},
                json={"content": {"parts": [{"text": text}]}},
            )
            return resp.json().get("embedding", {}).get("values", [])

    async def is_available(self) -> bool:
        return bool(self.api_key)
