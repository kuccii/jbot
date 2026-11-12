from job_hunter import profile_sync

CV = """
## Skills
### Technical Expertise
Cloud Systems, AI & Automation, Mobile & Web Development, Databases, DevOps Tools
### Project & Product Management
Product Planning & Roadmapping, KPI Tracking & Performance Analysis, Agile & Scrum Methodologies
"""

PROFILE_YML = {
    "name": "Patrick Hirwa",
    "email": "impatrickhi@gmail.com",
    "location": "Rwanda",
    "target_roles": ["Product Manager", "AI / Automation Specialist",
                     "Software Engineer", "Project Manager"],
}


def test_derive_skills_expands_cv_phrases_and_roles():
    skills = profile_sync.derive_skills(CV, PROFILE_YML["target_roles"])
    assert "product manager" in skills
    assert "automation" in skills          # from "AI & Automation"
    assert "docker" in skills              # from "DevOps Tools"
    assert "sql" in skills                 # from "Databases"
    assert skills == sorted(set(skills))   # deduped + stable order


def test_build_profile_shape():
    p = profile_sync.build_profile(PROFILE_YML, CV)
    assert p["name"] == "Patrick Hirwa"
    assert p["email"] == "impatrickhi@gmail.com"
    assert p["location"] == "Rwanda"
    assert p["seniority"] == "mid"
    assert isinstance(p["skills"], list) and p["skills"]


def test_replace_profile_block_is_surgical():
    cfg = "profile:\n  name: \"Your Name\"\n  skills:\n    - python\nboards:\n  remoteok: true\n"
    out = profile_sync.replace_profile_block(cfg, {"name": "Patrick Hirwa", "skills": ["ai"]})
    assert "Patrick Hirwa" in out
    assert "Your Name" not in out
    assert "boards:\n  remoteok: true" in out   # untouched


def test_replace_profile_block_handles_eof():
    cfg = "boards:\n  remoteok: true\nprofile:\n  name: x\n"
    out = profile_sync.replace_profile_block(cfg, {"name": "Y"})
    assert out.rstrip().endswith("name: Y")
