"""
Unit tests for the SQLSafetyConfig class.

This file contains unit test cases for the SQLSafetyConfig class, which is responsible for
determining the risk level of SQL operations and whether they are allowed or require confirmation.
"""

from unittest.mock import MagicMock

import pytest

from supabase_mcp.services.safety.models import OperationRiskLevel, SafetyMode
from supabase_mcp.services.safety.safety_configs import SQLSafetyConfig


@pytest.mark.unit
class TestSQLSafetyConfig:
    """Unit tests for the SQLSafetyConfig class."""

    def test_get_risk_level(self):
        """Test that get_risk_level returns the highest_risk_level from the operation."""
        config = SQLSafetyConfig()

        # Create mock QueryValidationResults objects with different risk levels
        low_risk_op = MagicMock()
        low_risk_op.highest_risk_level = OperationRiskLevel.LOW

        medium_risk_op = MagicMock()
        medium_risk_op.highest_risk_level = OperationRiskLevel.MEDIUM

        high_risk_op = MagicMock()
        high_risk_op.highest_risk_level = OperationRiskLevel.HIGH

        extreme_risk_op = MagicMock()
        extreme_risk_op.highest_risk_level = OperationRiskLevel.EXTREME

        # Test that the risk level is correctly returned
        assert config.get_risk_level(low_risk_op) == OperationRiskLevel.LOW
        assert config.get_risk_level(medium_risk_op) == OperationRiskLevel.MEDIUM
        assert config.get_risk_level(high_risk_op) == OperationRiskLevel.HIGH
        assert config.get_risk_level(extreme_risk_op) == OperationRiskLevel.EXTREME

    def test_is_operation_allowed(self):
        """Test if operations are allowed based on risk level and safety mode.

        This tests the behavior inherited from SafetyConfigBase.
        """
        config = SQLSafetyConfig()

        # Low risk operations should be allowed in both safe and unsafe modes
        assert config.is_operation_allowed(OperationRiskLevel.LOW, SafetyMode.SAFE) is True
        assert config.is_operation_allowed(OperationRiskLevel.LOW, SafetyMode.UNSAFE) is True

        # Medium/high risk operations should only be allowed in unsafe mode
        assert config.is_operation_allowed(OperationRiskLevel.MEDIUM, SafetyMode.SAFE) is False
        assert config.is_operation_allowed(OperationRiskLevel.MEDIUM, SafetyMode.UNSAFE) is True
        assert config.is_operation_allowed(OperationRiskLevel.HIGH, SafetyMode.SAFE) is False
        assert config.is_operation_allowed(OperationRiskLevel.HIGH, SafetyMode.UNSAFE) is True

        # Extreme risk operations are never allowed
        assert config.is_operation_allowed(OperationRiskLevel.EXTREME, SafetyMode.SAFE) is False
        assert config.is_operation_allowed(OperationRiskLevel.EXTREME, SafetyMode.UNSAFE) is False

    def test_needs_confirmation(self):
        """Test if operations need confirmation based on risk level.

        This tests the behavior inherited from SafetyConfigBase.
        """
        config = SQLSafetyConfig()

        # Low and medium risk operations should not need confirmation
        assert config.needs_confirmation(OperationRiskLevel.LOW) is False
        assert config.needs_confirmation(OperationRiskLevel.MEDIUM) is False

        # High risk operations should need confirmation
        assert config.needs_confirmation(OperationRiskLevel.HIGH) is True

        # Extreme risk operations should need confirmation
        assert config.needs_confirmation(OperationRiskLevel.EXTREME) is True

    def test_classify_statement_known_type(self):
        """Test classify_statement returns correct config for known statement types."""
        config = SQLSafetyConfig()

        result = config.classify_statement("SelectStmt", None)
        assert result["risk_level"] == OperationRiskLevel.LOW

        result = config.classify_statement("InsertStmt", None)
        assert result["risk_level"] == OperationRiskLevel.MEDIUM

        result = config.classify_statement("DropStmt", None)
        assert result["risk_level"] == OperationRiskLevel.HIGH

    def test_classify_statement_unknown_type_defaults_medium(self):
        """Test classify_statement defaults to MEDIUM risk for unknown statement types."""
        config = SQLSafetyConfig()
        result = config.classify_statement("UnknownStmt", None)
        assert result["risk_level"] == OperationRiskLevel.MEDIUM

    def test_classify_statement_copy_to_is_low_risk(self):
        """Test that COPY TO (export) is classified as LOW risk."""
        config = SQLSafetyConfig()
        stmt_node = MagicMock()
        stmt_node.is_from = False  # COPY TO

        result = config.classify_statement("CopyStmt", stmt_node)
        assert result["risk_level"] == OperationRiskLevel.LOW

    def test_classify_statement_copy_from_is_medium_risk(self):
        """Test that COPY FROM (import) is classified as MEDIUM risk."""
        config = SQLSafetyConfig()
        stmt_node = MagicMock()
        stmt_node.is_from = True  # COPY FROM

        result = config.classify_statement("CopyStmt", stmt_node)
        assert result["risk_level"] == OperationRiskLevel.MEDIUM
