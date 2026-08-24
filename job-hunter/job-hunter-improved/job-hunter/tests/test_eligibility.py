import pytest

from job_hunter.eligibility import check_eligibility, matches_keywords
from job_hunter.models import Job


def job(**kw):
    base = dict(title="Python Developer", company="Acme", url="https://x.example/1",
                board="test")
    base.update(kw)
    return Job(**base)


class TestCountryList:
    def test_rwanda_in_list(self):
        ok, note = check_eligibility(job(eligible_countries=["Kenya", "Rwanda", "Uganda"]))
        assert ok

    def test_kenya_in_list(self):
        ok, note = check_eligibility(job(eligible_countries=["Kenya"]))
        assert ok

    def test_neither_rwanda_nor_kenya_missing(self):
        ok, note = check_eligibility(job(eligible_countries=["Ghana", "Nigeria"]))
        assert not ok
        assert "restricts" in note

    def test_africa_region_includes_rwanda(self):
        ok, note = check_eligibility(job(eligible_countries=["Africa"]))
        assert ok

    def test_east_africa_region_includes_rwanda(self):
        ok, _ = check_eligibility(job(eligible_countries=["East Africa"]))
        assert ok

    def test_empty_list_remote4africa_is_open(self):
        ok, _ = check_eligibility(job(board="remote4africa", eligible_countries=[]))
        assert ok


class TestLocationHeuristics:
    @pytest.mark.parametrize("loc,remote", [
        ("Anywhere in the World", "Remote"),
        ("🌏", ""),
        ("Worldwide", "Remote"),
        ("Remote - Global", ""),
        ("Africa", "Remote"),
        ("East Africa", ""),
        ("Kigali, Rwanda", ""),
        ("Nairobi, Kenya", ""),
        ("Nairobi, Kenya (East Africa)", "Remote"),
        ("Kenya", "Remote"),
        ("", "100% Remote"),
    ])
    def test_eligible(self, loc, remote):
        ok, note = check_eligibility(job(location=loc, remote=remote))
        assert ok, (loc, remote, note)

    @pytest.mark.parametrize("loc,remote", [
        ("USA only", "Remote"),
        ("United States", ""),
        ("Europe", "Remote"),
        ("UK only", "Remote"),
        ("Canada", "Remote"),
        ("Hybrid - New York", ""),
        ("Onsite - Lagos", ""),
        ("North York, Ontario", ""),
    ])
    def test_not_eligible(self, loc, remote):
        ok, note = check_eligibility(job(location=loc, remote=remote))
        assert not ok, (loc, remote, note)

    def test_unknown_location_not_eligible(self):
        ok, _ = check_eligibility(job(location="", remote="", board="weworkremotely"))
        assert not ok


class TestATSPatterns:
    """Direct company postings (Greenhouse/Ashby/SmartRecruiters) use
    locations like "Remote, Italy" or "New York" with a remote flag —
    the remote word must not grant worldwide status when a place is named."""

    @pytest.mark.parametrize("loc,remote", [
        ("Remote, Italy", "Remote"),
        ("Remote - US", ""),
        ("Remote (UK)", ""),
        ("Remote, Bangalore", "Remote"),
        ("New York, New York", "Remote"),
        ("APAC", "Remote"),
        ("San Francisco, California", "Remote"),
        ("Cardiff, London or Remote (UK)", ""),
    ])
    def test_remote_with_specific_place_not_eligible(self, loc, remote):
        ok, note = check_eligibility(job(board="ats", location=loc, remote=remote))
        assert not ok, (loc, remote, note)

    @pytest.mark.parametrize("loc,remote", [
        ("Remote", ""),
        ("Remote, Worldwide", "Remote"),
        ("Remote - Global", ""),
        ("EMEA", "Remote"),
        ("Remote, EMEA", ""),
        ("Africa", "Remote"),
        ("East Africa", ""),
    ])
    def test_remote_with_worldwide_or_africa_eligible(self, loc, remote):
        ok, note = check_eligibility(job(board="ats", location=loc, remote=remote))
        assert ok, (loc, remote, note)

    def test_kenya_location_is_eligible(self):
        # A role mentioning Kenya is eligible (Kenya and Rwanda are both
        # target markets for this tool).
        ok, note = check_eligibility(job(board="ats", location="Remote, Kenya", remote="Remote"))
        assert ok

    def test_kenya_only_country_in_list_eligible(self):
        ok, note = check_eligibility(job(board="ats", eligible_countries=["Kenya"]))
        assert ok


class TestRemoteOKBoard:
    """RemoteOK's feed mixes in physical/onsite roles, so bare cities are not
    eligible — only remote/worldwide signals or empty locations pass."""

    def test_city_only_location_is_not_eligible(self):
        ok, _ = check_eligibility(job(board="remoteok", location="New York City"))
        assert not ok

    def test_empty_location_is_eligible(self):
        ok, _ = check_eligibility(job(board="remoteok", location=""))
        assert ok

    def test_worldwide_remote_is_eligible(self):
        ok, _ = check_eligibility(job(board="remoteok", location="🌏"))
        assert ok

    def test_usa_restricted_remote_is_not_eligible(self):
        ok, _ = check_eligibility(job(board="remoteok", location="Select USA Remote Locations"))
        assert not ok

    def test_hybrid_is_not_eligible(self):
        ok, _ = check_eligibility(job(board="remoteok", location="Hybrid - London"))
        assert not ok


class TestGenericTitleRejection:
    """Generic postings (not real jobs) should be rejected."""

    @pytest.mark.parametrize("title", [
        "General Application",
        "General Upwork Application",
        "Join Our Talent Community",
        "Campus Crew Ambassador (Student Program)",
        "Diversity Internship Program",
        "Early Career - Software Engineer",
    ])
    def test_generic_titles_rejected(self, title):
        ok, note = check_eligibility(job(title=title, location="Remote"))
        assert not ok, (title, note)
        assert "generic" in note.lower()


class TestTitleRegionRestriction:
    """Title with region codes should be rejected."""

    @pytest.mark.parametrize("title", [
        "Customer Solution Architect (AMER)",
        "Director of Product Marketing - USA",
        "Account Executive - EMEA",
        "Backend Engineer (APAC)",
        "Sales Manager - UK Only",
        "Product Manager (EU Only)",
    ])
    def test_region_in_title_rejected(self, title):
        ok, note = check_eligibility(job(title=title, location="Remote"))
        assert not ok, (title, note)
        assert "region restriction" in note.lower()


class TestDescriptionRestrictions:
    """Hidden timezone/region restrictions in descriptions should be caught."""

    @pytest.mark.parametrize("desc", [
        "Must work US hours and overlap with Eastern Time zone.",
        "Available during US business hours (9am-5pm Pacific Time).",
        "We need overlap with North American business hours.",
        "This role requires working US timezone hours.",
        "Must be available during Eastern Standard Time.",
    ])
    def test_timezone_restrictions_rejected(self, desc):
        ok, note = check_eligibility(
            job(title="Software Engineer", location="Remote", description=desc)
        )
        assert not ok, (desc[:50], note)
        assert "timezone" in note.lower()

    @pytest.mark.parametrize("desc", [
        "Preference towards candidates based in San Francisco.",
        "We prefer candidates located in London.",
        "Strong preference for candidates in the United States.",
        "We are only hiring in the US.",
        "Ideally based in Berlin.",
    ])
    def test_preference_phrases_rejected(self, desc):
        ok, note = check_eligibility(
            job(title="Software Engineer", location="Remote", description=desc)
        )
        assert not ok, (desc[:50], note)
        assert "preference" in note.lower() or "region" in note.lower()

    def test_clean_description_passes(self):
        ok, _ = check_eligibility(
            job(title="Software Engineer", location="Remote",
                description="We are a remote-first company. Build great products.")
        )
        assert ok


class TestKeywords:
    def test_match(self):
        assert matches_keywords(job(tags="python, ai"), ["python"])

    def test_no_match(self):
        assert not matches_keywords(job(title="Barista", description="Coffee"), ["python"])

    def test_empty_keywords_matches_all(self):
        assert matches_keywords(job(), [])
