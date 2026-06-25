import httpx
from job_bot.intelligence.providers.base import LLMProvider


class NimProvider(LLMProvider):
    name = "nim"

    def __init__(self, model: str = "meta/llama3-70b-instruct", api_key: str = "", base_url: str = "https://api.nvcf.nvidia.com/v2/llm"):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    async def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "input": text},
            )
            data = resp.json()
            return data.get("data", [{}])[0].get("embedding", [])

    async def is_available(self) -> bool:
        return bool(self.api_key)
