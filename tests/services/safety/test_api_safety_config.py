"""
Unit tests for the APISafetyConfig class.

This file contains unit test cases for the APISafetyConfig class, which is responsible for
determining the risk level of API operations and whether they are allowed or require confirmation.
"""

import pytest

from supabase_mcp.services.safety.models import OperationRiskLevel, SafetyMode
from supabase_mcp.services.safety.safety_configs import APISafetyConfig, HTTPMethod


@pytest.mark.unit
class TestAPISafetyConfig:
    """Unit tests for the APISafetyConfig class."""

    def test_get_risk_level_low_risk(self):
        """Test getting risk level for low-risk operations (GET requests)."""
        config = APISafetyConfig()
        # API operations are tuples of (method, path, path_params, query_params, request_body)
        operation = ("GET", "/v1/projects/{ref}/functions", {}, {}, {})
        risk_level = config.get_risk_level(operation)
        assert risk_level == OperationRiskLevel.LOW

    def test_get_risk_level_medium_risk(self):
        """Test getting risk level for medium-risk operations (POST/PUT/PATCH)."""
        config = APISafetyConfig()

        # Test POST request
        operation = ("POST", "/v1/projects/{ref}/functions", {}, {}, {})
        risk_level = config.get_risk_level(operation)
        assert risk_level == OperationRiskLevel.MEDIUM

        # Test PUT request
        operation = ("PUT", "/v1/projects/{ref}/functions", {}, {}, {})
        risk_level = config.get_risk_level(operation)
        assert risk_level == OperationRiskLevel.MEDIUM

        # Test PATCH request
        operation = ("PATCH", "/v1/projects/{ref}/functions/{function_slug}", {}, {}, {})
        risk_level = config.get_risk_level(operation)
        assert risk_level == OperationRiskLevel.MEDIUM

    def test_get_risk_level_high_risk(self):
        """Test getting risk level for high-risk operations."""
        config = APISafetyConfig()

        # Test DELETE request for a function
        operation = ("DELETE", "/v1/projects/{ref}/functions/{function_slug}", {}, {}, {})
        risk_level = config.get_risk_level(operation)
        assert risk_level == OperationRiskLevel.HIGH

        # Test other high-risk operations
        high_risk_paths = [
            "/v1/projects/{ref}/branches/{branch_id}",
            "/v1/projects/{ref}/custom-hostname",
            "/v1/projects/{ref}/network-bans",
        ]

        for path in high_risk_paths:
            operation = ("DELETE", path, {}, {}, {})
            risk_level = config.get_risk_level(operation)
            assert risk_level == OperationRiskLevel.HIGH, f"Path {path} should be HIGH risk"

    def test_get_risk_level_extreme_risk(self):
        """Test getting risk level for extreme-risk operations."""
        config = APISafetyConfig()

        # Test DELETE request for a project
        operation = ("DELETE", "/v1/projects/{ref}", {}, {}, {})
        risk_level = config.get_risk_level(operation)
        assert risk_level == OperationRiskLevel.EXTREME

    def test_is_operation_allowed(self):
        """Test if operations are allowed based on risk level and safety mode."""
        config = APISafetyConfig()

        # Low risk operations should be allowed in both safe and unsafe modes
        assert config.is_operation_allowed(OperationRiskLevel.LOW, SafetyMode.SAFE) is True
        assert config.is_operation_allowed(OperationRiskLevel.LOW, SafetyMode.UNSAFE) is True

        # Medium/high risk operations should only be allowed in unsafe mode
        assert config.is_operation_allowed(OperationRiskLevel.MEDIUM, SafetyMode.SAFE) is False
        assert config.is_operation_allowed(OperationRiskLevel.MEDIUM, SafetyMode.UNSAFE) is True
        assert config.is_operation_allowed(OperationRiskLevel.HIGH, SafetyMode.SAFE) is False
        assert config.is_operation_allowed(OperationRiskLevel.HIGH, SafetyMode.UNSAFE) is True

        # Extreme risk operations should not be allowed in safe mode
        assert config.is_operation_allowed(OperationRiskLevel.EXTREME, SafetyMode.SAFE) is False
        # In the current implementation, extreme risk operations are never allowed
        assert config.is_operation_allowed(OperationRiskLevel.EXTREME, SafetyMode.UNSAFE) is False

    def test_needs_confirmation(self):
        """Test if operations need confirmation based on risk level."""
        config = APISafetyConfig()

        # Low and medium risk operations should not need confirmation
        assert config.needs_confirmation(OperationRiskLevel.LOW) is False
        assert config.needs_confirmation(OperationRiskLevel.MEDIUM) is False

        # High and extreme risk operations should need confirmation
        assert config.needs_confirmation(OperationRiskLevel.HIGH) is True
        assert config.needs_confirmation(OperationRiskLevel.EXTREME) is True

    def test_path_matching(self):
        """Test that path patterns are correctly matched."""
        config = APISafetyConfig()

        # Test exact path matching
        operation = ("GET", "/v1/projects/{ref}/functions", {}, {}, {})
        assert config.get_risk_level(operation) == OperationRiskLevel.LOW

        # Test path with parameters
        operation = ("GET", "/v1/projects/abc123/functions", {}, {}, {})
        assert config.get_risk_level(operation) == OperationRiskLevel.LOW

        # Test path with multiple parameters
        operation = ("DELETE", "/v1/projects/abc123/functions/my-function", {}, {}, {})
        assert config.get_risk_level(operation) == OperationRiskLevel.HIGH

        # Test path that doesn't match any pattern (should default to MEDIUM for non-GET)
        operation = ("DELETE", "/v1/some/unknown/path", {}, {}, {})
        assert config.get_risk_level(operation) == OperationRiskLevel.LOW

        # Test path that doesn't match any pattern (should default to LOW for GET)
        operation = ("GET", "/v1/some/unknown/path", {}, {}, {})
        assert config.get_risk_level(operation) == OperationRiskLevel.LOW

    def test_method_case_insensitivity(self):
        """Test that HTTP method matching is case-insensitive."""
        config = APISafetyConfig()

        # Test with lowercase method
        operation = ("get", "/v1/projects/{ref}/functions", {}, {}, {})
        assert config.get_risk_level(operation) == OperationRiskLevel.LOW

        # Test with uppercase method
        operation = ("GET", "/v1/projects/{ref}/functions", {}, {}, {})
        assert config.get_risk_level(operation) == OperationRiskLevel.LOW

        # Test with mixed case method
        operation = ("GeT", "/v1/projects/{ref}/functions", {}, {}, {})
        assert config.get_risk_level(operation) == OperationRiskLevel.LOW

    def test_path_safety_config_structure(self):
        """Test that the PATH_SAFETY_CONFIG structure is correctly defined."""
        config = APISafetyConfig()

        # Check that the config has the expected structure
        assert hasattr(config, "PATH_SAFETY_CONFIG")

        # Check that risk levels are represented as keys
        assert OperationRiskLevel.MEDIUM in config.PATH_SAFETY_CONFIG
        assert OperationRiskLevel.HIGH in config.PATH_SAFETY_CONFIG
        assert OperationRiskLevel.EXTREME in config.PATH_SAFETY_CONFIG

        # Check that each risk level has a dictionary of methods to paths
        for _risk_level, methods_dict in config.PATH_SAFETY_CONFIG.items():
            assert isinstance(methods_dict, dict)
            for method, paths in methods_dict.items():
                assert isinstance(method, HTTPMethod)
                assert isinstance(paths, list)
                for path in paths:
                    assert isinstance(path, str)
