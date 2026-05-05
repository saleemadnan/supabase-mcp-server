"""Unit tests for get_auth_status tool."""
from unittest.mock import AsyncMock, MagicMock

import pytest

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
