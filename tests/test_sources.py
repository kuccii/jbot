from pathlib import Path

from job_bot.discovery.sources import SourcesConfig, ProviderConfig, load_sources


class TestSources:
    def test_empty_config(self):
        config = SourcesConfig()
        assert config.providers == {}

    def test_provider_config_defaults(self):
        p = ProviderConfig()
        assert p.enabled is True
        assert p.type == "serper"
        assert p.queries == []

    def test_provider_with_queries(self):
        p = ProviderConfig(queries=["test query"], targets=["example.com"])
        assert p.queries == ["test query"]
        assert p.targets == ["example.com"]

    def test_load_nonexistent(self, tmp_path):
        config = load_sources(tmp_path / "nonexistent.yaml")
        assert config.providers == {}

    def test_load_valid_yaml(self, tmp_path):
        path = tmp_path / "sources.yaml"
        path.write_text("providers:\n  test:\n    enabled: true\n    type: html\n    queries:\n      - q1\n")
        config = load_sources(path)
        assert "test" in config.providers
        assert config.providers["test"].queries == ["q1"]
        assert config.providers["test"].type == "html"
