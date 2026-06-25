from job_bot.intelligence.providers.base import LLMProvider


class Matcher:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def score(self, profile_text: str, opportunity_text: str, category: str = "job") -> float:
        prompts = {
            "job": f"""Rate the fit (0-100) between this profile and job opportunity.

PROFILE:
{profile_text[:1500]}

OPPORTUNITY:
{opportunity_text[:1500]}

Return ONLY a number between 0 and 100 representing how well this profile matches the job requirements.""",
            "startup": f"""Rate the fit (0-100) between this profile and startup program.

PROFILE:
{profile_text[:1500]}

PROGRAM:
{opportunity_text[:1500]}

Return ONLY a number between 0 and 100 representing how well this profile fits the startup program's eligibility and the founder's background.""",
            "grant": f"""Rate the fit (0-100) between this profile and grant/fellowship opportunity.

PROFILE:
{profile_text[:1500]}

GRANT DETAILS:
{opportunity_text[:1500]}

Return ONLY a number between 0 and 100 representing how well this profile matches the grant's eligibility criteria and focus area.""",
        }
        prompt = prompts.get(category, prompts["job"])
        result = await self.provider.generate(prompt)
        try:
            return min(100, max(0, float(result.strip()))) / 100
        except (ValueError, TypeError):
            return 0.0
