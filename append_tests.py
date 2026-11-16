#!/usr/bin/env python3
"""Append TestCityNameLeak and TestVisaSponsorshipSignal to test_eligibility.py."""

TEST_CONTENT = '''

class TestCityNameLeak:
    """A bare 'Remote' must not grant worldwide status when the title or
    description names a specific city (the Ciudad de México leak)."""

    @pytest.mark.parametrize("title,desc", [
        ("Remote Recruiter - Ciudad de México, CDMX", ""),
        ("Customer Support (Mexico City)", ""),
        ("Software Engineer", "Our team is based in Bangalore, India."),
        ("Data Analyst", "This role is in Toronto."),
    ])
    def test_named_city_rejected(self, title, desc):
        ok, note = check_eligibility(job(title=title, location="Remote", description=desc))
        assert not ok, (title, note)

    def test_africa_city_still_eligible(self):
        ok, _ = check_eligibility(job(title="Engineer", location="Remote",
                                      description="Our office is in Kigali, Rwanda."))
        assert ok


class TestVisaSponsorshipSignal:
    def test_signal_detected_regardless_of_board(self):
        from job_hunter.eligibility import has_visa_sponsorship
        ok, note = has_visa_sponsorship(
            job(title="Backend Engineer", board="himalayas",
                description="We provide visa sponsorship and relocation support.")
        )
        assert ok

    def test_no_signal_is_false(self):
        from job_hunter.eligibility import has_visa_sponsorship
        ok, _ = has_visa_sponsorship(job(title="Backend Engineer", board="himalayas",
                                        description="Remote role."))
        assert not ok
'''

with open(r'C:\Users\impat\OneDrive\Documents\GitHub\JBot\job-hunter\tests\test_eligibility.py', 'a', encoding='utf-8') as f:
    f.write(TEST_CONTENT)
print('Appended successfully')