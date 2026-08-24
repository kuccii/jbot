"""AI Training & Gig Platforms aggregator.

Major AI training platforms where workers earn money by doing RLHF, data
labeling, annotation, and other AI training tasks. These are NOT traditional
job boards — you sign up, qualify via a screening test, then get tasks.

The board generates entries for each platform with direct sign-up links.
Workers can then register and start earning. Platforms are curated for:
  - Legitimacy (pay reliably)
  - Remote accessibility (work from Rwanda)
  - Reasonable pay rates ($15-50+/hour for skilled tasks)

Platforms are NOT scraped — they require authentication. Instead, we
provide structured info cards with sign-up URLs.
"""

from __future__ import annotations

from job_hunter.boards.base import Board
from job_hunter.models import Job


# Curated list of legitimate gig platforms with direct sign-up links.
# Updated: August 2026
PLATFORMS: list[dict] = [
    {
        "name": "Outlier (formerly Remotasks)",
        "url": "https://outlier.ai",
        "signup": "https://app.outlier.ai",
        "tasks": "RLHF, code editing, math, writing, image annotation",
        "pay": "$15-50/hr depending on task and expertise",
        "requirements": "Qualification test, domain expertise",
        "tags": "rlhf,annotation,ai,remote",
    },
    {
        "name": "Scale AI (Remotasks)",
        "url": "https://scale.com",
        "signup": "https://app.scale.com",
        "tasks": "Data labeling, RLHF, prompt engineering, code review",
        "pay": "$15-40/hr depending on task",
        "requirements": "Qualification test",
        "tags": "rlhf,labeling,ai,remote",
    },
    {
        "name": "DataAnnotation.tech",
        "url": "https://www.dataannotation.tech",
        "signup": "https://www.dataannotation.tech",
        "tasks": "Code evaluation, writing, RLHF, prompt engineering",
        "pay": "$15-25/hr for coding, $15-20/hr for writing",
        "requirements": "Qualification test (coding or writing)",
        "tags": "coding,writing,rlhf,ai,remote",
    },
    {
        "name": "Alignerr",
        "url": "https://www.alignerr.com",
        "signup": "https://www.alignerr.com",
        "tasks": "Domain expert tasks (math, science, law, finance)",
        "pay": "$20-50+/hr for specialized domains",
        "requirements": "Domain expertise, qualification test",
        "tags": "domain-expert,math,science,finance,remote",
    },
    {
        "name": "Telus International (formerly Lionbridge)",
        "url": "https://www.telusinternational.com",
        "signup": "https://www.telusinternational.com/ai-community",
        "tasks": "Search evaluation, data annotation, AI training",
        "pay": "$12-20/hr",
        "requirements": "Qualification test, consistent availability",
        "tags": "annotation,search-evaluation,ai,remote",
    },
    {
        "name": "Toloka",
        "url": "https://toloka.ai",
        "signup": "https://www.toloka.ai",
        "tasks": "Image annotation, text categorization, search relevance",
        "pay": "$5-15/hr (task-based)",
        "requirements": "Sign up, complete training",
        "tags": "annotation,categorization,ai,remote",
    },
    {
        "name": "Prolific",
        "url": "https://www.prolific.co",
        "signup": "https://app.prolific.co",
        "tasks": "Research studies, surveys, AI training data",
        "pay": "$8-15/hr (minimum wage enforced)",
        "requirements": "Sign up, complete profile",
        "tags": "research,surveys,ai,remote",
    },
    {
        "name": "Appen",
        "url": "https://appen.com",
        "signup": "https://appen.com/ai-community",
        "tasks": "Search evaluation, social media evaluation, transcription",
        "pay": "$10-20/hr",
        "requirements": "Qualification test",
        "tags": "evaluation,transcription,ai,remote",
    },
    {
        "name": "LXT (formerly Clickworker)",
        "url": "https://lxt.ai",
        "signup": "https://lxt.ai",
        "tasks": "Data collection, web research, categorization",
        "pay": "$8-15/hr",
        "requirements": "Sign up, complete profile",
        "tags": "data-collection,research,remote",
    },
    {
        "name": "OneForma",
        "url": "https://www.oneforma.com",
        "signup": "https://www.oneforma.com",
        "tasks": "Data collection, transcription, AI training",
        "pay": "$10-20/hr",
        "requirements": "Qualification test",
        "tags": "data-collection,transcription,ai,remote",
    },
    {
        "name": "ModSquad",
        "url": "https://www.modsquad.com",
        "signup": "https://www.modsquad.com",
        "tasks": "Content moderation, customer support, community management",
        "pay": "$12-18/hr",
        "requirements": "Application, interview",
        "tags": "moderation,support,community,remote",
    },
    {
        "name": "Surge AI",
        "url": "https://www.surgehq.ai",
        "signup": "https://www.surgehq.ai",
        "tasks": "AI training, data labeling, prompt engineering",
        "pay": "$15-30/hr",
        "requirements": "Qualification test",
        "tags": "ai-training,labeling,remote",
    },
]


class GigPlatformsBoard(Board):
    """Aggregates AI training and gig platform sign-up links."""

    name = "gig_platforms"
    label = "AI Training & Gig Platforms (Outlier, Scale, DataAnnotation, etc.)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        jobs: list[Job] = []

        for platform in PLATFORMS[:limit]:
            jobs.append(Job(
                title=f"{platform['name']} — {platform['tasks'][:50]}",
                company=platform["name"],
                url=platform["signup"],
                board=self.name,
                location="Worldwide",
                remote="Remote",
                tags=platform["tags"],
                description=(
                    f"Platform: {platform['name']}\\n"
                    f"Tasks: {platform['tasks']}\\n"
                    f"Pay: {platform['pay']}\\n"
                    f"Requirements: {platform['requirements']}\\n"
                    f"Website: {platform['url']}"
                ),
                posted_at="",
                eligible_countries=[],
            ))

        return jobs
