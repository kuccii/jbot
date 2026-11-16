from pathlib import Path
from job_hunter.config import Config, AudiencesConfig
from job_hunter import audience_rules as ar


def test_defaults_come_from_audience_rules():
    c = Config()
    assert c.wage_floor_usd_per_hour == 4.0
    assert c.audiences.tech.title_allow == ar.TECH_TITLE_ALLOW
    assert c.audiences.entry.require_company_or_description is True
    assert c.audiences.tech.require_company is True
    assert c.audiences.visa.require_description is True


def test_production_config_audiences_match_defaults():
    cfg_path = Path(__file__).resolve().parents[1] / "config.production.yaml"
    import yaml
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg = Config(**data)
    assert cfg.audiences == AudiencesConfig()