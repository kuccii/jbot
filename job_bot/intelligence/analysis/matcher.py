import json

from job_bot.intelligence.providers.base import LLMProvider
from job_bot.utils.logging import get_logger

logger = get_logger()

FALLBACK_SCORES = {
    "cv_match": 50, "compensation": 50, "culture": 50,
    "red_flags": 50, "legitimacy": 50, "global": 50,
    "prose": "Score parsing failed. Manual review recommended.",
    "composite": 50,
}

SCORING_PROMPT = """Rate this opportunity across 6 dimensions.
Return ONLY valid JSON with these keys (no markdown, no explanation):

{{
  "cv_match": <0-100 how well does the profile match the requirements>,
  "compensation": <0-100 how competitive is the pay/benefits>,
  "culture": <0-100 how well does the company culture fit>,
  "red_flags": <0-100 how many red flags (inverted: 0=many flags, 100=clean)>,
  "legitimacy": <0-100 how legitimate/verifiable is this opportunity>,
  "global": <0-100 how accessible is this for global applicants. If location is
            a specific city/country that is hard to get a work visa for (US, UK, EU, Canada, etc.),
            score this LOW. If fully remote with no location restriction, score HIGH.>,
  "prose": "<2-3 sentence summary of why or why not, noting any location restrictions>"
}}

PROFILE:
{profile}

OPPORTUNITY:
{opportunity}
"""


class Matcher:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def score(self, profile_text: str, opportunity_text: str, category: str = "job") -> dict:
        prompt = SCORING_PROMPT.format(
            profile=profile_text[:2000],
            opportunity=opportunity_text[:2000],
        )
        result = await self.provider.generate(
            prompt,
            system="You are a career opportunity evaluator. Return JSON only.",
        )
        try:
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                cleaned = cleaned.rsplit("```", 1)[0].strip()
            scores = json.loads(cleaned)
            required = {"cv_match", "compensation", "culture", "red_flags", "legitimacy", "global", "prose"}
            if not required.issubset(scores.keys()):
                raise ValueError(f"Missing keys: {required - scores.keys()}")
            for k in required - {"prose"}:
                scores[k] = max(0, min(100, int(scores[k])))
            scores["composite"] = sum(scores[k] for k in required - {"prose"}) // 6
            return scores
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("score_parse_failed", error=str(e), raw=result[:200])
            return dict(FALLBACK_SCORES)
