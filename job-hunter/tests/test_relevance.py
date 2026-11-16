from job_hunter.config import Config
from job_hunter.models import Job
from job_hunter import relevance

LONG = "We build products for teams worldwide. " * 3


def job(**kw):
    base = dict(title="Software Engineer", company="Acme", url="https://x/1",
                board="himalayas", location="Remote", remote="Remote",
                description=LONG, tags="")
    base.update(kw)
    return Job(**base)


def classify(j, cfg=None):
    return relevance.classify(j, cfg or Config())


def test_wrong_country_recruiter_is_dropped():
    c = classify(job(title="Remote Recruiter",
                     description="Based in Ciudad de Mexico, CDMX. " + LONG))
    assert c.audience is None


def test_real_tech_role_routes_to_tech():
    c = classify(job(title="Senior Software Engineer"))
    assert c.audience == "tech" and c.score > 0 and c.reasons


def test_entry_va_routes_to_entry_without_company():
    c = classify(job(title="Virtual Assistant", company="", board="indeed_search",
                     description="Support the team with scheduling."))
    assert c.audience == "entry"


def test_visa_posting_routes_to_visa():
    c = classify(job(title="Senior Backend Engineer", board="visa_sponsorship",
                     description="We offer visa sponsorship and relocation support. " + LONG))
    assert c.audience == "visa"


def test_scam_is_dropped():
    assert classify(job(title="Data Entry Clerk", company="",
                        description="Unpaid internship, no experience needed.")).audience is None


def test_metadata_thin_tech_is_dropped_not_routed_to_entry():
    # tech family title, but no company and no real description -> fails tech,
    # fails entry (title not in entry allow) -> dropped.
    assert classify(job(title="Backend Engineer", company="", description="")).audience is None


def test_admin_assistant_kept_for_entry_dropped_for_tech():
    j = job(title="Administrative Assistant", company="", board="indeed_search",
            description="Manage calendars and email.")
    assert classify(j).audience == "entry"


def test_legacy_audience_normalization():
    assert relevance.normalize_audience("gig") == "entry"
    assert relevance.normalize_audience("creative") == "entry"
    assert relevance.normalize_audience("tech") == "tech"
    assert relevance.normalize_audience("") == ""


def test_priority_visa_beats_tech():
    j = job(title="Senior Software Engineer", board="visa_sponsorship",
            description="Relocation and visa sponsorship provided. " + LONG)
    assert classify(j).audience == "visa"


def test_poverty_wage_hourly_is_dropped():
    j = job(title="Virtual Assistant", company="", board="indeed_search",
            description="Pay is $2/hr. " + LONG)
    assert classify(j).audience is None


def test_overlapping_title_routes_to_tech_not_entry():
    # "technical support" is an entry family, "engineer" a tech family;
    # the fixed priority (tech before entry) must win.
    assert classify(job(title="Technical Support Engineer", company="Acme")).audience == "tech"


def test_annual_salary_is_not_treated_as_hourly():
    j = job(title="Senior Software Engineer",
            description="Compensation: $120,000 per year. " + LONG)
    assert classify(j).audience == "tech"


def test_visa_board_country_restriction_does_not_block_sponsorship():
    j = job(title="Senior Backend Engineer", board="visa_sponsorship",
            location="Remote (US only)",
            description="We provide visa sponsorship and relocation. " + LONG)
    assert classify(j).audience == "visa"


def test_missing_url_is_dropped():
    assert classify(job(title="Software Engineer", url="")).audience is None