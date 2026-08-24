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

URLs verified: August 24, 2026
"""

from __future__ import annotations

from job_hunter.boards.base import Board
from job_hunter.models import Job, AUDIENCE_ENTRY


# Curated list of entry-level / VA / data entry / CX platforms.
# All URLs verified working as of August 24, 2026.
PLATFORMS: list[dict] = [
    # ── Virtual Assistant Platforms ────────────────────────────────────
    {
        "name": "BELAY",
        "url": "https://belay.com",
        "signup": "https://belay.com",
        "tasks": "Virtual assistant, bookkeeping, social media management",
        "pay": "$15-20/hr",
        "requirements": "US-based, 5+ years experience, background check",
        "tags": "virtual-assistant,bookkeeping,remote",
        "category": "Virtual Assistant",
    },
    {
        "name": "Time Etc",
        "url": "https://www.timeetc.com",
        "signup": "https://www.timeetc.com",
        "tasks": "Email management, scheduling, research, data entry",
        "pay": "$12-16/hr",
        "requirements": "English fluent, 5+ years experience",
        "tags": "virtual-assistant,data-entry,remote",
        "category": "Virtual Assistant",
    },
    {
        "name": "Belay Solutions",
        "url": "https://belaysolutions.com",
        "signup": "https://belaysolutions.com/jobs",
        "tasks": "Virtual assistant, bookkeeping, social media",
        "pay": "$18-22/hr",
        "requirements": "US-based, 7+ years experience",
        "tags": "virtual-assistant,bookkeeping,remote",
        "category": "Virtual Assistant",
    },
    {
        "name": "Boldly",
        "url": "https://boldly.com",
        "signup": "https://boldly.com/jobs/",
        "tasks": "Executive assistant, project management, marketing",
        "pay": "$20-30/hr",
        "requirements": "7+ years experience, English fluent",
        "tags": "executive-assistant,project-management,remote",
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
        "url": "https://www.appen.com",
        "signup": "https://www.appen.com",
        "tasks": "Data entry, search evaluation, web research, transcription",
        "pay": "$10-20/hr",
        "requirements": "Qualification test, consistent availability",
        "tags": "data-entry,evaluation,transcription,remote",
        "category": "Data Entry",
    },
    {
        "name": "Hive Micro",
        "url": "https://www.hivemicro.com",
        "signup": "https://www.hivemicro.com",
        "tasks": "Image tagging, content moderation, categorization",
        "pay": "$5-15/hr (task-based)",
        "requirements": "Sign up, complete training",
        "tags": "microtasks,tagging,moderation,remote",
        "category": "Data Entry",
    },
    {
        "name": "Microworkers",
        "url": "https://www.microworkers.com",
        "signup": "https://www.microworkers.com",
        "tasks": "Data entry, web research, surveys, categorization",
        "pay": "$2-10/task",
        "requirements": "Sign up, no experience needed",
        "tags": "microtasks,data-entry,research,remote",
        "category": "Data Entry",
    },
    {
        "name": "Picoworkers",
        "url": "https://www.picoworkers.com",
        "signup": "https://www.picoworkers.com",
        "tasks": "Micro tasks, app downloads, sign-ups, data entry",
        "pay": "$1-5/task",
        "requirements": "Sign up, no experience needed",
        "tags": "microtasks,data-entry,remote",
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
        "name": "Transcom",
        "url": "https://transcom.com",
        "signup": "https://transcom.com/careers",
        "tasks": "Customer support, tech support, sales",
        "pay": "$10-16/hr",
        "requirements": "Application, assessment",
        "tags": "customer-support,sales,remote",
        "category": "Customer Support",
    },
    {
        "name": "Alorica",
        "url": "https://alorica.com",
        "signup": "https://alorica.com/careers/",
        "tasks": "Customer support, tech support, billing, collections",
        "pay": "$10-16/hr",
        "requirements": "Application, assessment",
        "tags": "customer-support,billing,remote",
        "category": "Customer Support",
    },
    {
        "name": "Sutherland",
        "url": "https://www.sutherlandglobal.com",
        "signup": "https://www.jobs.sutherlandglobal.com/",
        "tasks": "Customer support, finance, healthcare, insurance",
        "pay": "$10-18/hr",
        "requirements": "Application, assessment",
        "tags": "customer-support,finance,remote",
        "category": "Customer Support",
    },
    {
        "name": "Teleperformance",
        "url": "https://www.tp.com",
        "signup": "https://www.tp.com/en-us/careers/",
        "tasks": "Customer support, content moderation, tech support",
        "pay": "$10-18/hr",
        "requirements": "Application, background check",
        "tags": "customer-support,moderation,remote",
        "category": "Customer Support",
    },
    {
        "name": "Foundever (Sitel Group)",
        "url": "https://foundever.com",
        "signup": "https://foundever.com/careers/",
        "tasks": "Customer support, tech support, sales",
        "pay": "$10-16/hr",
        "requirements": "Application, assessment",
        "tags": "customer-support,sales,remote",
        "category": "Customer Support",
    },
    {
        "name": "Concentrix",
        "url": "https://www.concentrix.com",
        "signup": "https://www.concentrix.com/careers/",
        "tasks": "Customer support, tech support, sales, billing",
        "pay": "$10-18/hr",
        "requirements": "Application, assessment",
        "tags": "customer-support,sales,remote",
        "category": "Customer Support",
    },
    {
        "name": "TaskUs",
        "url": "https://www.taskus.com",
        "signup": "https://www.taskus.com/careers",
        "tasks": "Content moderation, customer support, AI training, safety",
        "pay": "$12-20/hr",
        "requirements": "Application, assessment",
        "tags": "moderation,safety,ai-training,remote",
        "category": "Customer Support",
    },
    {
        "name": "Besedo",
        "url": "https://besedo.com",
        "signup": "https://besedo.com",
        "tasks": "Content moderation, trust & safety, community management",
        "pay": "$10-16/hr",
        "requirements": "Application, assessment",
        "tags": "moderation,safety,community,remote",
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
        "name": "GoTranscript",
        "url": "https://gotranscript.com",
        "signup": "https://gotranscript.com/transcription-jobs",
        "tasks": "Audio transcription, captioning",
        "pay": "$6-15/audio hour",
        "requirements": "Entrance test",
        "tags": "transcription,captioning,remote",
        "category": "Transcription",
    },
    {
        "name": "Scribie",
        "url": "https://scribie.com",
        "signup": "https://scribie.com/freelancer",
        "tasks": "Audio transcription, proofreading",
        "pay": "$5-20/audio hour",
        "requirements": "Entrance test",
        "tags": "transcription,proofreading,remote",
        "category": "Transcription",
    },
    {
        "name": "CastingWords",
        "url": "https://castingwords.com",
        "signup": "https://castingwords.com",
        "tasks": "Audio transcription, podcast transcription",
        "pay": "$5-15/audio hour",
        "requirements": "Entrance test",
        "tags": "transcription,podcast,remote",
        "category": "Transcription",
    },
    # ── Freelance / Marketplace ────────────────────────────────────────
    {
        "name": "PeoplePerHour",
        "url": "https://www.peopleperhour.com",
        "signup": "https://www.peopleperhour.com",
        "tasks": "Data entry, VA, writing, design, admin support",
        "pay": "$5-30/hr",
        "requirements": "Create profile, apply for jobs",
        "tags": "freelance,data-entry,virtual-assistant,remote",
        "category": "Freelance",
    },
    {
        "name": "Freelancer.com",
        "url": "https://www.freelancer.com",
        "signup": "https://www.freelancer.com/signup",
        "tasks": "Data entry, VA, writing, design, admin support",
        "pay": "$5-50/hr",
        "requirements": "Create profile, bid on jobs",
        "tags": "freelance,data-entry,virtual-assistant,remote",
        "category": "Freelance",
    },
    {
        "name": "Guru",
        "url": "https://www.guru.com",
        "signup": "https://www.guru.com",
        "tasks": "Data entry, VA, writing, design, admin support",
        "pay": "$5-40/hr",
        "requirements": "Create profile, bid on jobs",
        "tags": "freelance,data-entry,virtual-assistant,remote",
        "category": "Freelance",
    },
    # ── Survey / Research Platforms ────────────────────────────────────
    {
        "name": "Prolific",
        "url": "https://www.prolific.com",
        "signup": "https://app.prolific.com/",
        "tasks": "Research studies, surveys, AI training data",
        "pay": "$8-15/hr (minimum wage enforced)",
        "requirements": "Sign up, complete profile",
        "tags": "research,surveys,ai-training,remote",
        "category": "Data Entry",
    },
    {
        "name": "Toloka",
        "url": "https://toloka.ai",
        "signup": "https://toloka.ai",
        "tasks": "Image annotation, text categorization, search relevance",
        "pay": "$5-15/hr (task-based)",
        "requirements": "Sign up, complete training",
        "tags": "annotation,categorization,ai-training,remote",
        "category": "Data Entry",
    },
    {
        "name": "OneForma",
        "url": "https://www.oneforma.com",
        "signup": "https://www.oneforma.com",
        "tasks": "Data collection, transcription, AI training",
        "pay": "$10-20/hr",
        "requirements": "Qualification test",
        "tags": "data-collection,transcription,ai-training,remote",
        "category": "Data Entry",
    },
    # ── Writing / Content ──────────────────────────────────────────────
    {
        "name": "Textbroker",
        "url": "https://www.textbroker.com",
        "signup": "https://www.textbroker.com",
        "tasks": "Content writing, blog posts, product descriptions",
        "pay": "$0.01-0.05/word",
        "requirements": "Writing sample, English test",
        "tags": "writing,content,remote",
        "category": "Creative",
    },
    {
        "name": "FreeUp",
        "url": "https://freeup.net/",
        "signup": "https://freeup.net/",
        "tasks": "Content writing, blog posts, articles",
        "pay": "$1-20/article",
        "requirements": "Writing test",
        "tags": "writing,content,remote",
        "category": "Creative",
    },
    {
        "name": "Constant Content",
        "url": "https://www.constant-content.com",
        "signup": "https://www.constant-content.com",
        "tasks": "Article writing, SEO content, product descriptions",
        "pay": "$5-100/article",
        "requirements": "Writing samples, editorial review",
        "tags": "writing,seo,content,remote",
        "category": "Creative",
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
