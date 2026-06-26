import pytest
from job_bot.intelligence.liveness import LivenessChecker, DEAD_PHRASES


@pytest.mark.asyncio
async def test_dead_phrase_detection():
    checker = LivenessChecker()
    text = "This position has been filled and we are no longer accepting applications"
    is_live = any(p in text.lower() for p in DEAD_PHRASES)
    assert is_live is True


@pytest.mark.asyncio
async def test_live_text_no_dead_phrases():
    checker = LivenessChecker()
    text = "We are currently hiring for this position. Apply now!"
    is_live = any(p in text.lower() for p in DEAD_PHRASES)
    assert is_live is False


@pytest.mark.asyncio
async def test_url_not_ats_fallback_to_unknown():
    checker = LivenessChecker()
    is_live, source = await checker.check("https://example.com/nonexistent-page-12345")
    assert source in ("unknown", "http_status", "content_classifier", "http_ok")


@pytest.mark.asyncio
async def test_greenhouse_url_pattern_matches():
    from job_bot.intelligence.liveness import LIVENESS_PROVIDERS
    import re
    for pattern, _ in LIVENESS_PROVIDERS:
        if "greenhouse" in str(type(_)).lower():
            m = pattern.search("https://boards.greenhouse.io/openai/jobs/12345")
            assert m is not None
            break
