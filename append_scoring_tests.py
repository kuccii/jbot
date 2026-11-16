#!/usr/bin/env python3
"""Append TestAudienceRankers to test_scoring.py."""

TEST_CONTENT = '''from job_hunter.config import Config
from job_hunter.scoring import score_entry, score_tech, score_visa, score_for_audience


class TestAudienceRankers:
    def test_role_family_raises_tech_score(self):
        j = make_job(title="Software Engineer")
        plain, _ = score_tech(j, skills=[], role_families=None)
        ranked, reasons = score_tech(j, skills=[], role_families=["engineer", "developer"])
        assert ranked > plain
        assert "role family" in reasons

    def test_entry_scores_above_zero_without_any_skills(self):
        j = make_job(title="Virtual Assistant")
        j.board = "indeed_search"
        score, reasons = score_entry(j, Config())
        assert score > 0
        assert reasons

    def test_entry_ranks_known_platform_higher(self):
        a = make_job(title="Virtual Assistant"); a.board = "entry_platforms"
        b = make_job(title="Virtual Assistant"); b.board = "some_unknown_board"
        assert score_entry(a, Config())[0] > score_entry(b, Config())[0]

    def test_visa_rewards_explicit_sponsorship(self):
        j = make_job(title="Backend Engineer",
                     description="We provide visa sponsorship and relocation.")
        j.company = "Acme"
        score, reasons = score_visa(j, skills=[], role_families=["engineer"])
        assert score > 0
        assert "sponsorship" in reasons

    def test_dispatch_matches_direct_call(self):
        cfg = Config()
        j = make_job(title="Software Engineer"); j.company = "Acme"
        assert score_for_audience(j, "tech", cfg) == score_tech(
            j, cfg.profile.skills, cfg.profile.seniority, cfg.audiences.tech.title_allow)
'''

with open(r'C:\Users\impat\OneDrive\Documents\GitHub\JBot\job-hunter\tests\test_scoring.py', 'a', encoding='utf-8') as f:
    f.write(TEST_CONTENT)
print('Appended successfully')