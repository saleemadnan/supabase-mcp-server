from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml

from supabase_mcp.logger import logger


class ToolName(str, Enum):
    """Enum of all available tools in the Supabase MCPh server."""

    # Database tools
    GET_SCHEMAS = "get_schemas"
    GET_TABLES = "get_tables"
    GET_TABLE_SCHEMA = "get_table_schema"
    EXECUTE_POSTGRESQL = "execute_postgresql"
    RETRIEVE_MIGRATIONS = "retrieve_migrations"

    # Safety tools
    LIVE_DANGEROUSLY = "live_dangerously"
    CONFIRM_DESTRUCTIVE_OPERATION = "confirm_destructive_operation"

    # Management API tools
    SEND_MANAGEMENT_API_REQUEST = "send_management_api_request"
    GET_MANAGEMENT_API_SPEC = "get_management_api_spec"

    # Auth Admin tools
    GET_AUTH_ADMIN_METHODS_SPEC = "get_auth_admin_methods_spec"
    CALL_AUTH_ADMIN_METHOD = "call_auth_admin_method"

    # Logs & Analytics tools
    RETRIEVE_LOGS = "retrieve_logs"

    # Auth status tool
    GET_AUTH_STATUS = "get_auth_status"

    # Meta Marketing API tools
    META_LIST_LINKED_ACCOUNTS = "meta_list_linked_accounts"
    META_GET_ACCOUNT_INFO = "meta_get_account_info"
    META_LIST_CAMPAIGNS = "meta_list_campaigns"
    META_GET_CAMPAIGN = "meta_get_campaign"
    META_CREATE_CAMPAIGN = "meta_create_campaign"
    META_UPDATE_CAMPAIGN = "meta_update_campaign"
    META_DELETE_CAMPAIGN = "meta_delete_campaign"
    META_TOGGLE_CAMPAIGN = "meta_toggle_campaign"
    META_LIST_ADSETS = "meta_list_adsets"
    META_GET_ADSET = "meta_get_adset"
    META_CREATE_ADSET = "meta_create_adset"
    META_UPDATE_ADSET = "meta_update_adset"
    META_DELETE_ADSET = "meta_delete_adset"
    META_LIST_ADS = "meta_list_ads"
    META_GET_AD = "meta_get_ad"
    META_CREATE_AD = "meta_create_ad"
    META_UPDATE_AD = "meta_update_ad"
    META_DELETE_AD = "meta_delete_ad"
    META_GET_ACCOUNT_INSIGHTS = "meta_get_account_insights"
    META_GET_CAMPAIGN_INSIGHTS = "meta_get_campaign_insights"
    META_GET_ADSET_INSIGHTS = "meta_get_adset_insights"
    META_GET_AD_INSIGHTS = "meta_get_ad_insights"
    META_LIST_CREATIVES = "meta_list_creatives"
    META_CREATE_CREATIVE = "meta_create_creative"
    META_EXCHANGE_TOKEN = "meta_exchange_token"


class ToolManager:
    """Manager for tool descriptions and registration.

    This class is responsible for loading tool descriptions from YAML files
    and providing them to the main application.
    """

    _instance: ToolManager | None = None  # Singleton instance

    def __init__(self) -> None:
        """Initialize the tool manager."""
        self.descriptions: dict[str, str] = {}
        self._load_descriptions()

    @classmethod
    def get_instance(cls) -> ToolManager:
        """Get or create the singleton instance of ToolManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance of ToolManager."""
        if cls._instance is not None:
            cls._instance = None
            logger.info("ToolManager instance reset complete")

    def _load_descriptions(self) -> None:
        """Load tool descriptions from YAML files."""
        # Path to the descriptions directory
        descriptions_dir = Path(__file__).parent / "descriptions"

        # Check if the directory exists
        if not descriptions_dir.exists():
            raise FileNotFoundError(f"Tool descriptions directory not found: {descriptions_dir}")

        # Load all YAML files in the directory
        for yaml_file in descriptions_dir.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    tool_descriptions = yaml.safe_load(f)
                    if tool_descriptions:
                        self.descriptions.update(tool_descriptions)
            except Exception as e:
                print(f"Error loading tool descriptions from {yaml_file}: {e}")

    def get_description(self, tool_name: str) -> str:
        """Get the description for a specific tool.

        Args:
            tool_name: The name of the tool to get the description for.

        Returns:
            The description of the tool, or an empty string if not found.
        """
        return self.descriptions.get(tool_name, "")
