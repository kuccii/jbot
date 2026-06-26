import pytest
from job_bot.config import Config, LLMConfig, load_config


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
