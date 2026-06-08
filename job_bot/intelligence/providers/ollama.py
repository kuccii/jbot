import httpx
from job_bot.intelligence.providers.base import LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def generate(self, prompt: str, system: str | None = None) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            payload = {"model": self.model, "prompt": prompt, "stream": False}
            if system:
                payload["system"] = system
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            return resp.json().get("response", "")

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            return resp.json().get("embedding", [])

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
