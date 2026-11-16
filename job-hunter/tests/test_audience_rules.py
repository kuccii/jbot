from job_hunter import audience_rules as ar


def test_match_any_is_word_boundary():
    assert ar.match_any("Senior Python Engineer", ar.TECH_TITLE_ALLOW) == "engineer"
    # "ai" must not match inside "maintenance" / "email"
    assert ar.match_any("Maintenance Coordinator", ["ai"]) is None
    assert ar.match_any("Salesforce Developer", ar.TECH_TITLE_DENY) is None


def test_deny_lists_catch_off_profile_titles():
    for title in ["Technical Recruiter", "Online Tutor", "Customer Support Agent",
                  "Sales Manager", "Registered Nurse", "Marketing Manager",
                  "Data Entry Clerk"]:
        assert ar.match_any(title, ar.TECH_TITLE_DENY), title


def test_tech_allow_keeps_target_families():
    for title in ["Software Engineer", "Product Manager", "AI Automation Specialist",
                  "Project Manager", "DevOps Engineer", "Data Scientist"]:
        assert ar.match_any(title, ar.TECH_TITLE_ALLOW), title


def test_entry_allow_keeps_entry_families():
    for title in ["Virtual Assistant", "Data Annotator", "Transcriptionist",
                  "Content Moderator", "Customer Support Agent", "Online Tutor"]:
        assert ar.match_any(title, ar.ENTRY_TITLE_ALLOW), title


def test_lists_are_populated_and_lowercase():
    for name in ("TECH_TITLE_ALLOW", "TECH_TITLE_DENY", "ENTRY_TITLE_ALLOW",
                 "ENTRY_TITLE_DENY", "VISA_TITLE_DENY", "SENIORITY_DENY",
                 "GENERIC_DENY"):
        terms = getattr(ar, name)
        assert terms, name
        assert all(t == t.lower() for t in terms), name