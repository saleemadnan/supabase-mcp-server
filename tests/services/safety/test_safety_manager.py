import time

import pytest

from supabase_mcp.exceptions import ConfirmationRequiredError, OperationNotAllowedError
from supabase_mcp.services.safety.models import ClientType, OperationRiskLevel, SafetyMode
from supabase_mcp.services.safety.safety_configs import SafetyConfigBase
from supabase_mcp.services.safety.safety_manager import SafetyManager


class MockSafetyConfig(SafetyConfigBase[str]):
    """Mock safety configuration for testing."""

    def get_risk_level(self, operation: str) -> OperationRiskLevel:
        """Get the risk level for an operation."""
        if operation == "low_risk":
            return OperationRiskLevel.LOW
        elif operation == "medium_risk":
            return OperationRiskLevel.MEDIUM
        elif operation == "high_risk":
            return OperationRiskLevel.HIGH
        elif operation == "extreme_risk":
            return OperationRiskLevel.EXTREME
        else:
            return OperationRiskLevel.LOW


@pytest.mark.unit
class TestSafetyManager:
    """Unit test cases for the SafetyManager class."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and teardown for each test."""
        # Reset the singleton before each test
        # pylint: disable=protected-access
        SafetyManager._instance = None  # type: ignore
        yield
        # Reset the singleton after each test
        SafetyManager._instance = None  # type: ignore

    def test_singleton_pattern(self):
        """Test that SafetyManager follows the singleton pattern."""
        # Get two instances of the SafetyManager
        manager1 = SafetyManager.get_instance()
        manager2 = SafetyManager.get_instance()

        # Verify they are the same instance
        assert manager1 is manager2

        # Verify that creating a new instance directly doesn't affect the singleton
        direct_instance = SafetyManager()
        assert direct_instance is not manager1

    def test_register_config(self):
        """Test registering a safety configuration."""
        manager = SafetyManager.get_instance()
        mock_config = MockSafetyConfig()

        # Register the config for DATABASE client type
        manager.register_config(ClientType.DATABASE, mock_config)

        # Verify the config was registered
        assert manager._safety_configs[ClientType.DATABASE] is mock_config

        # Test that registering a config for the same client type overwrites the previous config
        new_mock_config = MockSafetyConfig()
        manager.register_config(ClientType.DATABASE, new_mock_config)
        assert manager._safety_configs[ClientType.DATABASE] is new_mock_config

    def test_get_safety_mode_default(self):
        """Test getting the default safety mode for an unregistered client type."""
        manager = SafetyManager.get_instance()

        # Create a custom client type that hasn't been registered
        class CustomClientType(str):
            pass

        custom_type = CustomClientType("custom")

        # Verify that getting a safety mode for an unregistered client type returns SafetyMode.SAFE
        assert manager.get_safety_mode(custom_type) == SafetyMode.SAFE  # type: ignore

    def test_get_safety_mode_registered(self):
        """Test getting the safety mode for a registered client type."""
        manager = SafetyManager.get_instance()

        # Set a safety mode for a client type
        manager._safety_modes[ClientType.API] = SafetyMode.UNSAFE

        # Verify it's returned correctly
        assert manager.get_safety_mode(ClientType.API) == SafetyMode.UNSAFE

    def test_set_safety_mode(self):
        """Test setting the safety mode for a client type."""
        manager = SafetyManager.get_instance()

        # Set a safety mode for a client type
        manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)

        # Verify it was updated
        assert manager._safety_modes[ClientType.DATABASE] == SafetyMode.UNSAFE

        # Change it back to SAFE
        manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

        # Verify it was updated again
        assert manager._safety_modes[ClientType.DATABASE] == SafetyMode.SAFE

    def test_validate_operation_allowed(self):
        """Test validating an operation that is allowed."""
        manager = SafetyManager.get_instance()
        mock_config = MockSafetyConfig()

        # Register the config
        manager.register_config(ClientType.DATABASE, mock_config)

        # Set safety mode to SAFE
        manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

        # Validate a low risk operation (should be allowed in SAFE mode)
        # This should not raise an exception
        manager.validate_operation(ClientType.DATABASE, "low_risk")

        # Set safety mode to UNSAFE
        manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)

        # Validate medium risk operation (should be allowed in UNSAFE mode)
        # This should not raise an exception
        manager.validate_operation(ClientType.DATABASE, "medium_risk")

        # High risk operations require confirmation, so we test with confirmation=True
        manager.validate_operation(ClientType.DATABASE, "high_risk", has_confirmation=True)

    def test_validate_operation_not_allowed(self):
        """Test validating an operation that is not allowed."""
        manager = SafetyManager.get_instance()
        mock_config = MockSafetyConfig()

        # Register the config
        manager.register_config(ClientType.DATABASE, mock_config)

        # Set safety mode to SAFE
        manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

        # Validate medium risk operation (should not be allowed in SAFE mode)
        with pytest.raises(OperationNotAllowedError):
            manager.validate_operation(ClientType.DATABASE, "medium_risk")

        # Validate high risk operation (should not be allowed in SAFE mode)
        with pytest.raises(OperationNotAllowedError):
            manager.validate_operation(ClientType.DATABASE, "high_risk")

        # Validate extreme risk operation (should not be allowed in SAFE mode)
        with pytest.raises(OperationNotAllowedError):
            manager.validate_operation(ClientType.DATABASE, "extreme_risk")

    def test_validate_operation_requires_confirmation(self):
        """Test validating an operation that requires confirmation."""
        manager = SafetyManager.get_instance()
        mock_config = MockSafetyConfig()

        # Register the config
        manager.register_config(ClientType.DATABASE, mock_config)

        # Set safety mode to UNSAFE
        manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)

        # Validate high risk operation without confirmation
        # Should raise ConfirmationRequiredError
        with pytest.raises(ConfirmationRequiredError):
            manager.validate_operation(ClientType.DATABASE, "high_risk", has_confirmation=False)

        # Extreme risk operations are not allowed even in UNSAFE mode
        with pytest.raises(OperationNotAllowedError):
            manager.validate_operation(ClientType.DATABASE, "extreme_risk", has_confirmation=False)

        # Even with confirmation, extreme risk operations are not allowed
        with pytest.raises(OperationNotAllowedError):
            manager.validate_operation(ClientType.DATABASE, "extreme_risk", has_confirmation=True)

    def test_store_confirmation(self):
        """Test storing a confirmation for an operation."""
        manager = SafetyManager.get_instance()

        # Store a confirmation
        confirmation_id = manager._store_confirmation(ClientType.DATABASE, "test_operation", OperationRiskLevel.EXTREME)

        # Verify that a confirmation ID is returned
        assert confirmation_id is not None
        assert confirmation_id.startswith("conf_")

        # Verify that the confirmation can be retrieved
        confirmation = manager._get_confirmation(confirmation_id)
        assert confirmation is not None
        assert confirmation["operation"] == "test_operation"
        assert confirmation["client_type"] == ClientType.DATABASE
        assert confirmation["risk_level"] == OperationRiskLevel.EXTREME
        assert "timestamp" in confirmation

    def test_get_confirmation_valid(self):
        """Test getting a valid confirmation."""
        manager = SafetyManager.get_instance()

        # Store a confirmation
        confirmation_id = manager._store_confirmation(ClientType.DATABASE, "test_operation", OperationRiskLevel.EXTREME)

        # Retrieve the confirmation
        confirmation = manager._get_confirmation(confirmation_id)

        # Verify it matches what was stored
        assert confirmation is not None
        assert confirmation["operation"] == "test_operation"
        assert confirmation["client_type"] == ClientType.DATABASE
        assert confirmation["risk_level"] == OperationRiskLevel.EXTREME

    def test_get_confirmation_invalid(self):
        """Test getting an invalid confirmation."""
        manager = SafetyManager.get_instance()

        # Try to retrieve a confirmation with an invalid ID
        confirmation = manager._get_confirmation("invalid_id")

        # Verify that None is returned
        assert confirmation is None

    def test_get_confirmation_expired(self):
        """Test getting an expired confirmation."""
        manager = SafetyManager.get_instance()

        # Store a confirmation with a past expiration time
        confirmation_id = manager._store_confirmation(ClientType.DATABASE, "test_operation", OperationRiskLevel.EXTREME)

        # Manually set the timestamp to be older than the expiry time
        manager._pending_confirmations[confirmation_id]["timestamp"] = time.time() - manager._confirmation_expiry - 10

        # Try to retrieve the confirmation
        confirmation = manager._get_confirmation(confirmation_id)

        # Verify that None is returned
        assert confirmation is None

    def test_cleanup_expired_confirmations(self):
        """Test cleaning up expired confirmations."""
        manager = SafetyManager.get_instance()

        # Store multiple confirmations with different expiration times
        valid_id = manager._store_confirmation(ClientType.DATABASE, "valid_operation", OperationRiskLevel.EXTREME)

        expired_id = manager._store_confirmation(ClientType.DATABASE, "expired_operation", OperationRiskLevel.EXTREME)

        # Manually set the timestamp of the expired confirmation to be older than the expiry time
        manager._pending_confirmations[expired_id]["timestamp"] = time.time() - manager._confirmation_expiry - 10

        # Call cleanup
        manager._cleanup_expired_confirmations()

        # Verify that expired confirmations are removed and valid ones remain
        assert valid_id in manager._pending_confirmations
        assert expired_id not in manager._pending_confirmations

    def test_get_stored_operation(self):
        """Test getting a stored operation."""
        manager = SafetyManager.get_instance()

        # Store a confirmation for an operation
        confirmation_id = manager._store_confirmation(ClientType.DATABASE, "test_operation", OperationRiskLevel.EXTREME)

        # Retrieve the operation
        operation = manager.get_stored_operation(confirmation_id)

        # Verify that the retrieved operation matches the original
        assert operation == "test_operation"

        # Test with an invalid ID
        assert manager.get_stored_operation("invalid_id") is None

    def test_integration_validate_and_confirm(self):
        """Test the full flow of validating an operation that requires confirmation and then confirming it."""
        manager = SafetyManager.get_instance()
        mock_config = MockSafetyConfig()

        # Register the config
        manager.register_config(ClientType.DATABASE, mock_config)

        # Set safety mode to UNSAFE
        manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)

        # Try to validate a high risk operation and catch the ConfirmationRequiredError
        confirmation_id = None
        try:
            manager.validate_operation(ClientType.DATABASE, "high_risk", has_confirmation=False)
        except ConfirmationRequiredError as e:
            # Extract the confirmation ID from the error message
            error_message = str(e)
            # Find the confirmation ID in the message
            import re

            match = re.search(r"ID: (conf_[a-f0-9]+)", error_message)
            if match:
                confirmation_id = match.group(1)

        # Verify that we got a confirmation ID
        assert confirmation_id is not None

        # Now validate the operation again with the confirmation ID
        # This should not raise an exception
        manager.validate_operation(ClientType.DATABASE, "high_risk", has_confirmation=True)

    def test_register_safety_configs(self):
        """Test that register_safety_configs registers both SQL and API configs."""
        manager = SafetyManager.get_instance()
        result = manager.register_safety_configs()

        assert result is True
        assert ClientType.DATABASE in manager._safety_configs
        assert ClientType.API in manager._safety_configs

    def test_validate_operation_no_config_raises(self):
        """Test that validate_operation raises OperationNotAllowedError when no config is registered."""
        manager = SafetyManager.get_instance()
        # No config registered for API — should raise immediately
        with pytest.raises(OperationNotAllowedError, match="No safety configuration registered"):
            manager.validate_operation(ClientType.API, "any_operation")

    def test_get_current_mode_returns_string(self):
        """Test that get_current_mode returns the mode as a string."""
        manager = SafetyManager.get_instance()

        manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)
        assert manager.get_current_mode(ClientType.DATABASE) == str(SafetyMode.SAFE)

        manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)
        assert manager.get_current_mode(ClientType.DATABASE) == str(SafetyMode.UNSAFE)

    def test_get_operations_by_risk_level_with_api_config(self):
        """Test get_operations_by_risk_level returns correct paths for API config."""
        from supabase_mcp.services.safety.models import OperationRiskLevel

        manager = SafetyManager.get_instance()
        manager.register_safety_configs()

        result = manager.get_operations_by_risk_level(OperationRiskLevel.EXTREME, ClientType.API)
        assert result is not None
        assert isinstance(result, dict)

    def test_get_operations_by_risk_level_no_config(self):
        """Test get_operations_by_risk_level returns empty dict when no config registered."""
        manager = SafetyManager.get_instance()
        # No config registered — DATABASE config missing PATH_SAFETY_CONFIG
        result = manager.get_operations_by_risk_level("extreme", ClientType.DATABASE)
        assert result == {}

    def test_reset_clears_singleton(self):
        """Test that reset() clears the singleton instance."""
        manager1 = SafetyManager.get_instance()
        SafetyManager.reset()
        manager2 = SafetyManager.get_instance()
        assert manager1 is not manager2

    def test_api_client_type_safety_modes(self):
        """Test safety mode management for API client type."""
        manager = SafetyManager.get_instance()

        assert manager.get_safety_mode(ClientType.API) == SafetyMode.SAFE

        manager.set_safety_mode(ClientType.API, SafetyMode.UNSAFE)
        assert manager.get_safety_mode(ClientType.API) == SafetyMode.UNSAFE

        manager.set_safety_mode(ClientType.API, SafetyMode.SAFE)
        assert manager.get_safety_mode(ClientType.API) == SafetyMode.SAFE

    def test_extreme_risk_always_blocked_regardless_of_mode(self):
        """Test that EXTREME risk operations are blocked in both SAFE and UNSAFE modes."""
        manager = SafetyManager.get_instance()
        mock_config = MockSafetyConfig()
        manager.register_config(ClientType.DATABASE, mock_config)

        for mode in (SafetyMode.SAFE, SafetyMode.UNSAFE):
            manager.set_safety_mode(ClientType.DATABASE, mode)
            with pytest.raises(OperationNotAllowedError):
                manager.validate_operation(ClientType.DATABASE, "extreme_risk", has_confirmation=True)
