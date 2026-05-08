from unittest.mock import patch

import pytest
from pydantic import ValidationError

from supabase_mcp.settings import SUPPORTED_REGIONS, Settings


@pytest.fixture(autouse=True)
def reset_settings_singleton() -> None:
    """Reset the Settings singleton before each test"""
    # Clear singleton instance if it exists
    if hasattr(Settings, "_instance"):
        delattr(Settings, "_instance")
    yield
    # Clean up after test
    if hasattr(Settings, "_instance"):
        delattr(Settings, "_instance")


class TestSettings:
    """Integration tests for Settings."""

    @pytest.mark.integration
    def test_settings_default_values(self, clean_environment: None) -> None:
        """Test default values (no config file, no env vars)"""
        settings = Settings.with_config()  # No config file
        assert settings.supabase_project_ref == "127.0.0.1:54322"
        assert settings.supabase_db_password == "postgres"
        assert settings.supabase_region == "us-east-1"
        assert settings.supabase_access_token is None
        assert settings.supabase_service_role_key is None

    @pytest.mark.integration
    def test_settings_from_env_test(self, clean_environment: None) -> None:
        """Test loading from .env.test"""
        import os

        settings = Settings.with_config(".env.test")

        # In CI, we expect default values since .env.test might not be properly set up
        if os.environ.get("CI") == "true":
            assert settings.supabase_project_ref == "127.0.0.1:54322"  # Default value in CI
            assert settings.supabase_db_password == "postgres"  # Default value in CI
        else:
            # In local dev, we expect .env.test to override defaults
            assert settings.supabase_project_ref != "127.0.0.1:54322"  # Should be overridden by .env.test
            assert settings.supabase_db_password != "postgres"  # Should be overridden by .env.test

        # Check that the values are not empty
        assert settings.supabase_project_ref, "Project ref should not be empty"
        assert settings.supabase_db_password, "DB password should not be empty"

    @pytest.mark.integration
    def test_settings_from_env_vars(self, clean_environment: None) -> None:
        """Test env vars take precedence over config file"""
        env_values = {
            "SUPABASE_PROJECT_REF": "abcdefghij1234567890",  # Valid 20-char project ref
            "SUPABASE_DB_PASSWORD": "env-password",
        }
        with patch.dict("os.environ", env_values, clear=False):
            settings = Settings.with_config(".env.test")  # Even with config file
            assert settings.supabase_project_ref == "abcdefghij1234567890"
            assert settings.supabase_db_password == "env-password"

    @pytest.mark.integration
    def test_settings_integration_fixture(self, settings_integration: Settings) -> None:
        """Test the settings_integration fixture provides valid settings."""
        # The settings_integration fixture should load from .env.test or environment variables
        assert settings_integration.supabase_project_ref, "Project ref should not be empty"
        assert settings_integration.supabase_db_password, "DB password should not be empty"
        assert settings_integration.supabase_region, "Region should not be empty"

    @pytest.mark.integration
    def test_settings_region_validation(self) -> None:
        """Test region validation."""
        # Test default region
        settings = Settings()
        assert settings.supabase_region == "us-east-1"

        # Test valid region from environment
        env_values = {"SUPABASE_REGION": "ap-southeast-1"}
        with patch.dict("os.environ", env_values, clear=True):
            settings = Settings()
            assert settings.supabase_region == "ap-southeast-1"

        # Test invalid region
        with pytest.raises(ValidationError) as exc_info:
            env_values = {"SUPABASE_REGION": "invalid-region"}
            with patch.dict("os.environ", env_values, clear=True):
                Settings()
        assert "Region 'invalid-region' is not supported" in str(exc_info.value)

    @pytest.mark.integration
    def test_supported_regions(self) -> None:
        """Test that all supported regions are valid."""
        for region in SUPPORTED_REGIONS.__args__:
            env_values = {"SUPABASE_REGION": region}
            with patch.dict("os.environ", env_values, clear=True):
                settings = Settings()
                assert settings.supabase_region == region

    @pytest.mark.integration
    def test_settings_access_token_and_service_role(self) -> None:
        """Test access token and service role key settings."""
        # Test with environment variables
        env_values = {
            "SUPABASE_ACCESS_TOKEN": "test-access-token",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
        }
        with patch.dict("os.environ", env_values, clear=True):
            settings = Settings()
            assert settings.supabase_access_token == "test-access-token"
            assert settings.supabase_service_role_key == "test-service-role-key"

        # Test defaults (should be None)
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            assert settings.supabase_access_token is None
            assert settings.supabase_service_role_key is None

    def test_supabase_url_sets_remote_project_ref(self) -> None:
        """Test SUPABASE_URL validation and project ref extraction."""
        env_values = {
            "SUPABASE_URL": "https://abcdefghijklmnopqrst.supabase.co/",
            "SUPABASE_DB_PASSWORD": "remote-password",
        }
        with patch.dict("os.environ", env_values, clear=True):
            settings = Settings()
            assert settings.supabase_url == "https://abcdefghijklmnopqrst.supabase.co"
            assert settings.supabase_project_ref == "abcdefghijklmnopqrst"
            assert settings.supabase_db_password == "remote-password"

    @pytest.mark.parametrize(
        "supabase_url, expected_message",
        [
            ("http://abcdefghijklmnopqrst.supabase.co", "SUPABASE_URL must start with https://"),
            ("https://example.com", "SUPABASE_URL must match https://<project-ref>.supabase.co"),
            (
                "https://short.supabase.co",
                "SUPABASE_URL project ref must be 20 lowercase alphanumeric characters",
            ),
            (
                "https://abcdefghijklmnopqrst.supabase.co/rest/v1",
                "SUPABASE_URL must be a project root URL",
            ),
        ],
    )
    def test_supabase_url_validation_errors(self, supabase_url: str, expected_message: str) -> None:
        """Test malformed SUPABASE_URL values fail with actionable messages."""
        env_values = {
            "SUPABASE_URL": supabase_url,
            "SUPABASE_DB_PASSWORD": "remote-password",
        }
        with pytest.raises(ValidationError) as exc_info:
            with patch.dict("os.environ", env_values, clear=True):
                Settings()
        assert expected_message in str(exc_info.value)

    def test_supabase_url_must_match_project_ref_when_both_are_set(self) -> None:
        """Test SUPABASE_URL and SUPABASE_PROJECT_REF cannot conflict."""
        env_values = {
            "SUPABASE_URL": "https://abcdefghijklmnopqrst.supabase.co",
            "SUPABASE_PROJECT_REF": "tsrqponmlkjihgfedcba",
            "SUPABASE_DB_PASSWORD": "remote-password",
        }
        with pytest.raises(ValidationError) as exc_info:
            with patch.dict("os.environ", env_values, clear=True):
                Settings()
        assert "SUPABASE_URL project ref does not match SUPABASE_PROJECT_REF" in str(exc_info.value)

    def test_remote_project_requires_database_password_or_db_url(self) -> None:
        """Test remote projects fail early without database credentials."""
        env_values = {"SUPABASE_PROJECT_REF": "abcdefghijklmnopqrst"}
        with pytest.raises(ValidationError) as exc_info:
            with patch.dict("os.environ", env_values, clear=True):
                Settings()
        assert "Database password is required for remote Supabase projects unless DB_URL is provided" in str(
            exc_info.value
        )

    def test_remote_project_accepts_db_url_without_password(self) -> None:
        """Test DB_URL can explicitly provide the remote database connection."""
        db_url = "postgresql://postgres:secret@db.example.com:5432/postgres"
        env_values = {
            "SUPABASE_PROJECT_REF": "abcdefghijklmnopqrst",
            "DB_URL": db_url,
        }
        with patch.dict("os.environ", env_values, clear=True):
            settings = Settings()
            assert settings.supabase_project_ref == "abcdefghijklmnopqrst"
            assert settings.supabase_db_password is None
            assert settings.db_url == db_url

    @pytest.mark.parametrize(
        "db_url, expected_message",
        [
            ("postgres://postgres:secret@db.example.com/postgres", "DB_URL must start with postgresql://"),
            ("postgresql:///postgres", "DB_URL must include a database host"),
            ("postgresql://postgres:secret@db.example.com", "DB_URL must include a database name"),
        ],
    )
    def test_db_url_validation_errors(self, db_url: str, expected_message: str) -> None:
        """Test malformed DB_URL values fail with actionable messages."""
        env_values = {
            "SUPABASE_PROJECT_REF": "abcdefghijklmnopqrst",
            "DB_URL": db_url,
        }
        with pytest.raises(ValidationError) as exc_info:
            with patch.dict("os.environ", env_values, clear=True):
                Settings()
        assert expected_message in str(exc_info.value)

    def test_empty_service_role_key_is_treated_as_missing(self) -> None:
        """Test blank SUPABASE_SERVICE_ROLE_KEY fails the feature-specific requirement."""
        with patch.dict("os.environ", {"SUPABASE_SERVICE_ROLE_KEY": "   "}, clear=True):
            settings = Settings()
            assert settings.supabase_service_role_key is None
            with pytest.raises(ValueError) as exc_info:
                settings.require_service_role_key()
        assert "SUPABASE_SERVICE_ROLE_KEY is required to use Auth Admin SDK tools" in str(exc_info.value)
