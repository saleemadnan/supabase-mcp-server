from typing import TYPE_CHECKING, Any, Literal

from supabase_mcp.clients.api_client import ApiClient
from supabase_mcp.exceptions import APIError, ConfirmationRequiredError, FeatureAccessError, FeatureTemporaryError
from supabase_mcp.logger import logger
from supabase_mcp.services.database.postgres_client import QueryResult
from supabase_mcp.services.safety.models import ClientType, SafetyMode
from supabase_mcp.tools.manager import ToolName

if TYPE_CHECKING:
    from supabase_mcp.core.container import ServicesContainer


class FeatureManager:
    """Service for managing features, access to them and their configuration."""

    def __init__(self, api_client: ApiClient):
        """Initialize the feature service.

        Args:
            api_client: Client for communicating with the API
        """
        self.api_client = api_client

    async def check_feature_access(self, feature_name: str) -> None:
        """Check if the user has access to a feature.

        Args:
            feature_name: Name of the feature to check

        Raises:
            FeatureAccessError: If the user doesn't have access to the feature
        """
        try:
            # Use the API client to check feature access
            response = await self.api_client.check_feature_access(feature_name)

            # If access is not granted, raise an exception
            if not response.access_granted:
                logger.info(f"Feature access denied: {feature_name}")
                raise FeatureAccessError(feature_name)

            logger.debug(f"Feature access granted: {feature_name}")

        except APIError as e:
            logger.error(f"API error checking feature access: {feature_name} - {e}")
            raise FeatureTemporaryError(feature_name, e.status_code, e.response_body) from e
        except Exception as e:
            if not isinstance(e, FeatureAccessError):
                logger.error(f"Unexpected error checking feature access: {feature_name} - {e}")
                raise FeatureTemporaryError(feature_name) from e
            raise

    async def execute_tool(self, tool_name: ToolName, services_container: "ServicesContainer", **kwargs: Any) -> Any:
        """Execute a tool with feature access check.

        Args:
            tool_name: Name of the tool to execute
            services_container: Container with all services
            **kwargs: Arguments to pass to the tool

        Returns:
            Result of the tool execution
        """
        # Check feature access
        await self.check_feature_access(tool_name.value)

        # Execute the appropriate tool based on name
        if tool_name == ToolName.GET_SCHEMAS:
            return await self.get_schemas(services_container)
        elif tool_name == ToolName.GET_TABLES:
            return await self.get_tables(services_container, **kwargs)
        elif tool_name == ToolName.GET_TABLE_SCHEMA:
            return await self.get_table_schema(services_container, **kwargs)
        elif tool_name == ToolName.EXECUTE_POSTGRESQL:
            return await self.execute_postgresql(services_container, **kwargs)
        elif tool_name == ToolName.RETRIEVE_MIGRATIONS:
            return await self.retrieve_migrations(services_container, **kwargs)
        elif tool_name == ToolName.SEND_MANAGEMENT_API_REQUEST:
            return await self.send_management_api_request(services_container, **kwargs)
        elif tool_name == ToolName.GET_MANAGEMENT_API_SPEC:
            return await self.get_management_api_spec(services_container, **kwargs)
        elif tool_name == ToolName.GET_AUTH_ADMIN_METHODS_SPEC:
            return await self.get_auth_admin_methods_spec(services_container)
        elif tool_name == ToolName.CALL_AUTH_ADMIN_METHOD:
            return await self.call_auth_admin_method(services_container, **kwargs)
        elif tool_name == ToolName.LIVE_DANGEROUSLY:
            return await self.live_dangerously(services_container, **kwargs)
        elif tool_name == ToolName.CONFIRM_DESTRUCTIVE_OPERATION:
            return await self.confirm_destructive_operation(services_container, **kwargs)
        elif tool_name == ToolName.RETRIEVE_LOGS:
            return await self.retrieve_logs(services_container, **kwargs)
        # Meta Marketing API tools
        elif tool_name == ToolName.META_LIST_LINKED_ACCOUNTS:
            return await self.meta_list_linked_accounts(services_container)
        elif tool_name == ToolName.META_GET_ACCOUNT_INFO:
            return await self.meta_get_account_info(services_container, **kwargs)
        elif tool_name == ToolName.META_LIST_CAMPAIGNS:
            return await self.meta_list_campaigns(services_container, **kwargs)
        elif tool_name == ToolName.META_GET_CAMPAIGN:
            return await self.meta_get_campaign(services_container, **kwargs)
        elif tool_name == ToolName.META_CREATE_CAMPAIGN:
            return await self.meta_create_campaign(services_container, **kwargs)
        elif tool_name == ToolName.META_UPDATE_CAMPAIGN:
            return await self.meta_update_campaign(services_container, **kwargs)
        elif tool_name == ToolName.META_DELETE_CAMPAIGN:
            return await self.meta_delete_campaign(services_container, **kwargs)
        elif tool_name == ToolName.META_TOGGLE_CAMPAIGN:
            return await self.meta_toggle_campaign(services_container, **kwargs)
        elif tool_name == ToolName.META_LIST_ADSETS:
            return await self.meta_list_adsets(services_container, **kwargs)
        elif tool_name == ToolName.META_GET_ADSET:
            return await self.meta_get_adset(services_container, **kwargs)
        elif tool_name == ToolName.META_CREATE_ADSET:
            return await self.meta_create_adset(services_container, **kwargs)
        elif tool_name == ToolName.META_UPDATE_ADSET:
            return await self.meta_update_adset(services_container, **kwargs)
        elif tool_name == ToolName.META_DELETE_ADSET:
            return await self.meta_delete_adset(services_container, **kwargs)
        elif tool_name == ToolName.META_LIST_ADS:
            return await self.meta_list_ads(services_container, **kwargs)
        elif tool_name == ToolName.META_GET_AD:
            return await self.meta_get_ad(services_container, **kwargs)
        elif tool_name == ToolName.META_CREATE_AD:
            return await self.meta_create_ad(services_container, **kwargs)
        elif tool_name == ToolName.META_UPDATE_AD:
            return await self.meta_update_ad(services_container, **kwargs)
        elif tool_name == ToolName.META_DELETE_AD:
            return await self.meta_delete_ad(services_container, **kwargs)
        elif tool_name == ToolName.META_GET_ACCOUNT_INSIGHTS:
            return await self.meta_get_account_insights(services_container, **kwargs)
        elif tool_name == ToolName.META_GET_CAMPAIGN_INSIGHTS:
            return await self.meta_get_campaign_insights(services_container, **kwargs)
        elif tool_name == ToolName.META_GET_ADSET_INSIGHTS:
            return await self.meta_get_adset_insights(services_container, **kwargs)
        elif tool_name == ToolName.META_GET_AD_INSIGHTS:
            return await self.meta_get_ad_insights(services_container, **kwargs)
        elif tool_name == ToolName.META_LIST_CREATIVES:
            return await self.meta_list_creatives(services_container, **kwargs)
        elif tool_name == ToolName.META_CREATE_CREATIVE:
            return await self.meta_create_creative(services_container, **kwargs)
        elif tool_name == ToolName.META_EXCHANGE_TOKEN:
            return await self.meta_exchange_token(services_container, **kwargs)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def get_schemas(self, container: "ServicesContainer") -> QueryResult:
        """List all database schemas with their sizes and table counts."""
        query_manager = container.query_manager
        query = query_manager.get_schemas_query()
        return await query_manager.handle_query(query)

    async def get_tables(self, container: "ServicesContainer", schema_name: str) -> QueryResult:
        """List all tables, foreign tables, and views in a schema with their sizes, row counts, and metadata."""
        query_manager = container.query_manager
        query = query_manager.get_tables_query(schema_name)
        return await query_manager.handle_query(query)

    async def get_table_schema(self, container: "ServicesContainer", schema_name: str, table: str) -> QueryResult:
        """Get detailed table structure including columns, keys, and relationships."""
        query_manager = container.query_manager
        query = query_manager.get_table_schema_query(schema_name, table)
        return await query_manager.handle_query(query)

    async def execute_postgresql(
        self, container: "ServicesContainer", query: str, migration_name: str = ""
    ) -> QueryResult:
        """Execute PostgreSQL statements against your Supabase database."""
        query_manager = container.query_manager
        return await query_manager.handle_query(query, has_confirmation=False, migration_name=migration_name)

    async def retrieve_migrations(
        self,
        container: "ServicesContainer",
        limit: int = 50,
        offset: int = 0,
        name_pattern: str = "",
        include_full_queries: bool = False,
    ) -> QueryResult:
        """Retrieve a list of all migrations a user has from Supabase."""
        query_manager = container.query_manager
        query = query_manager.get_migrations_query(
            limit=limit, offset=offset, name_pattern=name_pattern, include_full_queries=include_full_queries
        )
        return await query_manager.handle_query(query)

    async def send_management_api_request(
        self,
        container: "ServicesContainer",
        method: str,
        path: str,
        path_params: dict[str, str],
        request_params: dict[str, Any],
        request_body: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a Supabase Management API request."""
        api_manager = container.api_manager
        return await api_manager.execute_request(method, path, path_params, request_params, request_body)

    async def get_management_api_spec(
        self, container: "ServicesContainer", params: dict[str, Any] = {}
    ) -> dict[str, Any]:
        """Get the Supabase Management API specification."""
        path = params.get("path")
        method = params.get("method")
        domain = params.get("domain")
        all_paths = params.get("all_paths", False)

        logger.debug(
            f"Getting management API spec with path: {path}, method: {method}, domain: {domain}, all_paths: {all_paths}"
        )
        api_manager = container.api_manager
        return await api_manager.handle_spec_request(path, method, domain, all_paths)

    async def get_auth_admin_methods_spec(self, container: "ServicesContainer") -> dict[str, Any]:
        """Get Python SDK methods specification for Auth Admin."""
        sdk_client = container.sdk_client
        return sdk_client.return_python_sdk_spec()

    async def call_auth_admin_method(
        self, container: "ServicesContainer", method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Call an Auth Admin method from Supabase Python SDK."""
        sdk_client = container.sdk_client
        return await sdk_client.call_auth_admin_method(method, params)

    async def live_dangerously(
        self, container: "ServicesContainer", service: Literal["api", "database", "meta"], enable_unsafe_mode: bool = False
    ) -> dict[str, Any]:
        """
        Toggle between safe and unsafe operation modes for API, Database, or Meta services.

        This function controls the safety level for operations, allowing you to:
        - Enable write operations for the database (INSERT, UPDATE, DELETE, schema changes)
        - Enable state-changing operations for the Management API
        - Enable write/delete operations for Meta Marketing API campaigns and ads
        """
        safety_manager = container.safety_manager
        if service == "api":
            new_mode = SafetyMode.UNSAFE if enable_unsafe_mode else SafetyMode.SAFE
            safety_manager.set_safety_mode(ClientType.API, new_mode)
            return {"service": "api", "mode": safety_manager.get_safety_mode(ClientType.API)}
        elif service == "database":
            new_mode = SafetyMode.UNSAFE if enable_unsafe_mode else SafetyMode.SAFE
            safety_manager.set_safety_mode(ClientType.DATABASE, new_mode)
            return {"service": "database", "mode": safety_manager.get_safety_mode(ClientType.DATABASE)}
        elif service == "meta":
            new_mode = SafetyMode.UNSAFE if enable_unsafe_mode else SafetyMode.SAFE
            safety_manager.set_safety_mode(ClientType.META, new_mode)
            return {"service": "meta", "mode": safety_manager.get_safety_mode(ClientType.META)}

    async def confirm_destructive_operation(
        self,
        container: "ServicesContainer",
        operation_type: Literal["api", "database", "meta"],
        confirmation_id: str,
        user_confirmation: bool = False,
    ) -> QueryResult | dict[str, Any]:
        """Execute a destructive operation after confirmation. Use this only after reviewing the risks with the user."""
        api_manager = container.api_manager
        query_manager = container.query_manager
        if not user_confirmation:
            raise ConfirmationRequiredError("Destructive operation requires explicit user confirmation.")

        if operation_type == "api":
            return await api_manager.handle_confirmation(confirmation_id)
        elif operation_type == "database":
            return await query_manager.handle_confirmation(confirmation_id)
        elif operation_type == "meta":
            safety_manager = container.safety_manager
            stored = safety_manager.get_stored_operation(confirmation_id)
            if stored is None:
                raise ConfirmationRequiredError(
                    f"Confirmation ID '{confirmation_id}' not found or expired. "
                    "Re-run the delete operation to receive a new confirmation ID."
                )
            tool_name, kwargs = stored if isinstance(stored, tuple) else (stored, {})
            return await getattr(self, tool_name)(container, **kwargs)

    async def retrieve_logs(
        self,
        container: "ServicesContainer",
        collection: str,
        limit: int = 20,
        hours_ago: int = 1,
        filters: list[dict[str, Any]] = [],
        search: str = "",
        custom_query: str = "",
    ) -> dict[str, Any]:
        """Retrieve logs from your Supabase project's services for debugging and monitoring."""
        logger.info(
            f"Tool called: retrieve_logs(collection={collection}, limit={limit}, hours_ago={hours_ago}, filters={filters}, search={search}, custom_query={'<custom>' if custom_query else None})"
        )

        api_manager = container.api_manager
        result = await api_manager.retrieve_logs(
            collection=collection,
            limit=limit,
            hours_ago=hours_ago,
            filters=filters,
            search=search,
            custom_query=custom_query,
        )

        logger.info(f"Tool completed: retrieve_logs - Retrieved log entries for collection={collection}")

        return result

    # ── Meta Marketing API helpers ─────────────────────────────────────────────

    def _meta_safety_check(self, container: "ServicesContainer", tool_name: str, **kwargs: Any) -> None:
        """Validate that the Meta operation is permitted under the current safety mode."""
        from supabase_mcp.exceptions import ConfirmationRequiredError as _CRE

        safety_manager = container.safety_manager
        operation = (tool_name, kwargs) if kwargs else tool_name
        try:
            safety_manager.validate_operation(ClientType.META, operation)
        except _CRE as exc:
            import re as _re
            m = _re.search(r"ID: (\S+)", str(exc))
            conf_id = m.group(1) if m else "?"
            raise _CRE(
                f"Operation '{tool_name}' is destructive and requires explicit user confirmation.\n\n"
                f"WHAT TO DO: Review the operation with the user. If approved, run:\n\n"
                f'  confirm_destructive_operation(operation_type="meta", '
                f'confirmation_id="{conf_id}", user_confirmation=True)'
            ) from None

    def _meta_manager(self, container: "ServicesContainer", account_id: str = "") -> Any:
        """Return the MetaAdsCampaignManager for the given account_id.

        If account_id is empty, returns the primary (first) manager.
        Raises APIClientError if Meta is not configured or account_id is unknown.
        """
        from supabase_mcp.exceptions import APIClientError

        managers: dict[str, Any] = getattr(container, "meta_ads_managers", {})

        if not managers:
            raise APIClientError(
                message=(
                    "Meta Ads is not configured. "
                    "Set META_APP_ID, META_APP_SECRET, META_ACCESS_TOKEN, and META_AD_ACCOUNT_IDS."
                ),
                status_code=None,
            )

        if not account_id:
            # Default: primary manager
            primary = container.meta_ads_manager  # type: ignore[attr-defined]
            if primary is None:
                raise APIClientError(message="No primary Meta ad account configured.", status_code=None)
            return primary

        # Normalise prefix
        aid = account_id if account_id.startswith("act_") else f"act_{account_id}"
        if aid not in managers:
            available = ", ".join(managers.keys())
            raise APIClientError(
                message=f"Ad account '{aid}' is not linked. Available accounts: {available}",
                status_code=None,
            )
        return managers[aid]

    async def meta_list_linked_accounts(self, container: "ServicesContainer") -> dict[str, Any]:
        """Return a list of all linked Meta ad accounts."""
        managers: dict[str, Any] = getattr(container, "meta_ads_managers", {})
        account_names = {
            "act_1198372168168124": "طعم ابوغزالة",
            "act_968620118865243": "Yazan Ali",
        }
        return {
            "linked_accounts": [
                {"account_id": aid, "name": account_names.get(aid, aid)}
                for aid in managers
            ]
        }

    async def meta_get_account_info(self, container: "ServicesContainer", account_id: str = "") -> dict[str, Any]:
        return await self._meta_manager(container, account_id).get_account_info()

    async def meta_list_campaigns(
        self, container: "ServicesContainer", status_filter: str | None = None, limit: int = 25
    ) -> dict[str, Any]:
        return await self._meta_manager(container).list_campaigns(status_filter=status_filter, limit=limit)

    async def meta_get_campaign(self, container: "ServicesContainer", campaign_id: str, account_id: str = "") -> dict[str, Any]:
        return await self._meta_manager(container, account_id).get_campaign(campaign_id)

    async def meta_create_campaign(self, container: "ServicesContainer", campaign: dict[str, Any], account_id: str = "") -> dict[str, Any]:
        self._meta_safety_check(container, "meta_create_campaign")
        from supabase_mcp.services.meta_ads.models import CreateCampaignRequest

        return await self._meta_manager(container, account_id).create_campaign(CreateCampaignRequest(**campaign))

    async def meta_update_campaign(
        self, container: "ServicesContainer", campaign_id: str, updates: dict[str, Any], account_id: str = ""
    ) -> dict[str, Any]:
        self._meta_safety_check(container, "meta_update_campaign")
        from supabase_mcp.services.meta_ads.models import UpdateCampaignRequest

        return await self._meta_manager(container, account_id).update_campaign(campaign_id, UpdateCampaignRequest(**updates))

    async def meta_delete_campaign(self, container: "ServicesContainer", campaign_id: str, account_id: str = "") -> dict[str, Any]:
        self._meta_safety_check(container, "meta_delete_campaign", campaign_id=campaign_id)
        return await self._meta_manager(container, account_id).delete_campaign(campaign_id)

    async def meta_toggle_campaign(
        self, container: "ServicesContainer", campaign_id: str, active: bool, account_id: str = ""
    ) -> dict[str, Any]:
        self._meta_safety_check(container, "meta_toggle_campaign")
        return await self._meta_manager(container, account_id).toggle_campaign(campaign_id, active)

    async def meta_list_adsets(
        self, container: "ServicesContainer", campaign_id: str | None = None, limit: int = 25, account_id: str = ""
    ) -> dict[str, Any]:
        return await self._meta_manager(container, account_id).list_adsets(campaign_id=campaign_id, limit=limit)

    async def meta_get_adset(self, container: "ServicesContainer", adset_id: str, account_id: str = "") -> dict[str, Any]:
        return await self._meta_manager(container, account_id).get_adset(adset_id)

    async def meta_create_adset(self, container: "ServicesContainer", adset: dict[str, Any], account_id: str = "") -> dict[str, Any]:
        self._meta_safety_check(container, "meta_create_adset")
        from supabase_mcp.services.meta_ads.models import CreateAdSetRequest

        return await self._meta_manager(container, account_id).create_adset(CreateAdSetRequest(**adset))

    async def meta_update_adset(
        self, container: "ServicesContainer", adset_id: str, updates: dict[str, Any], account_id: str = ""
    ) -> dict[str, Any]:
        self._meta_safety_check(container, "meta_update_adset")
        return await self._meta_manager(container, account_id).update_adset(adset_id, updates)

    async def meta_delete_adset(self, container: "ServicesContainer", adset_id: str, account_id: str = "") -> dict[str, Any]:
        self._meta_safety_check(container, "meta_delete_adset", adset_id=adset_id)
        return await self._meta_manager(container, account_id).delete_adset(adset_id)

    async def meta_list_ads(
        self, container: "ServicesContainer", adset_id: str | None = None, limit: int = 25, account_id: str = ""
    ) -> dict[str, Any]:
        return await self._meta_manager(container, account_id).list_ads(adset_id=adset_id, limit=limit)

    async def meta_get_ad(self, container: "ServicesContainer", ad_id: str, account_id: str = "") -> dict[str, Any]:
        return await self._meta_manager(container, account_id).get_ad(ad_id)

    async def meta_create_ad(self, container: "ServicesContainer", ad: dict[str, Any], account_id: str = "") -> dict[str, Any]:
        self._meta_safety_check(container, "meta_create_ad")
        from supabase_mcp.services.meta_ads.models import CreateAdRequest

        return await self._meta_manager(container, account_id).create_ad(CreateAdRequest(**ad))

    async def meta_update_ad(
        self, container: "ServicesContainer", ad_id: str, updates: dict[str, Any], account_id: str = ""
    ) -> dict[str, Any]:
        self._meta_safety_check(container, "meta_update_ad")
        return await self._meta_manager(container, account_id).update_ad(ad_id, updates)

    async def meta_delete_ad(self, container: "ServicesContainer", ad_id: str, account_id: str = "") -> dict[str, Any]:
        self._meta_safety_check(container, "meta_delete_ad", ad_id=ad_id)
        return await self._meta_manager(container, account_id).delete_ad(ad_id)

    async def meta_get_account_insights(
        self, container: "ServicesContainer", insights: dict[str, Any] = {}, account_id: str = ""
    ) -> dict[str, Any]:
        from supabase_mcp.services.meta_ads.models import InsightsRequest

        return await self._meta_manager(container, account_id).get_account_insights(InsightsRequest(**insights))

    async def meta_get_campaign_insights(
        self, container: "ServicesContainer", campaign_id: str, insights: dict[str, Any] = {}, account_id: str = ""
    ) -> dict[str, Any]:
        from supabase_mcp.services.meta_ads.models import InsightsRequest

        return await self._meta_manager(container, account_id).get_campaign_insights(campaign_id, InsightsRequest(**insights))

    async def meta_get_adset_insights(
        self, container: "ServicesContainer", adset_id: str, insights: dict[str, Any] = {}, account_id: str = ""
    ) -> dict[str, Any]:
        from supabase_mcp.services.meta_ads.models import InsightsRequest

        return await self._meta_manager(container, account_id).get_adset_insights(adset_id, InsightsRequest(**insights))

    async def meta_get_ad_insights(
        self, container: "ServicesContainer", ad_id: str, insights: dict[str, Any] = {}, account_id: str = ""
    ) -> dict[str, Any]:
        from supabase_mcp.services.meta_ads.models import InsightsRequest

        return await self._meta_manager(container, account_id).get_ad_insights(ad_id, InsightsRequest(**insights))

    async def meta_list_creatives(self, container: "ServicesContainer", limit: int = 25, account_id: str = "") -> dict[str, Any]:
        return await self._meta_manager(container, account_id).list_creatives(limit=limit)

    async def meta_create_creative(
        self, container: "ServicesContainer", creative_data: dict[str, Any], account_id: str = ""
    ) -> dict[str, Any]:
        self._meta_safety_check(container, "meta_create_creative")
        return await self._meta_manager(container, account_id).create_creative(creative_data)

    async def meta_exchange_token(
        self, container: "ServicesContainer", short_lived_token: str
    ) -> dict[str, Any]:
        client = container.meta_ads_client  # type: ignore[attr-defined]
        if client is None:
            from supabase_mcp.exceptions import APIClientError

            raise APIClientError(
                message="Meta Ads client is not configured. Set META_APP_ID and META_APP_SECRET.",
                status_code=None,
            )
        return await client.exchange_token(short_lived_token)
