from job_bot.intelligence.providers.base import LLMProvider


class Drafter:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate_cover_letter(
        self, profile: str, opportunity_title: str, company: str, skills: list[str]
    ) -> str:
        prompt = f"""Write a professional cover letter for:

Position: {opportunity_title}
Company: {company}
Key Skills: {', '.join(skills)}
Background: {profile[:500]}

Write 3-4 paragraphs. Be specific about relevant experience. Keep it concise."""
        return await self.provider.generate(prompt)
