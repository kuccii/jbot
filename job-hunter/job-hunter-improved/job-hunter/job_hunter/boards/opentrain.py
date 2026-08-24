"""OpenTrain.ai — https://www.opentrain.ai

AI training and data labeling marketplace. Lists remote gigs for RLHF,
LLM evaluation, data annotation, red teaming, and other AI training tasks.
The site is client-side rendered (Astro/Next.js) so we use Playwright to
render the JavaScript and extract job listings from the DOM.

Typical jobs: "PII Document Review Analyst", "Legal Technology Connector
Evaluation Expert", "LLM Response Evaluator", "Data Annotation Specialist".

Most gigs are project-based (not full-time employment) but pay well and
can be done from anywhere — ideal for Rwandan freelancers.
"""

from __future__ import annotations

import re

from job_hunter.boards.base import Board
from job_hunter.models import Job

# Lazy import — only used if available
_js_render = None


def _get_renderer():
    global _js_render
    if _js_render is None:
        try:
            from job_hunter.boards.js_render import render_js
            _js_render = render_js
        except ImportError:
            pass
    return _js_render


JOBS_URL = "https://www.opentrain.ai/jobs/"


class OpenTrainBoard(Board):
    """Fetches AI training gigs from opentrain.ai via Playwright."""

    name = "opentrain"
    label = "OpenTrain.ai (AI training & data labeling gigs)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        render_js = _get_renderer()
        if not render_js:
            return []

        html = await render_js(JOBS_URL, timeout_ms=45_000)
        if not html:
            return []

        return self._parse_jobs(html, limit)

    def _parse_jobs(self, html: str, limit: int) -> list[Job]:
        """Extract job listings from rendered HTML."""
        jobs: list[Job] = []

        # opentrain.ai renders job cards as <a> tags with href="/jobs/<slug>"
        # and job titles as text within the card
        # Pattern: <a href="/jobs/<slug>/"> with title text inside
        card_pattern = re.compile(
            r'<a[^>]*href="(/jobs/[^"?]+/?)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        seen_slugs: set[str] = set()
        for m in card_pattern.finditer(html):
            slug = m.group(1).rstrip("/")
            inner = m.group(2)

            # Skip apply/view buttons, only want title cards
            if any(skip in inner.lower() for skip in ["apply now", "view job", "sign up"]):
                continue

            # Skip duplicates
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            # Extract title from inner HTML — strip tags
            title = re.sub(r"<[^>]+>", " ", inner).strip()
            title = re.sub(r"\s+", " ", title)
            if not title or len(title) < 5:
                continue

            url = f"https://www.opentrain.ai{slug}/"

            # Extract domain/category from title or slug
            tags = self._extract_tags(title, slug)

            jobs.append(Job(
                title=title,
                company="OpenTrain",
                url=url,
                board=self.name,
                location="Worldwide",
                remote="Remote",
                tags=tags,
                description=f"AI training gig on OpenTrain.ai. {title}",
                posted_at="",
                eligible_countries=[],
            ))

            if len(jobs) >= limit:
                break

        return jobs

    def _extract_tags(self, title: str, slug: str) -> str:
        """Extract domain tags from title/slug."""
        tags = set()
        title_lower = title.lower()
        slug_lower = slug.lower()

        tag_keywords = {
            "rlhf": "rlhf",
            "llm": "llm",
            "evaluation": "evaluation",
            "annotation": "annotation",
            "labeling": "labeling",
            "red team": "red-teaming",
            "data": "data",
            "ai": "ai",
            "machine learning": "ml",
            "nlp": "nlp",
            "legal": "legal",
            "medical": "medical",
            "finance": "finance",
            "code": "coding",
            "coding": "coding",
            "translation": "translation",
            "writing": "writing",
            "survey": "survey",
            "review": "review",
        }

        combined = f"{title_lower} {slug_lower}"
        for keyword, tag in tag_keywords.items():
            if keyword in combined:
                tags.add(tag)

        return ",".join(sorted(tags))
