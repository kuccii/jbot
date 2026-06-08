from job_bot.intelligence.providers.base import LLMProvider


class Matcher:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def score(self, profile_text: str, opportunity_text: str) -> float:
        prompt = f"""Rate the fit (0-100) between this profile and job opportunity.

PROFILE:
{profile_text[:1500]}

OPPORTUNITY:
{opportunity_text[:1500]}

Return ONLY a number between 0 and 100 representing how well this profile matches."""
        result = await self.provider.generate(prompt)
        try:
            return min(100, max(0, float(result.strip()))) / 100
        except (ValueError, TypeError):
            return 0.0
