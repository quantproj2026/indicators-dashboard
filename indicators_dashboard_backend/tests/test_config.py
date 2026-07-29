"""Settings loaded the way a deployment actually loads them: from the environment.

These tests exist because a bug shipped that unit tests could not see. Every
other suite builds `Settings(...)` in Python, which bypasses pydantic-settings'
environment source entirely -- and that source is where list-typed fields are
JSON-decoded before any validator runs. A plain `CORS_ORIGINS=https://x.com`
crashed the process at import time on Render while every local test passed.

So: exercise the env source, not the constructor.
"""

from __future__ import annotations

import pytest

from indicators_dashboard_backend.config import Settings


@pytest.fixture
def env(monkeypatch):
    """Settings built purely from environment variables, ignoring any .env file."""

    def build(**variables: str) -> Settings:
        for key, value in variables.items():
            monkeypatch.setenv(key, value)
        # `_env_file=None` keeps a developer's real .env out of the assertions.
        # It is a documented pydantic-settings init argument that its type stubs
        # do not declare, hence the ignore.
        return Settings(_env_file=None)  # type: ignore[call-arg]

    return build


class TestCorsOrigins:
    def test_a_single_origin_is_accepted(self, env):
        """The most common deployment value: one frontend URL, no punctuation."""
        settings = env(CORS_ORIGINS="https://my-dashboard.vercel.app")
        assert settings.cors_origins == ["https://my-dashboard.vercel.app"]

    def test_a_comma_separated_list_is_split(self, env):
        settings = env(
            CORS_ORIGINS="https://app.example.com,https://www.example.com"
        )
        assert settings.cors_origins == [
            "https://app.example.com",
            "https://www.example.com",
        ]

    def test_surrounding_whitespace_is_trimmed(self, env):
        settings = env(CORS_ORIGINS=" https://a.com , https://b.com ")
        assert settings.cors_origins == ["https://a.com", "https://b.com"]

    def test_trailing_commas_do_not_produce_empty_origins(self, env):
        settings = env(CORS_ORIGINS="https://a.com,,https://b.com,")
        assert settings.cors_origins == ["https://a.com", "https://b.com"]

    def test_a_json_array_still_works(self, env):
        settings = env(CORS_ORIGINS='["https://a.com", "https://b.com"]')
        assert settings.cors_origins == ["https://a.com", "https://b.com"]

    def test_malformed_json_explains_the_alternative(self, env):
        with pytest.raises(Exception, match="comma-separated"):
            env(CORS_ORIGINS='["https://a.com"')

    def test_an_empty_value_allows_no_origins(self, env):
        assert env(CORS_ORIGINS="").cors_origins == []

    def test_the_default_covers_local_development(self, env):
        assert "http://localhost:3000" in env().cors_origins


class TestOtherFieldsFromTheEnvironment:
    def test_the_api_key_is_read(self, env):
        settings = env(ALPHA_VANTAGE_API_KEY="from-the-environment")
        assert settings.alpha_vantage_api_key == "from-the-environment"
        assert settings.has_api_key is True

    def test_a_blank_key_reads_as_absent(self, env):
        assert env(ALPHA_VANTAGE_API_KEY="   ").has_api_key is False

    def test_numeric_settings_are_coerced(self, env):
        settings = env(CACHE_TTL_SECONDS="43200", MAX_RETRIES="0")
        assert settings.cache_ttl_seconds == 43200
        assert settings.max_retries == 0

    def test_booleans_accept_the_usual_spellings(self, env):
        assert env(CACHE_PERSIST="false").cache_persist is False
        assert env(CACHE_PERSIST="true").cache_persist is True

    def test_the_cache_directory_can_be_relocated(self, env):
        """Render mounts a persistent disk outside the source tree."""
        settings = env(CACHE_DIR="/var/data/cache")
        assert str(settings.cache_dir).replace("\\", "/").endswith("/var/data/cache")

    def test_the_api_prefix_is_normalised(self, env):
        assert env(API_PREFIX="api/v2/").api_prefix == "/api/v2"
        assert env(API_PREFIX="/").api_prefix == ""

    def test_unknown_variables_are_ignored(self, env):
        """Render injects PORT, PYTHON_VERSION and friends; none are ours."""
        settings = env(PORT="10000", PYTHON_VERSION="3.13.4", WEB_CONCURRENCY="1")
        assert settings.api_prefix == "/api/v1"


def test_every_documented_variable_in_the_example_file_parses(env):
    """`.env.example` is documentation people paste from -- it has to work.

    The CORS bug was present in that file too: the commented default was the
    comma-separated form that could not be parsed.
    """
    from indicators_dashboard_backend.config import PROJECT_ROOT

    example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    variables: dict[str, str] = {}
    for line in example.splitlines():
        line = line.strip().lstrip("#").strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.isupper() and value.strip():
            variables[key] = value.strip()

    assert "CORS_ORIGINS" in variables, "expected the example file to document CORS"

    settings = env(**variables)
    assert settings.cors_origins
    assert settings.cache_ttl_seconds > 0
