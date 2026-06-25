from job_bot.intelligence.providers.base import LLMProvider


class Drafter:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate_cover_letter(
        self, profile: str, opportunity_title: str, company: str, skills: list[str],
        category: str = "job",
    ) -> str:
        prompts = {
            "job": f"""Write a professional cover letter for:

Position: {opportunity_title}
Company: {company}
Key Skills: {', '.join(skills)}
Background: {profile[:500]}

Write 3-4 paragraphs. Be specific about relevant experience. Keep it concise.""",
            "startup": f"""Write a compelling pitch / application message for this startup program:

Program: {opportunity_title}
Organization: {company}
Key Skills: {', '.join(skills)}
Background: {profile[:500]}

Write 2-3 paragraphs explaining why the founder is a great fit, what they bring, and what they hope to gain. Keep it concise and enthusiastic.""",
            "grant": f"""Write a strong grant proposal / personal statement for this fellowship or grant:

Grant: {opportunity_title}
Organization: {company}
Key Skills: {', '.join(skills)}
Background: {profile[:500]}

Write 3-4 paragraphs. Explain why the applicant is eligible, the impact they will create, and how the grant will help. Keep it focused on eligibility criteria.""",
        }
        prompt = prompts.get(category, prompts["job"])
        return await self.provider.generate(prompt)
