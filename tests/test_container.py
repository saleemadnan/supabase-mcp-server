from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from supabase_mcp.core.container import ServicesContainer
from supabase_mcp.settings import Settings


class TestContainer:
    """Tests for the Container class functionality."""

    def test_container_initialization(self, container_integration: ServicesContainer):
        """Test that the container is properly initialized with all services."""
        # Verify all services are properly initialized
        assert container_integration.postgres_client is not None
        assert container_integration.api_client is not None
        assert container_integration.sdk_client is not None
        assert container_integration.api_manager is not None
        assert container_integration.safety_manager is not None
        assert container_integration.query_manager is not None
        assert container_integration.tool_manager is not None
        assert container_integration.mcp_server is not None

    def test_container_initialize_method(self, settings_integration: Settings, mock_mcp_server: Any):
        """Test the initialize method creates all services properly."""
        # Create empty container
        container = ServicesContainer(mcp_server=cast(FastMCP, mock_mcp_server))

        # Initialize with settings
        container.initialize_services(settings_integration)

        # Verify all services were created
        assert container.postgres_client is not None
        assert container.api_client is not None
        assert container.sdk_client is not None
        assert container.api_manager is not None
        assert container.safety_manager is not None
        assert container.query_manager is not None
        assert container.tool_manager is not None
        assert container.mcp_server is not None

    @pytest.mark.asyncio
    async def test_connect_services_establishes_pool(self):
        """Auto-login should eagerly create the database connection pool at startup."""
        postgres_client = AsyncMock()
        container = ServicesContainer(postgres_client=postgres_client)

        await container.connect_services()

        postgres_client.ensure_pool.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_services_is_best_effort(self):
        """A failed startup connection must be swallowed so the server still starts."""
        postgres_client = AsyncMock()
        postgres_client.ensure_pool.side_effect = ConnectionError("db unreachable")
        container = ServicesContainer(postgres_client=postgres_client)

        # Should not raise despite the connection failure
        await container.connect_services()

        postgres_client.ensure_pool.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_services_without_client(self):
        """Auto-login should be a no-op when no postgres client is present."""
        container = ServicesContainer(postgres_client=None)

        # Should not raise
        await container.connect_services()
