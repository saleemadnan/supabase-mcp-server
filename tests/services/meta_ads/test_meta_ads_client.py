"""Unit tests for MetaAdsClient and MetaAdsCampaignManager."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from supabase_mcp.clients.meta_ads_client import META_GRAPH_API_BASE, MetaAdsClient
from supabase_mcp.exceptions import APIClientError
from supabase_mcp.services.meta_ads.campaign_manager import MetaAdsCampaignManager
from supabase_mcp.services.meta_ads.models import (
    BillingEvent,
    CampaignStatus,
    CreateAdSetRequest,
    CreateCampaignRequest,
    InsightsRequest,
    LegacyObjective,
    ODAXObjective,
    OptimizationGoal,
    UpdateCampaignRequest,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    """Reset singletons before and after every test."""
    MetaAdsClient.reset()
    MetaAdsCampaignManager.reset()
    yield
    MetaAdsClient.reset()
    MetaAdsCampaignManager.reset()


@pytest.fixture
def client() -> MetaAdsClient:
    return MetaAdsClient(
        access_token="test_token",
        app_id="app_id",
        app_secret="app_secret",
        api_version="v21.0",
        timeout=10.0,
    )


@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Return a mock httpx.Response with a successful JSON body."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.is_success = True
    response.json.return_value = {"id": "123", "name": "Test"}
    response.text = '{"id": "123", "name": "Test"}'
    return response


@pytest.fixture
def manager(client: MetaAdsClient) -> MetaAdsCampaignManager:
    return MetaAdsCampaignManager(client=client, ad_account_id="987654321")


# ─── MetaAdsClient unit tests ────────────────────────────────────────────────


@pytest.mark.unit
class TestMetaAdsClient:
    def test_singleton(self) -> None:
        a = MetaAdsClient.get_instance("tok", "aid", "sec")
        b = MetaAdsClient.get_instance("tok2", "aid2", "sec2")
        assert a is b

    def test_reset_clears_singleton(self) -> None:
        a = MetaAdsClient.get_instance("tok", "aid", "sec")
        MetaAdsClient.reset()
        b = MetaAdsClient.get_instance("tok2", "aid2", "sec2")
        assert a is not b

    def test_api_version_and_timeout_stored(self) -> None:
        c = MetaAdsClient("tok", "aid", "sec", api_version="v20.0", timeout=5.0)
        assert c._api_version == "v20.0"
        assert c._timeout == 5.0

    def test_inject_token(self, client: MetaAdsClient) -> None:
        result = client._inject_token({"fields": "id,name"})
        assert result["access_token"] == "test_token"
        assert result["fields"] == "id,name"

    def test_inject_token_none_params(self, client: MetaAdsClient) -> None:
        result = client._inject_token(None)
        assert result == {"access_token": "test_token"}

    def test_inject_token_does_not_mutate_original(self, client: MetaAdsClient) -> None:
        original = {"fields": "id"}
        client._inject_token(original)
        assert "access_token" not in original

    @pytest.mark.asyncio
    async def test_ensure_client_creates_async_client(self, client: MetaAdsClient) -> None:
        http = await client._ensure_client()
        assert isinstance(http, httpx.AsyncClient)
        assert str(http.base_url) == f"{META_GRAPH_API_BASE}/v21.0/"
        await client.close()

    @pytest.mark.asyncio
    async def test_ensure_client_reuses_open_client(self, client: MetaAdsClient) -> None:
        first = await client._ensure_client()
        second = await client._ensure_client()
        assert first is second
        await client.close()

    @pytest.mark.asyncio
    async def test_close_sets_client_none(self, client: MetaAdsClient) -> None:
        await client._ensure_client()
        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_exchange_token_raises_on_api_error(self, client: MetaAdsClient) -> None:
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 400
        error_response.is_success = False
        error_response.json.return_value = {"error": {"message": "Invalid token"}}
        error_response.text = '{"error": {"message": "Invalid token"}}'

        with patch.object(client, "_ensure_client", new_callable=AsyncMock) as mock_ensure:
            mock_http = MagicMock()
            mock_ensure.return_value = mock_http
            with patch.object(client, "prepare_request", return_value=MagicMock()):
                with patch.object(client, "send_request", new_callable=AsyncMock, return_value=error_response):
                    with patch.object(client, "parse_response", return_value={"error": {"message": "Invalid token"}}):
                        with patch.object(client, "handle_error_response", side_effect=APIClientError("Invalid token", 400)):
                            with pytest.raises(APIClientError):
                                await client.exchange_token("bad_token")

    @pytest.mark.asyncio
    async def test_exchange_token_wraps_unexpected_error(self, client: MetaAdsClient) -> None:
        with patch.object(client, "_ensure_client", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            with pytest.raises(APIClientError, match="Token exchange failed"):
                await client.exchange_token("tok")


# ─── MetaAdsCampaignManager unit tests ───────────────────────────────────────


@pytest.mark.unit
class TestMetaAdsCampaignManager:
    def test_account_id_prefix_added(self, client: MetaAdsClient) -> None:
        mgr = MetaAdsCampaignManager(client, "123456789")
        assert mgr._account_id == "act_123456789"

    def test_account_id_prefix_not_doubled(self, client: MetaAdsClient) -> None:
        mgr = MetaAdsCampaignManager(client, "act_123456789")
        assert mgr._account_id == "act_123456789"

    def test_singleton(self, client: MetaAdsClient) -> None:
        a = MetaAdsCampaignManager.get_instance(client, "111")
        b = MetaAdsCampaignManager.get_instance(client, "222")
        assert a is b

    def test_reset_clears_singleton(self, client: MetaAdsClient) -> None:
        a = MetaAdsCampaignManager.get_instance(client, "111")
        MetaAdsCampaignManager.reset()
        b = MetaAdsCampaignManager.get_instance(client, "222")
        assert a is not b

    @pytest.mark.asyncio
    async def test_get_account_info(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.get = AsyncMock(return_value={"id": "act_987654321", "name": "Test Account"})
        result = await manager.get_account_info()
        manager._client.get.assert_called_once()
        assert result["id"] == "act_987654321"

    @pytest.mark.asyncio
    async def test_list_campaigns_default(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.get = AsyncMock(return_value={"data": []})
        await manager.list_campaigns()
        call_args = manager._client.get.call_args
        assert "act_987654321/campaigns" in call_args[0][0]
        assert call_args[1]["params"]["limit"] == 25

    @pytest.mark.asyncio
    async def test_list_campaigns_with_status_filter(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.get = AsyncMock(return_value={"data": []})
        await manager.list_campaigns(status_filter="ACTIVE")
        call_args = manager._client.get.call_args
        assert call_args[1]["params"]["effective_status"] == ["ACTIVE"]

    @pytest.mark.asyncio
    async def test_create_campaign(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.post = AsyncMock(return_value={"id": "camp_001"})
        req = CreateCampaignRequest(
            name="My Campaign",
            objective=ODAXObjective.TRAFFIC,
            status=CampaignStatus.PAUSED,
        )
        result = await manager.create_campaign(req)
        assert result["id"] == "camp_001"
        body = manager._client.post.call_args[1]["body"]
        assert body["name"] == "My Campaign"
        assert body["objective"] == "TRAFFIC"
        assert body["status"] == "PAUSED"

    @pytest.mark.asyncio
    async def test_create_campaign_with_budget(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.post = AsyncMock(return_value={"id": "camp_002"})
        req = CreateCampaignRequest(
            name="Budget Campaign",
            objective=ODAXObjective.SALES,
            daily_budget=5000,
        )
        await manager.create_campaign(req)
        body = manager._client.post.call_args[1]["body"]
        assert body["daily_budget"] == 5000
        assert "lifetime_budget" not in body

    @pytest.mark.asyncio
    async def test_update_campaign(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.post = AsyncMock(return_value={"success": True})
        req = UpdateCampaignRequest(name="Updated Name", status=CampaignStatus.ACTIVE)
        await manager.update_campaign("camp_001", req)
        body = manager._client.post.call_args[1]["body"]
        assert body["name"] == "Updated Name"
        assert body["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_update_campaign_partial(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.post = AsyncMock(return_value={"success": True})
        req = UpdateCampaignRequest(name="Only Name")
        await manager.update_campaign("camp_001", req)
        body = manager._client.post.call_args[1]["body"]
        assert "status" not in body
        assert body["name"] == "Only Name"

    @pytest.mark.asyncio
    async def test_delete_campaign(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.delete = AsyncMock(return_value={"success": True})
        result = await manager.delete_campaign("camp_001")
        manager._client.delete.assert_called_once_with("/camp_001")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_toggle_campaign_activate(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.post = AsyncMock(return_value={"success": True})
        await manager.toggle_campaign("camp_001", active=True)
        body = manager._client.post.call_args[1]["body"]
        assert body["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_toggle_campaign_pause(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.post = AsyncMock(return_value={"success": True})
        await manager.toggle_campaign("camp_001", active=False)
        body = manager._client.post.call_args[1]["body"]
        assert body["status"] == "PAUSED"

    @pytest.mark.asyncio
    async def test_create_adset(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.post = AsyncMock(return_value={"id": "adset_001"})
        req = CreateAdSetRequest(
            campaign_id="camp_001",
            name="Test AdSet",
            billing_event=BillingEvent.IMPRESSIONS,
            optimization_goal=OptimizationGoal.REACH,
            daily_budget=2000,
            targeting={"geo_locations": {"countries": ["SA"]}},
        )
        result = await manager.create_adset(req)
        assert result["id"] == "adset_001"
        body = manager._client.post.call_args[1]["body"]
        assert body["campaign_id"] == "camp_001"
        assert body["billing_event"] == "IMPRESSIONS"

    @pytest.mark.asyncio
    async def test_get_account_insights_default_fields(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.get = AsyncMock(return_value={"data": [{"impressions": "1000"}]})
        req = InsightsRequest()
        await manager.get_account_insights(req)
        params = manager._client.get.call_args[1]["params"]
        assert "impressions" in params["fields"]
        assert "spend" in params["fields"]
        assert params["date_preset"] == "last_7d"

    @pytest.mark.asyncio
    async def test_get_campaign_insights_with_breakdowns(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.get = AsyncMock(return_value={"data": []})
        req = InsightsRequest(breakdowns=["age", "gender"])
        await manager.get_campaign_insights("camp_001", req)
        params = manager._client.get.call_args[1]["params"]
        assert params["breakdowns"] == "age,gender"

    def test_create_campaign_accepts_odax_objective(self) -> None:
        req = CreateCampaignRequest(name="ODAX", objective=ODAXObjective.AWARENESS)
        assert req.objective == ODAXObjective.AWARENESS

    def test_create_campaign_accepts_legacy_objective(self) -> None:
        req = CreateCampaignRequest(name="Legacy", objective=LegacyObjective.CONVERSIONS)
        assert req.objective == LegacyObjective.CONVERSIONS

    def test_create_campaign_accepts_string_objective(self) -> None:
        req = CreateCampaignRequest(name="String", objective="TRAFFIC")  # type: ignore[arg-type]
        assert req.objective.value == "TRAFFIC"

    @pytest.mark.asyncio
    async def test_list_creatives(self, manager: MetaAdsCampaignManager) -> None:
        manager._client.get = AsyncMock(return_value={"data": []})
        await manager.list_creatives()
        call_args = manager._client.get.call_args
        assert "adcreatives" in call_args[0][0]


# ─── MetaSafetyConfig unit tests ─────────────────────────────────────────────


@pytest.mark.unit
class TestMetaSafetyConfig:
    def test_read_ops_are_low_risk(self) -> None:
        from supabase_mcp.services.safety.safety_configs import MetaSafetyConfig
        from supabase_mcp.services.safety.models import OperationRiskLevel

        cfg = MetaSafetyConfig()
        for op in ["meta_get_account_info", "meta_list_campaigns", "meta_get_campaign_insights"]:
            assert cfg.get_risk_level(op) == OperationRiskLevel.LOW

    def test_write_ops_are_medium_risk(self) -> None:
        from supabase_mcp.services.safety.safety_configs import MetaSafetyConfig
        from supabase_mcp.services.safety.models import OperationRiskLevel

        cfg = MetaSafetyConfig()
        for op in ["meta_create_campaign", "meta_update_campaign", "meta_toggle_campaign", "meta_create_adset"]:
            assert cfg.get_risk_level(op) == OperationRiskLevel.MEDIUM

    def test_delete_ops_are_high_risk(self) -> None:
        from supabase_mcp.services.safety.safety_configs import MetaSafetyConfig
        from supabase_mcp.services.safety.models import OperationRiskLevel

        cfg = MetaSafetyConfig()
        for op in ["meta_delete_campaign", "meta_delete_adset", "meta_delete_ad"]:
            assert cfg.get_risk_level(op) == OperationRiskLevel.HIGH

    def test_tuple_operation_extracts_tool_name(self) -> None:
        from supabase_mcp.services.safety.safety_configs import MetaSafetyConfig
        from supabase_mcp.services.safety.models import OperationRiskLevel

        cfg = MetaSafetyConfig()
        assert cfg.get_risk_level(("meta_delete_campaign", {"campaign_id": "123"})) == OperationRiskLevel.HIGH
        assert cfg.get_risk_level(("meta_list_campaigns", {})) == OperationRiskLevel.LOW

    def test_unknown_op_defaults_to_medium(self) -> None:
        from supabase_mcp.services.safety.safety_configs import MetaSafetyConfig
        from supabase_mcp.services.safety.models import OperationRiskLevel

        cfg = MetaSafetyConfig()
        assert cfg.get_risk_level("meta_unknown_tool") == OperationRiskLevel.MEDIUM

    def test_write_op_blocked_in_safe_mode(self) -> None:
        from supabase_mcp.exceptions import OperationNotAllowedError
        from supabase_mcp.services.safety.models import ClientType, SafetyMode
        from supabase_mcp.services.safety.safety_manager import SafetyManager

        SafetyManager.reset()
        mgr = SafetyManager.get_instance()
        mgr.register_safety_configs()
        # Safe mode is the default
        with pytest.raises(OperationNotAllowedError):
            mgr.validate_operation(ClientType.META, "meta_create_campaign")
        SafetyManager.reset()

    def test_delete_op_requires_confirmation_in_unsafe_mode(self) -> None:
        from supabase_mcp.exceptions import ConfirmationRequiredError
        from supabase_mcp.services.safety.models import ClientType, SafetyMode
        from supabase_mcp.services.safety.safety_manager import SafetyManager

        SafetyManager.reset()
        mgr = SafetyManager.get_instance()
        mgr.register_safety_configs()
        mgr.set_safety_mode(ClientType.META, SafetyMode.UNSAFE)
        with pytest.raises(ConfirmationRequiredError):
            mgr.validate_operation(ClientType.META, ("meta_delete_campaign", {"campaign_id": "123"}))
        SafetyManager.reset()

    def test_read_op_always_allowed(self) -> None:
        from supabase_mcp.services.safety.models import ClientType
        from supabase_mcp.services.safety.safety_manager import SafetyManager

        SafetyManager.reset()
        mgr = SafetyManager.get_instance()
        mgr.register_safety_configs()
        # No exception raised
        mgr.validate_operation(ClientType.META, "meta_list_campaigns")
        SafetyManager.reset()
