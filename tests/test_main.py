import asyncio
import shutil
from unittest.mock import patch

import pytest

from supabase_mcp.core.container import ServicesContainer
from supabase_mcp.logger import logger
from supabase_mcp.main import run_inspector, run_server
from supabase_mcp.services.safety.models import ClientType
from supabase_mcp.tools.manager import ToolName

# === UNIT TESTS ===


class TestMain:
    """Tests for the main application functionality."""

    @pytest.mark.unit
    def test_mcp_server_initializes(self, container_integration: ServicesContainer):
        """Test that the MCP server initializes correctly."""
        # Verify server name
        mcp = container_integration.mcp_server
        assert mcp.name == "supabase"

        # Verify MCP server is created but not yet initialized with tools
        tools = asyncio.run(mcp.list_tools())
        logger.info(f"Found {len(tools)} MCP tools registered in basic container")

        # At this point, no tools should be registered yet
        assert len(tools) == 0, f"Expected 0 tools in basic container, but got {len(tools)}"

    @pytest.mark.unit
    def test_services_container_initialization(
        self,
        initialized_container_integration: ServicesContainer,
    ):
        """Test that the services container is correctly initialized."""
        # Verify container has all required services
        container = initialized_container_integration
        assert container.postgres_client is not None
        assert container.api_client is not None
        assert container.sdk_client is not None
        assert container.api_manager is not None
        assert container.safety_manager is not None
        assert container.query_manager is not None
        assert container.tool_manager is not None

        # Verify the container is fully initialized
        # Check that safety manager has been initialized by verifying it has configs registered
        safety_manager = container.safety_manager
        assert safety_manager.get_safety_mode(ClientType.DATABASE) is not None
        assert safety_manager.get_safety_mode(ClientType.API) is not None

    @pytest.mark.unit
    def test_tool_registration(self, tools_registry_integration: ServicesContainer):
        """Test that all ToolName enum members are registered as MCP tools."""

        # Get the tool manager from the container
        tool_manager = tools_registry_integration.tool_manager
        assert tool_manager is not None, "Tool manager should be initialized"

        # Get the MCP server from the container
        mcp = tools_registry_integration.mcp_server

        # Verify tools are registered in MCP
        registered_tools = asyncio.run(mcp.list_tools())
        registered_tool_names = {tool.name for tool in registered_tools}
        expected_tool_names = {tool_name.value for tool_name in ToolName}

        # Keep this assertion dynamic so adding tools does not require updating a hard-coded count.
        assert len(registered_tools) == len(expected_tool_names), (
            f"Expected {len(expected_tool_names)} tools, but got {len(registered_tools)}"
        )

        # Log the actual number of tools for reference
        logger.info(f"Found {len(registered_tools)} MCP tools registered")

        # Verify each tool has proper MCP protocol structure
        for tool in registered_tools:
            assert tool.name, "Tool must have a name"
            assert tool.description, "Tool must have a description"
            assert tool.inputSchema, "Tool must have an input schema"

        # Check that every ToolName enum value is registered by its string value.
        missing_tools = sorted(expected_tool_names - registered_tool_names)
        unexpected_tools = sorted(registered_tool_names - expected_tool_names)

        assert not missing_tools, f"Missing registered tools: {missing_tools}"
        assert not unexpected_tools, f"Unexpected registered tools: {unexpected_tools}"

        # Log all available tools for debugging
        tool_list = ", ".join(sorted(registered_tool_names))
        logger.info(f"Available MCP tools: {tool_list}")

    @pytest.mark.unit
    def test_run_server_starts(self):
        """Test that run_server starts the server."""
        # Patch the global mcp instance and its run method
        with patch("supabase_mcp.main.mcp") as mock_mcp:
            # Call run_server which should use the global mcp instance
            run_server()
            mock_mcp.run.assert_called_once()

    @pytest.mark.unit
    def test_inspector_mode(self):
        """Test that inspector mode initializes correctly."""
        # This test is fine as is since it's testing the global function
        # and mocking an external dependency
        with patch("mcp.cli.cli.dev") as mock_dev:
            # Patch __file__ in the main module to match what we expect
            with patch("supabase_mcp.main.__file__", __file__):
                run_inspector()
                mock_dev.assert_called_once_with(__file__)

    @pytest.mark.unit
    def test_server_command_exists(self):
        """Test that the server command exists and is executable when installed."""
        # Check if the command exists in PATH
        server_path = shutil.which("supabase-mcp-server")
        if server_path is None:
            pytest.skip("supabase-mcp-server command is not installed in PATH")

        # Check if the file is executable
        assert shutil.which("supabase-mcp-server") == server_path
