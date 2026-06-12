"""Unit tests for get_auth_status tool."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from supabase_mcp.core.feature_manager import FeatureManager
from supabase_mcp.tools.manager import ToolName


class TestGetAuthStatus:
    """Tests for the get_auth_status tool."""

    @pytest.mark.asyncio
    async def test_get_auth_status_returns_dict(self):
        """Test that get_auth_status returns a dictionary."""
        mock_feature_manager = AsyncMock()
        mock_feature_manager.execute_tool.return_value = {
            "personal_access_token": "configured",
            "service_role_key": "configured",
            "supabase_url": "configured",
            "db_url": "configured",
            "api_connection": "healthy",
            "db_connection": "healthy",
        }

        result = await mock_feature_manager.execute_tool(
            ToolName.GET_AUTH_STATUS,
            services_container=MagicMock(),
        )

        assert isinstance(result, dict)
        assert "personal_access_token" in result
        assert "service_role_key" in result
        assert "supabase_url" in result
        assert "db_url" in result
        assert "api_connection" in result
        assert "db_connection" in result

    @pytest.mark.asyncio
    async def test_get_auth_status_missing_credentials(self):
        """Test that get_auth_status correctly reports missing credentials."""
        mock_feature_manager = AsyncMock()
        mock_feature_manager.execute_tool.return_value = {
            "personal_access_token": "missing",
            "service_role_key": "missing",
            "supabase_url": "configured",
            "db_url": "configured",
            "api_connection": "unreachable",
            "db_connection": "healthy",
        }

        result = await mock_feature_manager.execute_tool(
            ToolName.GET_AUTH_STATUS,
            services_container=MagicMock(),
        )

        assert result["personal_access_token"] == "missing"
        assert result["service_role_key"] == "missing"
        assert result["api_connection"] == "unreachable"

    @pytest.mark.asyncio
    async def test_get_auth_status_all_configured(self):
        """Test that get_auth_status reports all credentials as configured."""
        mock_feature_manager = AsyncMock()
        mock_feature_manager.execute_tool.return_value = {
            "personal_access_token": "configured",
            "service_role_key": "configured",
            "supabase_url": "configured",
            "db_url": "configured",
            "api_connection": "healthy",
            "db_connection": "healthy",
        }

        result = await mock_feature_manager.execute_tool(
            ToolName.GET_AUTH_STATUS,
            services_container=MagicMock(),
        )

        assert result["personal_access_token"] == "configured"
        assert result["service_role_key"] == "configured"
        assert result["supabase_url"] == "configured"
        assert result["db_url"] == "configured"
        assert result["api_connection"] == "healthy"
        assert result["db_connection"] == "healthy"

    def test_get_auth_status_tool_name_enum(self):
        """Test that GET_AUTH_STATUS is correctly defined in ToolName enum."""
        assert ToolName.GET_AUTH_STATUS == "get_auth_status"
        assert ToolName.GET_AUTH_STATUS.value == "get_auth_status"

    @pytest.mark.asyncio
    async def test_get_auth_status_is_read_only(self):
        """Test that get_auth_status tool is called without write parameters."""
        mock_feature_manager = AsyncMock()
        mock_feature_manager.execute_tool.return_value = {}
        mock_container = MagicMock()

        await mock_feature_manager.execute_tool(
            ToolName.GET_AUTH_STATUS,
            services_container=mock_container,
        )

        mock_feature_manager.execute_tool.assert_called_once_with(
            ToolName.GET_AUTH_STATUS,
            services_container=mock_container,
        )


class TestGetAuthStatusImplementation:
    """Tests for the real FeatureManager.get_auth_status implementation."""

    def _build_feature_manager(self) -> FeatureManager:
        feature_manager = FeatureManager(api_client=AsyncMock())
        feature_manager.check_feature_access = AsyncMock(return_value=None)
        return feature_manager

    @pytest.mark.asyncio
    async def test_execute_tool_dispatches_get_auth_status(self):
        """ToolName.GET_AUTH_STATUS must be dispatched, not raise 'Unknown tool'."""
        feature_manager = self._build_feature_manager()

        mock_container = MagicMock()
        mock_container.api_client.execute_request = AsyncMock(return_value={})
        mock_container.postgres_client.ensure_pool = AsyncMock(return_value=None)

        result = await feature_manager.execute_tool(
            ToolName.GET_AUTH_STATUS,
            services_container=mock_container,
        )

        assert result["api_connection"] == "healthy"
        assert result["db_connection"] == "healthy"
        assert "personal_access_token" in result
        assert "service_role_key" in result
        assert "supabase_url" in result
        assert "db_url" in result

    @pytest.mark.asyncio
    async def test_get_auth_status_reports_unreachable_connections(self):
        """Connection failures are reported as 'unreachable' rather than raised."""
        feature_manager = self._build_feature_manager()

        mock_container = MagicMock()
        mock_container.api_client.execute_request = AsyncMock(side_effect=Exception("boom"))
        mock_container.postgres_client.ensure_pool = AsyncMock(side_effect=Exception("boom"))

        result = await feature_manager.execute_tool(
            ToolName.GET_AUTH_STATUS,
            services_container=mock_container,
        )

        assert result["api_connection"] == "unreachable"
        assert result["db_connection"] == "unreachable"
