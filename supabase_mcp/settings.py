import os
from pathlib import Path
from typing import Literal, get_args
from urllib.parse import urlparse

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from supabase_mcp.logger import logger

SUPPORTED_REGIONS = Literal[
    "us-west-1",  # West US (North California)
    "us-east-1",  # East US (North Virginia)
    "us-east-2",  # East US (Ohio)
    "ca-central-1",  # Canada (Central)
    "eu-west-1",  # West EU (Ireland)
    "eu-west-2",  # West Europe (London)
    "eu-west-3",  # West EU (Paris)
    "eu-central-1",  # Central EU (Frankfurt)
    "eu-central-2",  # Central Europe (Zurich)
    "eu-north-1",  # North EU (Stockholm)
    "ap-south-1",  # South Asia (Mumbai)
    "ap-southeast-1",  # Southeast Asia (Singapore)
    "ap-northeast-1",  # Northeast Asia (Tokyo)
    "ap-northeast-2",  # Northeast Asia (Seoul)
    "ap-southeast-2",  # Oceania (Sydney)
    "sa-east-1",  # South America (São Paulo)
]
SUPPORTED_REGION_VALUES = get_args(SUPPORTED_REGIONS)

LOCAL_PROJECT_REF = "127.0.0.1:54322"
SUPABASE_HOST_SUFFIX = ".supabase.co"


def find_config_file(env_file: str = ".env") -> str | None:
    """Find the specified env file in order of precedence:
    1. Current working directory (where command is run)
    2. Global config:
       - Windows: %APPDATA%/supabase-mcp/{env_file}
       - macOS/Linux: ~/.config/supabase-mcp/{env_file}

    Args:
        env_file: The name of the environment file to look for (default: ".env")

    Returns:
        The path to the found config file, or None if not found
    """
    # 1. Check current directory
    cwd_config = Path.cwd() / env_file
    if cwd_config.exists():
        return str(cwd_config)

    # 2. Check global config
    home = Path.home()
    if os.name == "nt":  # Windows
        global_config = Path(os.environ.get("APPDATA", "")) / "supabase-mcp" / ".env"
    else:  # macOS/Linux
        global_config = home / ".config" / "supabase-mcp" / ".env"

    if global_config.exists():
        logger.error(
            f"DEPRECATED: {global_config} is deprecated and will be removed in a future release. "
            "Use your IDE's native .json config file to configure access to MCP."
        )
        return str(global_config)

    return None


class Settings(BaseSettings):
    """Initializes settings for Supabase MCP server."""

    supabase_project_ref: str = Field(
        default=LOCAL_PROJECT_REF,  # Local Supabase default
        description="Supabase project ref - Must be 20 chars for remote projects, can be local address for development",
        alias="SUPABASE_PROJECT_REF",
    )
    supabase_url: str | None = Field(
        default=None,
        description="Optional Supabase project URL. Must be https://<project-ref>.supabase.co for remote projects.",
        alias="SUPABASE_URL",
    )
    supabase_db_password: str | None = Field(
        default=None,  # Will be validated based on project_ref
        description="Supabase database password - Required for remote projects, defaults to 'postgres' for local",
        alias="SUPABASE_DB_PASSWORD",
    )
    db_url: str | None = Field(
        default=None,
        description="Optional PostgreSQL connection string. Must use the postgresql:// scheme.",
        alias="DB_URL",
    )
    supabase_region: str = Field(
        default="us-east-1",  # East US (North Virginia) - Supabase's default region
        description="Supabase region for connection",
        alias="SUPABASE_REGION",
    )
    supabase_access_token: str | None = Field(
        default=None,
        description="Optional personal access token for accessing Supabase Management API",
        alias="SUPABASE_ACCESS_TOKEN",
    )
    supabase_service_role_key: str | None = Field(
        default=None,
        description="Optional service role key for accessing Python SDK",
        alias="SUPABASE_SERVICE_ROLE_KEY",
    )

    supabase_api_url: str = Field(
        default="https://api.supabase.com",
        description="Supabase API URL",
    )

    query_api_key: str = Field(
        default="test-key",
        description="TheQuery.dev API key",
        alias="QUERY_API_KEY",
    )

    query_api_url: str = Field(
        default="https://api.thequery.dev/v1",
        description="TheQuery.dev API URL",
        alias="QUERY_API_URL",
    )

    @field_validator("supabase_region")
    @classmethod
    def validate_region(cls, v: str, info: ValidationInfo) -> str:
        """Validate that the region is supported by Supabase."""
        # Get the project_ref from the values
        values = info.data
        project_ref = values.get("supabase_project_ref", "")

        # If this is a remote project and region is the default
        if not project_ref.startswith("127.0.0.1") and v == "us-east-1" and "SUPABASE_REGION" not in os.environ:
            logger.warning(
                "You're connecting to a remote Supabase project but haven't specified a region. "
                "Using default 'us-east-1', which may cause 'Tenant or user not found' errors if incorrect. "
                "Please set the correct SUPABASE_REGION in your configuration."
            )

        # Validate that the region is supported
        if v not in SUPPORTED_REGION_VALUES:
            supported = "\n  - ".join([""] + list(SUPPORTED_REGION_VALUES))
            raise ValueError(f"Region '{v}' is not supported. Supported regions are:{supported}")
        return v

    @field_validator("supabase_url", mode="before")
    @classmethod
    def normalize_optional_supabase_url(cls, v: str | None) -> str | None:
        """Treat empty SUPABASE_URL values as unset."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("SUPABASE_URL must be a string")
        stripped = v.strip()
        return stripped or None

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, v: str | None) -> str | None:
        """Validate remote Supabase project URL format."""
        if v is None:
            return None

        parsed = urlparse(v)
        if parsed.scheme != "https":
            raise ValueError("SUPABASE_URL must start with https://")
        if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("SUPABASE_URL must be a project root URL like https://<project-ref>.supabase.co")

        host = parsed.hostname or ""
        if not host.endswith(SUPABASE_HOST_SUFFIX):
            raise ValueError("SUPABASE_URL must match https://<project-ref>.supabase.co")

        project_ref = host[: -len(SUPABASE_HOST_SUFFIX)]
        if len(project_ref) != 20 or not project_ref.isalnum() or project_ref.lower() != project_ref:
            raise ValueError("SUPABASE_URL project ref must be 20 lowercase alphanumeric characters")

        return f"https://{project_ref}{SUPABASE_HOST_SUFFIX}"

    @field_validator("db_url", mode="before")
    @classmethod
    def normalize_optional_db_url(cls, v: str | None) -> str | None:
        """Treat empty DB_URL values as unset."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("DB_URL must be a string")
        stripped = v.strip()
        return stripped or None

    @field_validator("db_url")
    @classmethod
    def validate_db_url(cls, v: str | None) -> str | None:
        """Validate explicit PostgreSQL connection string format."""
        if v is None:
            return None

        parsed = urlparse(v)
        if parsed.scheme != "postgresql":
            raise ValueError("DB_URL must start with postgresql://")
        if not parsed.hostname:
            raise ValueError("DB_URL must include a database host")
        if not parsed.path or parsed.path == "/":
            raise ValueError("DB_URL must include a database name")
        return v

    @field_validator("supabase_project_ref")
    @classmethod
    def validate_project_ref(cls, v: str) -> str:
        """Validate the project ref format."""
        if v.startswith("127.0.0.1"):
            # Local development - allow default format
            return v

        # Remote project - must be 20 chars
        if len(v) != 20:
            logger.error("Invalid Supabase project ref format")
            raise ValueError(
                "Invalid Supabase project ref format. "
                "Remote project refs must be exactly 20 characters long. "
                f"Got {len(v)} characters instead."
            )
        return v

    @field_validator("supabase_db_password")
    @classmethod
    def validate_db_password(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Default the local development database password only for local settings."""
        project_ref = info.data.get("supabase_project_ref", "")
        supabase_url = info.data.get("supabase_url")

        # For local development, allow default password
        if project_ref.startswith("127.0.0.1") and supabase_url is None:
            return v or "postgres"  # Default to postgres for local

        return v

    @field_validator("supabase_service_role_key", mode="before")
    @classmethod
    def normalize_optional_service_role_key(cls, v: str | None) -> str | None:
        """Treat empty SUPABASE_SERVICE_ROLE_KEY values as unset."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY must be a string")
        stripped = v.strip()
        return stripped or None

    @model_validator(mode="after")
    def align_supabase_url_and_project_ref(self) -> "Settings":
        """Keep SUPABASE_URL and SUPABASE_PROJECT_REF consistent."""
        if self.supabase_url is None:
            return self

        host = urlparse(self.supabase_url).hostname or ""
        project_ref = host[: -len(SUPABASE_HOST_SUFFIX)]

        if self.supabase_project_ref == LOCAL_PROJECT_REF:
            self.supabase_project_ref = project_ref
            return self

        if self.supabase_project_ref != project_ref:
            raise ValueError(
                "SUPABASE_URL project ref does not match SUPABASE_PROJECT_REF. "
                f"Got URL ref '{project_ref}' and project ref '{self.supabase_project_ref}'."
            )

        return self

    @model_validator(mode="after")
    def require_remote_database_credentials(self) -> "Settings":
        """Require clear database credentials for remote Supabase projects."""
        is_remote_project = not self.supabase_project_ref.startswith("127.0.0.1")
        if not is_remote_project:
            return self

        if not self.supabase_db_password and not self.db_url:
            raise ValueError(
                "Database password is required for remote Supabase projects unless DB_URL is provided. "
                "Set SUPABASE_DB_PASSWORD or DB_URL in your environment variables."
            )
        return self

    def require_service_role_key(self) -> str:
        """Return the service role key or raise a clear feature-specific error."""
        if not self.supabase_service_role_key:
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY is required to use Auth Admin SDK tools. "
                "Set SUPABASE_SERVICE_ROLE_KEY in your environment or config file."
            )
        return self.supabase_service_role_key

    @classmethod
    def with_config(cls, config_file: str | None = None) -> "Settings":
        """Create Settings with a specific config file.

        Args:
            config_file: Path to .env file to use, or None for no config file
        """

        # Create a new Settings class with the specific config
        class SettingsWithConfig(cls):  # type: ignore[misc, valid-type]
            model_config = SettingsConfigDict(env_file=config_file, env_file_encoding="utf-8")

        instance = SettingsWithConfig()

        # Log configuration source and precedence - simplified to a single clear message
        env_vars_present = any(var in os.environ for var in ["SUPABASE_PROJECT_REF", "SUPABASE_DB_PASSWORD"])

        if env_vars_present and config_file:
            logger.info(f"Using environment variables (highest precedence) over config file: {config_file}")
        elif env_vars_present:
            logger.info("Using environment variables for configuration")
        elif config_file:
            logger.info(f"Using settings from config file: {config_file}")
        else:
            logger.info("Using default settings (local development)")

        return instance


# Module-level singleton - maintains existing interface
settings = Settings.with_config(find_config_file())
