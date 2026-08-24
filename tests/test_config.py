import pytest
from job_bot.config import Config, LLMConfig, WebServicesConfig, load_config


class TestConfig:
    def test_default_config(self):
        cfg = load_config()
        assert isinstance(cfg, Config)
        assert cfg.llm.provider == "opencode"
        assert cfg.database.path == "data/job_bot.db"

    def test_llm_config_defaults(self):
        llm = LLMConfig()
        assert llm.model == "deepseek-v4-flash-free"
        assert llm.temperature == 0.3

    def test_web_services_config_defaults(self):
        ws = WebServicesConfig()
        assert ws.firecrawl_api_key == ""
        assert ws.jina_api_key == ""
        assert ws.tinyfish_api_key == ""

    def test_web_services_in_config(self):
        cfg = load_config()
        assert hasattr(cfg, "web_services")
        assert isinstance(cfg.web_services, WebServicesConfig)

    def test_application_autonomous_apply_default(self):
        cfg = load_config()
        assert cfg.application.autonomous_apply is False
