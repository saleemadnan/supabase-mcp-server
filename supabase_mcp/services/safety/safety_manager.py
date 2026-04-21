import time
import uuid
from typing import Any, Optional

from supabase_mcp.exceptions import ConfirmationRequiredError, OperationNotAllowedError
from supabase_mcp.logger import logger
from supabase_mcp.services.safety.models import ClientType, SafetyMode
from supabase_mcp.services.safety.safety_configs import APISafetyConfig, MetaSafetyConfig, SafetyConfigBase, SQLSafetyConfig


class SafetyManager:
    """A singleton service that maintains current safety state.

     Provides methods to:
      - Get/set safety modes for different clients
      - Register safety configurations
      - Check if operations are allowed
    Serves as the central point for safety decisions"""

    _instance: Optional["SafetyManager"] = None

    def __init__(self) -> None:
        """Initialize the safety manager with default safety modes."""
        self._safety_modes: dict[ClientType, SafetyMode] = {
            ClientType.DATABASE: SafetyMode.SAFE,
            ClientType.API: SafetyMode.SAFE,
            ClientType.META: SafetyMode.SAFE,
        }
        self._safety_configs: dict[ClientType, SafetyConfigBase[Any]] = {}
        self._pending_confirmations: dict[str, dict[str, Any]] = {}
        self._confirmation_expiry = 300  # 5 minutes in seconds

    @classmethod
    def get_instance(cls) -> "SafetyManager":
        """Get the singleton instance of the safety manager."""
        if cls._instance is None:
            cls._instance = SafetyManager()
        return cls._instance

    def register_safety_configs(self) -> bool:
        """Register all safety configurations with the SafetyManager.

        Returns:
            bool: True if all configurations were registered successfully
        """
        # Register SQL safety config
        sql_config = SQLSafetyConfig()
        self.register_config(ClientType.DATABASE, sql_config)

        # Register API safety config
        api_config = APISafetyConfig()
        self.register_config(ClientType.API, api_config)

        # Register Meta safety config
        meta_config = MetaSafetyConfig()
        self.register_config(ClientType.META, meta_config)

        logger.info("✓ Safety configurations registered successfully")
        return True

    def register_config(self, client_type: ClientType, config: SafetyConfigBase[Any]) -> None:
        """Register a safety configuration for a client type.

        Args:
            client_type: The client type to register the configuration for
            config: The safety configuration for the client
        """
        self._safety_configs[client_type] = config

    def get_safety_mode(self, client_type: ClientType) -> SafetyMode:
        """Get the current safety mode for a client type.

        Args:
            client_type: The client type to get the safety mode for

        Returns:
            The current safety mode for the client type
        """
        if client_type not in self._safety_modes:
            logger.warning(f"No safety mode registered for {client_type}, defaulting to SAFE")
            return SafetyMode.SAFE
        return self._safety_modes[client_type]

    def set_safety_mode(self, client_type: ClientType, mode: SafetyMode) -> None:
        """Set the safety mode for a client type.

        Args:
            client_type: The client type to set the safety mode for
            mode: The safety mode to set
        """
        self._safety_modes[client_type] = mode
        logger.debug(f"Set safety mode for {client_type} to {mode}")

    def validate_operation(
        self,
        client_type: ClientType,
        operation: Any,
        has_confirmation: bool = False,
    ) -> None:
        """Validate if an operation is allowed for a client type.

        This method will raise appropriate exceptions if the operation is not allowed
        or requires confirmation.

        Args:
            client_type: The client type to check the operation for
            operation: The operation to check
            has_confirmation: Whether the operation has been confirmed by the user

        Raises:
            OperationNotAllowedError: If the operation is not allowed in the current safety mode
            ConfirmationRequiredError: If the operation requires confirmation and has_confirmation is False
        """
        # Get the current safety mode and config
        mode = self.get_safety_mode(client_type)
        config = self._safety_configs.get(client_type)

        if not config:
            message = f"No safety configuration registered for {client_type}"
            logger.warning(message)
            raise OperationNotAllowedError(message)

        # Get the risk level for the operation
        risk_level = config.get_risk_level(operation)
        logger.debug(f"Operation risk level: {risk_level}")

        # Check if the operation is allowed in the current mode
        is_allowed = config.is_operation_allowed(risk_level, mode)
        if not is_allowed:
            message = f"Operation with risk level {risk_level} is not allowed in {mode} mode"
            logger.debug(f"Operation with risk level {risk_level} not allowed in {mode} mode")
            raise OperationNotAllowedError(message)

        # Check if the operation needs confirmation
        needs_confirmation = config.needs_confirmation(risk_level)
        if needs_confirmation and not has_confirmation:
            # Store the operation for later confirmation
            confirmation_id = self._store_confirmation(client_type, operation, risk_level)

            message = (
                f"Operation with risk level {risk_level} requires explicit user confirmation.\n\n"
                f"WHAT HAPPENED: This high-risk operation was rejected for safety reasons.\n"
                f"WHAT TO DO: 1. Review the operation with the user and explain the risks\n"
                f"            2. If the user approves, use the confirmation tool with this ID: {confirmation_id}\n\n"
                f'CONFIRMATION COMMAND: confirm_destructive_postgresql(confirmation_id="{confirmation_id}", user_confirmation=True)'
            )
            logger.debug(
                f"Operation with risk level {risk_level} requires confirmation, stored with ID {confirmation_id}"
            )
            raise ConfirmationRequiredError(message)

        logger.debug(f"Operation with risk level {risk_level} allowed in {mode} mode")

    def _store_confirmation(self, client_type: ClientType, operation: Any, risk_level: int) -> str:
        """Store an operation that needs confirmation.

        Args:
            client_type: The client type the operation is for
            operation: The operation to store
            risk_level: The risk level of the operation

        Returns:
            A unique confirmation ID
        """
        # Generate a unique ID
        confirmation_id = f"conf_{uuid.uuid4().hex[:8]}"

        # Store the operation with metadata
        self._pending_confirmations[confirmation_id] = {
            "operation": operation,
            "client_type": client_type,
            "risk_level": risk_level,
            "timestamp": time.time(),
        }

        # Clean up expired confirmations
        self._cleanup_expired_confirmations()

        return confirmation_id

    def _get_confirmation(self, confirmation_id: str) -> dict[str, Any] | None:
        """Retrieve a stored confirmation by ID.

        Args:
            confirmation_id: The ID of the confirmation to retrieve

        Returns:
            The stored confirmation data or None if not found or expired
        """
        # Clean up expired confirmations first
        self._cleanup_expired_confirmations()

        # Return the stored confirmation if it exists
        return self._pending_confirmations.get(confirmation_id)

    def _cleanup_expired_confirmations(self) -> None:
        """Remove expired confirmations from storage."""
        current_time = time.time()
        expired_ids = [
            conf_id
            for conf_id, data in self._pending_confirmations.items()
            if current_time - data["timestamp"] > self._confirmation_expiry
        ]

        for conf_id in expired_ids:
            logger.debug(f"Removing expired confirmation with ID {conf_id}")
            del self._pending_confirmations[conf_id]

    def get_stored_operation(self, confirmation_id: str) -> Any | None:
        """Get a stored operation by its confirmation ID.

        Args:
            confirmation_id: The confirmation ID to get the operation for

        Returns:
            The stored operation, or None if not found
        """
        confirmation = self._get_confirmation(confirmation_id)
        if confirmation is None:
            return None
        return confirmation.get("operation")

    def get_operations_by_risk_level(
        self, risk_level: str, client_type: ClientType = ClientType.DATABASE
    ) -> dict[str, list[str]]:
        """Get operations for a specific risk level.

        Args:
            risk_level: The risk level to get operations for
            client_type: The client type to get operations for

        Returns:
            A dictionary mapping HTTP methods to lists of paths
        """
        # Get the config for the specified client type
        config = self._safety_configs.get(client_type)
        if not config or not hasattr(config, "PATH_SAFETY_CONFIG"):
            return {}

        # Get the operations for this risk level
        risk_config = getattr(config, "PATH_SAFETY_CONFIG", {})
        if risk_level in risk_config:
            return risk_config[risk_level]

    def get_current_mode(self, client_type: ClientType) -> str:
        """Get the current safety mode as a string.

        Args:
            client_type: The client type to get the mode for

        Returns:
            The current safety mode as a string
        """
        mode = self.get_safety_mode(client_type)
        return str(mode)

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance cleanly.

        This closes any open connections and resets the singleton instance.
        """
        if cls._instance is not None:
            cls._instance = None
            logger.info("SafetyManager instance reset complete")
