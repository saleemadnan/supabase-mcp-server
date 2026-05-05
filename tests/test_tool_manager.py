from unittest.mock import MagicMock, mock_open, patch

from supabase_mcp.tools.manager import ToolManager, ToolName


class TestToolManager:
    """Tests for the ToolManager class."""

    def test_singleton_pattern(self):
        """Test that ToolManager follows the singleton pattern."""
        # Get two instances
        manager1 = ToolManager.get_instance()
        manager2 = ToolManager.get_instance()

        # They should be the same object
        assert manager1 is manager2

        # Reset the singleton for other tests
        # pylint: disable=protected-access
        # We need to reset the singleton for test isolation
        ToolManager._instance = None  # type: ignore

    @patch("supabase_mcp.tools.manager.Path")
    @patch("supabase_mcp.tools.manager.yaml.safe_load")
    def test_load_descriptions(self, mock_yaml_load: MagicMock, mock_path: MagicMock):
        """Test that descriptions are loaded correctly from YAML files."""
        # Setup mock directory structure
        mock_file_path = MagicMock()
        mock_dir = MagicMock()

        # Mock the Path(__file__) call
        mock_path.return_value = mock_file_path
        mock_file_path.parent = mock_dir
        mock_dir.__truediv__.return_value = mock_dir  # For the / operator

        # Mock directory existence check
        mock_dir.exists.return_value = True

        # Mock the glob to return some YAML files
        mock_file1 = MagicMock()
        mock_file1.name = "database_tools.yaml"
        mock_file2 = MagicMock()
        mock_file2.name = "api_tools.yaml"
        mock_dir.glob.return_value = [mock_file1, mock_file2]

        # Mock the file open and YAML load
        mock_yaml_data = {"get_schemas": "Description for get_schemas", "get_tables": "Description for get_tables"}
        mock_yaml_load.return_value = mock_yaml_data

        # Create a new instance to trigger _load_descriptions
        with patch("builtins.open", mock_open(read_data="dummy yaml content")):
            # We need to create the manager to trigger _load_descriptions
            ToolManager()

        # Verify the descriptions were loaded
        assert mock_dir.glob.call_count > 0
        assert mock_dir.glob.call_args[0][0] == "*.yaml"
        assert mock_yaml_load.call_count >= 1

        # Reset the singleton for other tests
        # pylint: disable=protected-access
        ToolManager._instance = None  # type: ignore

    def test_get_description_valid_tool(self):
        """Test getting a description for a valid tool."""
        # Setup
        manager = ToolManager.get_instance()

        # Force the descriptions to have a known value for testing
        # pylint: disable=protected-access
        # We need to set the descriptions directly for testing
        manager.descriptions = {
            ToolName.GET_SCHEMAS.value: "Description for get_schemas",
            ToolName.GET_TABLES.value: "Description for get_tables",
        }

        # Test
        description = manager.get_description(ToolName.GET_SCHEMAS.value)

        # Verify
        assert description == "Description for get_schemas"

        # Reset the singleton for other tests
        # pylint: disable=protected-access
        ToolManager._instance = None  # type: ignore

    def test_get_description_invalid_tool(self):
        """Test getting a description for an invalid tool."""
        # Setup
        manager = ToolManager.get_instance()

        # Force the descriptions to have a known value for testing
        # pylint: disable=protected-access
        # We need to set the descriptions directly for testing
        manager.descriptions = {
            ToolName.GET_SCHEMAS.value: "Description for get_schemas",
            ToolName.GET_TABLES.value: "Description for get_tables",
        }

        # Test and verify
        description = manager.get_description("nonexistent_tool")
        assert description == ""  # The method returns an empty string for unknown tools

        # Reset the singleton for other tests
        # pylint: disable=protected-access
        ToolManager._instance = None  # type: ignore

    def test_all_tool_names_have_descriptions(self):
        """Test that every ToolName enum member has a non-empty description."""
        # Setup - get a fresh instance
        # Reset the singleton first to ensure we get a clean instance
        # pylint: disable=protected-access
        ToolManager._instance = None  # type: ignore

        # Get a fresh instance that will load the real YAML files
        manager = ToolManager.get_instance()

        # Verify that we have at least some descriptions loaded
        assert len(manager.descriptions) > 0, "No descriptions were loaded"

        # Check that descriptions are not empty
        empty_descriptions: list[str] = []
        for tool_name, description in manager.descriptions.items():
            if not description or len(description.strip()) == 0:
                empty_descriptions.append(tool_name)

        # Fail if we found any empty descriptions
        assert len(empty_descriptions) == 0, f"Found empty descriptions for tools: {empty_descriptions}"

        # Check that every ToolName enum value has a description.
        missing_descriptions = [tool_name.value for tool_name in ToolName if not manager.get_description(tool_name.value)]
        assert not missing_descriptions, f"Missing descriptions for tools: {missing_descriptions}"

        # Reset the singleton for other tests
        # pylint: disable=protected-access
        ToolManager._instance = None  # type: ignore

    @patch.object(ToolManager, "_load_descriptions")
    def test_initialization_loads_descriptions(self, mock_load_descriptions: MagicMock):
        """Test that descriptions are loaded during initialization."""
        # Create a new instance
        # We need to create the manager to trigger __init__
        ToolManager()

        # Verify _load_descriptions was called
        assert mock_load_descriptions.call_count > 0

        # Reset the singleton for other tests
        # pylint: disable=protected-access
        ToolManager._instance = None  # type: ignore

    def test_tool_enum_completeness(self):
        """Test that ToolName enum contains unique values and required core tools."""
        # Get all tool values from the enum
        tool_values = [tool.value for tool in ToolName]

        # Verify enum values are unique. Keep the count dynamic so new tools do not break this test.
        assert len(tool_values) == len(set(tool_values)), "ToolName enum contains duplicate values"

        # Verify specific core tools are included
        assert "retrieve_logs" in tool_values, "retrieve_logs tool is missing from ToolName enum"
        assert "get_auth_status" in tool_values, "get_auth_status tool is missing from ToolName enum"

        # Reset the singleton for other tests
        # pylint: disable=protected-access
        ToolManager._instance = None  # type: ignore
