from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from supabase_mcp.clients.api_client import ApiClient
from supabase_mcp.clients.management_client import ManagementAPIClient
from supabase_mcp.clients.meta_ads_client import MetaAdsClient
from supabase_mcp.clients.sdk_client import SupabaseSDKClient
from supabase_mcp.core.feature_manager import FeatureManager
from supabase_mcp.logger import logger
from supabase_mcp.services.api.api_manager import SupabaseApiManager
from supabase_mcp.services.database.postgres_client import PostgresClient
from supabase_mcp.services.database.query_manager import QueryManager
from supabase_mcp.services.logs.log_manager import LogManager
from supabase_mcp.services.meta_ads.campaign_manager import MetaAdsCampaignManager
from supabase_mcp.services.safety.safety_manager import SafetyManager
from supabase_mcp.settings import Settings
from supabase_mcp.tools import ToolManager


class ServicesContainer:
    """Container for all services"""

    _instance: ServicesContainer | None = None

    def __init__(
        self,
        mcp_server: FastMCP | None = None,
        postgres_client: PostgresClient | None = None,
        api_client: ManagementAPIClient | None = None,
        sdk_client: SupabaseSDKClient | None = None,
        api_manager: SupabaseApiManager | None = None,
        safety_manager: SafetyManager | None = None,
        query_manager: QueryManager | None = None,
        tool_manager: ToolManager | None = None,
        log_manager: LogManager | None = None,
        query_api_client: ApiClient | None = None,
        feature_manager: FeatureManager | None = None,
        meta_ads_client: MetaAdsClient | None = None,
        meta_ads_manager: MetaAdsCampaignManager | None = None,
        meta_ads_managers: dict[str, MetaAdsCampaignManager] | None = None,
    ) -> None:
        """Create a new container container reference"""
        self.postgres_client = postgres_client
        self.api_client = api_client
        self.api_manager = api_manager
        self.sdk_client = sdk_client
        self.safety_manager = safety_manager
        self.query_manager = query_manager
        self.tool_manager = tool_manager
        self.log_manager = log_manager
        self.query_api_client = query_api_client
        self.feature_manager = feature_manager
        self.mcp_server = mcp_server
        self.meta_ads_client = meta_ads_client
        # Single manager (primary account) — kept for backwards compat
        self.meta_ads_manager = meta_ads_manager
        # Dict of all linked account managers: {"act_xxx": MetaAdsCampaignManager}
        self.meta_ads_managers: dict[str, MetaAdsCampaignManager] = meta_ads_managers or {}

    @classmethod
    def get_instance(cls) -> ServicesContainer:
        """Get the singleton instance of the container"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize_services(self, settings: Settings) -> None:
        """Initializes all services in a synchronous manner to satisfy MCP runtime requirements"""
        # Create clients
        self.postgres_client = PostgresClient.get_instance(settings=settings)
        self.api_client = ManagementAPIClient(settings=settings)  # not a singleton, simple
        self.sdk_client = SupabaseSDKClient.get_instance(settings=settings)

        # Create managers
        self.safety_manager = SafetyManager.get_instance()
        self.api_manager = SupabaseApiManager.get_instance(
            api_client=self.api_client,
            safety_manager=self.safety_manager,
        )
        self.query_manager = QueryManager(
            postgres_client=self.postgres_client,
            safety_manager=self.safety_manager,
        )
        self.tool_manager = ToolManager.get_instance()

        # Register safety configs
        self.safety_manager.register_safety_configs()

        # Create query api client
        self.query_api_client = ApiClient()
        self.feature_manager = FeatureManager(self.query_api_client)

        # Initialize Meta Ads integration if credentials are configured
        if settings.meta_app_id and settings.meta_app_secret and settings.meta_access_token:
            self.meta_ads_client = MetaAdsClient.get_instance(
                access_token=settings.meta_access_token,
                app_id=settings.meta_app_id,
                app_secret=settings.meta_app_secret,
                api_version=settings.meta_api_version,
                timeout=settings.meta_request_timeout,
            )
            account_ids = settings.get_meta_account_ids()
            if account_ids:
                self.meta_ads_managers = {}
                for aid in account_ids:
                    self.meta_ads_managers[aid] = MetaAdsCampaignManager(
                        client=self.meta_ads_client,
                        ad_account_id=aid,
                    )
                # Primary manager = first account
                self.meta_ads_manager = self.meta_ads_managers[account_ids[0]]
                names = {
                    "act_1198372168168124": "طعم ابوغزالة",
                    "act_968620118865243": "Yazan Ali",
                }
                linked = ", ".join(
                    f"{names.get(a, a)} ({a})" for a in account_ids
                )
                logger.info(f"✓ Meta Ads integration initialised — linked accounts: {linked}")
            else:
                logger.warning("No META_AD_ACCOUNT_ID(S) set — Meta campaign tools will be unavailable.")
        else:
            logger.info("Meta Ads credentials not configured — Meta tools will be skipped.")

        logger.info("✓ All services initialized successfully.")

    async def connect_services(self) -> None:
        """Eagerly establish the database connection at startup (auto-login).

        By default the PostgreSQL connection pool is created lazily on the first
        query. Calling this during startup authenticates against the database up
        front so the first query is fast and connection problems surface early.

        Failures are logged but do not prevent the server from starting — the
        connection is simply retried lazily on the first query.
        """
        if self.postgres_client is None:
            logger.warning("Cannot auto-connect: PostgreSQL client is not initialized.")
            return

        try:
            await self.postgres_client.ensure_pool()
            logger.info("✓ Database connection established automatically at startup (auto-login enabled).")
        except Exception as e:  # noqa: BLE001 - best-effort startup connection, must not crash the server
            logger.warning(
                f"Automatic database connection at startup failed: {e}. "
                "The connection will be retried lazily on the first query."
            )

    async def shutdown_services(self) -> None:
        """Properly close all relevant clients and connections"""
        # Postgres client
        if self.postgres_client:
            await self.postgres_client.close()

        # API clients
        if self.query_api_client:
            await self.query_api_client.close()

        if self.api_client:
            await self.api_client.close()

        # SDK client
        if self.sdk_client:
            await self.sdk_client.close()

        # Meta Ads client
        if self.meta_ads_client:
            await self.meta_ads_client.close()
