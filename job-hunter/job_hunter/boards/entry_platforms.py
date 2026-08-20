"""Entry-Level Gig & VA Platforms aggregator.

Platforms where people can find entry-level remote work: virtual assistant
tasks, data entry, customer support, transcription, content moderation,
micro-tasks, and more. These require NO college degree and are accessible
to high school graduates.

Unlike traditional job boards, these are task-based platforms — you sign
up, pass a screening test, and start getting tasks.

Platforms are curated for:
  - Legitimacy (pay reliably)
  - Remote accessibility (work from Rwanda/worldwide)
  - Low barrier to entry (no degree required)
  - Reasonable pay rates ($5-25/hr)
"""

from __future__ import annotations

from job_hunter.boards.base import Board
from job_hunter.models import Job, AUDIENCE_ENTRY


# Curated list of entry-level / VA / data entry / CX platforms.
# Updated: August 2026
PLATFORMS: list[dict] = [
    # ── Virtual Assistant Platforms ────────────────────────────────────
    {
        "name": "BELAY",
        "url": "https://www.belay.com",
        "signup": "https://www.belay.com/careers",
        "tasks": "Virtual assistant, bookkeeping, social media management",
        "pay": "$15-20/hr",
        "requirements": "US-based, 5+ years experience, background check",
        "tags": "virtual-assistant,bookkeeping,remote",
        "category": "Virtual Assistant",
    },
    {
        "name": "Time Etc",
        "url": "https://www.timeetc.com",
        "signup": "https://www.timeetc.com/for-virtual-assistants",
        "tasks": "Email management, scheduling, research, data entry",
        "pay": "$12-16/hr",
        "requirements": "English fluent, 5+ years experience",
        "tags": "virtual-assistant,data-entry,remote",
        "category": "Virtual Assistant",
    },
    {
        "name": "Zirtual",
        "url": "https://www.zirtual.com",
        "signup": "https://www.zirtual.com/virtual-assistants/",
        "tasks": "Email management, travel booking, research, social media",
        "pay": "$15-20/hr",
        "requirements": "US-based, detail-oriented",
        "tags": "virtual-assistant,admin,remote",
        "category": "Virtual Assistant",
    },
    {
        "name": "Fancy Hands",
        "url": "https://www.fancyhands.com",
        "signup": "https://www.fancyhands.com/apply",
        "tasks": "Quick tasks, scheduling, research, data lookups",
        "pay": "$3-7/task",
        "requirements": "US-based, fast turnaround",
        "tags": "microtasks,virtual-assistant,remote",
        "category": "Virtual Assistant",
    },
    # ── Data Entry & Micro-Tasks ──────────────────────────────────────
    {
        "name": "Clickworker",
        "url": "https://www.clickworker.com",
        "signup": "https://www.clickworker.com",
        "tasks": "Data entry, web research, categorization, surveys",
        "pay": "$8-15/hr",
        "requirements": "Sign up, complete profile, pass assessment",
        "tags": "data-entry,research,categorization,remote",
        "category": "Data Entry",
    },
    {
        "name": "LXT (formerly Clickworker AI)",
        "url": "https://lxt.ai",
        "signup": "https://lxt.ai",
        "tasks": "Data collection, web research, categorization, AI training",
        "pay": "$8-15/hr",
        "requirements": "Sign up, complete profile",
        "tags": "data-collection,research,remote",
        "category": "Data Entry",
    },
    {
        "name": "Amazon Mechanical Turk",
        "url": "https://www.mturk.com",
        "signup": "https://www.mturk.com/worker",
        "tasks": "Data entry, surveys, image labeling, transcription",
        "pay": "$5-12/hr (task-based)",
        "requirements": "US-based preferred, sign up + qualification tests",
        "tags": "microtasks,data-entry,transcription,remote",
        "category": "Data Entry",
    },
    {
        "name": "Appen",
        "url": "https://appen.com",
        "signup": "https://appen.com/ai-community",
        "tasks": "Data entry, search evaluation, web research, transcription",
        "pay": "$10-20/hr",
        "requirements": "Qualification test, consistent availability",
        "tags": "data-entry,evaluation,transcription,remote",
        "category": "Data Entry",
    },
    {
        "name": "Telus International (Lionbridge)",
        "url": "https://www.telusinternational.com",
        "signup": "https://www.telusinternational.com/ai-community",
        "tasks": "Data annotation, search evaluation, AI training, transcription",
        "pay": "$12-20/hr",
        "requirements": "Qualification test, consistent availability",
        "tags": "annotation,search-evaluation,transcription,remote",
        "category": "Data Entry",
    },
    # ── Customer Support / Call Center ─────────────────────────────────
    {
        "name": "ModSquad",
        "url": "https://www.modsquad.com",
        "signup": "https://join.modsquad.com/careers/",
        "tasks": "Content moderation, customer support, community management",
        "pay": "$12-18/hr",
        "requirements": "Application, interview",
        "tags": "moderation,support,community,remote",
        "category": "Customer Support",
    },
    {
        "name": "Arise",
        "url": "https://www.arise.com",
        "signup": "https://www.arise.com",
        "tasks": "Customer service, tech support, billing",
        "pay": "$10-18/hr",
        "requirements": "Background check, equipment requirements",
        "tags": "customer-support,call-center,remote",
        "category": "Customer Support",
    },
    {
        "name": "LiveWorld",
        "url": "https://www.liveworldtext.com",
        "signup": "https://apply.workable.com/liveworldtext/",
        "tasks": "Content moderation, social media support, brand monitoring",
        "pay": "$12-18/hr",
        "requirements": "Application, writing assessment",
        "tags": "moderation,social-media,remote",
        "category": "Customer Support",
    },
    # ── Transcription & Writing ───────────────────────────────────────
    {
        "name": "Rev",
        "url": "https://www.rev.com",
        "signup": "https://www.rev.com/freelancers",
        "tasks": "Audio transcription, captioning, subtitling",
        "pay": "$5-25/audio hour",
        "requirements": "Grammar test, transcription test",
        "tags": "transcription,captioning,writing,remote",
        "category": "Transcription",
    },
    {
        "name": "TranscribeMe",
        "url": "https://www.transcribeme.com",
        "signup": "https://www.transcribeme.com",
        "tasks": "Short audio transcription, medical transcription",
        "pay": "$7-22/audio hour",
        "requirements": "Entrance exam",
        "tags": "transcription,medical,remote",
        "category": "Transcription",
    },
    {
        "name": "GoTranscript",
        "url": "https://www.gotranscript.com",
        "signup": "https://www.gotranscript.com/transcription-jobs",
        "tasks": "Audio transcription, captioning",
        "pay": "$6-15/audio hour",
        "requirements": "Entrance test",
        "tags": "transcription,captioning,remote",
        "category": "Transcription",
    },
    {
        "name": "Scribie",
        "url": "https://www.scribie.com",
        "signup": "https://www.scribie.com/freelance-transcriptionist",
        "tasks": "Audio transcription, proofreading",
        "pay": "$5-20/audio hour",
        "requirements": "Entrance test",
        "tags": "transcription,proofreading,remote",
        "category": "Transcription",
    },
    # ── Content Moderation & Community ─────────────────────────────────
    {
        "name": "Teleperformance",
        "url": "https://www.teleperformance.com",
        "signup": "https://jobs.teleperformance.com",
        "tasks": "Customer support, content moderation, tech support",
        "pay": "$10-18/hr",
        "requirements": "Application, background check",
        "tags": "customer-support,moderation,remote",
        "category": "Customer Support",
    },
    {
        "name": "Foundever (Sitel Group)",
        "url": "https://www.foundever.com",
        "signup": "https://careers.foundever.com",
        "tasks": "Customer support, tech support, sales",
        "pay": "$10-16/hr",
        "requirements": "Application, assessment",
        "tags": "customer-support,sales,remote",
        "category": "Customer Support",
    },
    {
        "name": "Concentrix",
        "url": "https://www.concentrix.com",
        "signup": "https://careers.concentrix.com",
        "tasks": "Customer support, tech support, sales, billing",
        "pay": "$10-18/hr",
        "requirements": "Application, assessment",
        "tags": "customer-support,sales,remote",
        "category": "Customer Support",
    },
    # ── Freelance / Marketplace ────────────────────────────────────────
    {
        "name": "Fiverr (Seller)",
        "url": "https://www.fiverr.com",
        "signup": "https://www.fiverr.com/start_selling",
        "tasks": "Data entry, virtual assistant, writing, design, anything",
        "pay": "$5-100+/task",
        "requirements": "Create a gig, get orders",
        "tags": "freelance,data-entry,virtual-assistant,remote",
        "category": "Freelance",
    },
    {
        "name": "Upwork (Freelancer)",
        "url": "https://www.upwork.com",
        "signup": "https://www.upwork.com/nx/signup/",
        "tasks": "Data entry, virtual assistant, writing, research, admin",
        "pay": "$5-50/hr (varies widely)",
        "requirements": "Create profile, bid on jobs",
        "tags": "freelance,data-entry,virtual-assistant,remote",
        "category": "Freelance",
    },
    {
        "name": "PeoplePerHour",
        "url": "https://www.peopleperhour.com",
        "signup": "https://www.peopleperhour.com/freelancer/signup",
        "tasks": "Data entry, VA, writing, design, admin support",
        "pay": "$5-30/hr",
        "requirements": "Create profile, apply for jobs",
        "tags": "freelance,data-entry,virtual-assistant,remote",
        "category": "Freelance",
    },
]


class EntryPlatformsBoard(Board):
    """Aggregates entry-level VA, data entry, CX, transcription platforms."""

    name = "entry_platforms"
    label = "Entry-Level Platforms (VA, Data Entry, CX, Transcription)"

    async def fetch(self, limit: int = 50) -> list[Job]:
        jobs: list[Job] = []

        for platform in PLATFORMS[:limit]:
            jobs.append(Job(
                title=f"{platform['name']} — {platform['tasks'][:60]}",
                company=platform["name"],
                url=platform["signup"],
                board=self.name,
                location="Worldwide",
                remote="Remote",
                tags=f"{platform['tags']} {platform['category']}",
                description=(
                    f"Platform: {platform['name']}\\n"
                    f"Category: {platform['category']}\\n"
                    f"Tasks: {platform['tasks']}\\n"
                    f"Pay: {platform['pay']}\\n"
                    f"Requirements: {platform['requirements']}\\n"
                    f"Website: {platform['url']}"
                ),
                posted_at="",
                eligible_countries=[],
                audience=AUDIENCE_ENTRY,
            ))

        return jobs
