from unittest.mock import patch

import pytest

from supabase_mcp.services.database.sql.loader import SQLLoader
from supabase_mcp.services.logs.log_manager import LogManager


class TestLogManager:
    """Tests for the LogManager class."""

    def test_init(self):
        """Test initialization of LogManager."""
        log_manager = LogManager()
        assert isinstance(log_manager.sql_loader, SQLLoader)
        assert log_manager.COLLECTION_TO_TABLE["postgres"] == "postgres_logs"
        assert log_manager.COLLECTION_TO_TABLE["api_gateway"] == "edge_logs"
        assert log_manager.COLLECTION_TO_TABLE["edge_functions"] == "function_edge_logs"

    @pytest.mark.parametrize(
        "collection,hours_ago,filters,search,expected_clause",
        [
            # Test with hours_ago only
            (
                "postgres",
                24,
                None,
                None,
                "WHERE postgres_logs.timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)",
            ),
            # Test with search only
            (
                "auth",
                None,
                None,
                "error",
                "WHERE event_message LIKE '%error%'",
            ),
            # Test with filters only
            (
                "api_gateway",
                None,
                [{"field": "status_code", "operator": "=", "value": 500}],
                None,
                "WHERE status_code = 500",
            ),
            # Test with string value in filters
            (
                "api_gateway",
                None,
                [{"field": "method", "operator": "=", "value": "GET"}],
                None,
                "WHERE method = 'GET'",
            ),
            # Test with multiple filters
            (
                "postgres",
                None,
                [
                    {"field": "parsed.error_severity", "operator": "=", "value": "ERROR"},
                    {"field": "parsed.application_name", "operator": "LIKE", "value": "app%"},
                ],
                None,
                "WHERE parsed.error_severity = 'ERROR' AND parsed.application_name LIKE 'app%'",
            ),
            # Test with hours_ago and search
            (
                "storage",
                12,
                None,
                "upload",
                "WHERE storage_logs.timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 12 HOUR) "
                "AND event_message LIKE '%upload%'",
            ),
            # Test with all parameters
            (
                "edge_functions",
                6,
                [{"field": "response.status_code", "operator": ">", "value": 400}],
                "timeout",
                "WHERE function_edge_logs.timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 6 "
                "HOUR) AND event_message LIKE '%timeout%' AND response.status_code > 400",
            ),
            # Test with cron logs (special case)
            (
                "cron",
                24,
                None,
                None,
                "AND postgres_logs.timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)",
            ),
            # Test with cron logs and other parameters
            (
                "cron",
                12,
                [{"field": "parsed.error_severity", "operator": "=", "value": "ERROR"}],
                "failed",
                "AND postgres_logs.timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 12 HOUR) "
                "AND event_message LIKE '%failed%' AND parsed.error_severity = 'ERROR'",
            ),
        ],
    )
    def test_build_where_clause(self, collection, hours_ago, filters, search, expected_clause):
        """Test building WHERE clauses for different scenarios."""
        log_manager = LogManager()
        where_clause = log_manager._build_where_clause(
            collection=collection, hours_ago=hours_ago, filters=filters, search=search
        )
        assert where_clause == expected_clause

    def test_build_where_clause_escapes_single_quotes(self):
        """Test that single quotes in search strings are properly escaped."""
        log_manager = LogManager()
        where_clause = log_manager._build_where_clause(collection="postgres", search="O'Reilly")
        assert where_clause == "WHERE event_message LIKE '%O''Reilly%'"

        # Test with filters containing single quotes
        where_clause = log_manager._build_where_clause(
            collection="postgres",
            filters=[{"field": "parsed.query", "operator": "LIKE", "value": "SELECT * FROM O'Reilly"}],
        )
        assert where_clause == "WHERE parsed.query LIKE 'SELECT * FROM O''Reilly'"

    @patch.object(SQLLoader, "get_logs_query")
    def test_build_logs_query_with_custom_query(self, mock_get_logs_query):
        """Test building a logs query with a custom query."""
        log_manager = LogManager()
        custom_query = "SELECT * FROM postgres_logs LIMIT 10"

        query = log_manager.build_logs_query(collection="postgres", custom_query=custom_query)

        assert query == custom_query
        # Ensure get_logs_query is not called when custom_query is provided
        mock_get_logs_query.assert_not_called()

    @patch.object(LogManager, "_build_where_clause")
    @patch.object(SQLLoader, "get_logs_query")
    def test_build_logs_query_standard(self, mock_get_logs_query, mock_build_where_clause):
        """Test building a standard logs query."""
        log_manager = LogManager()
        mock_build_where_clause.return_value = "WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)"
        mock_get_logs_query.return_value = (
            "SELECT * FROM postgres_logs WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), "
            "INTERVAL 24 HOUR) LIMIT 20"
        )

        query = log_manager.build_logs_query(
            collection="postgres",
            limit=20,
            hours_ago=24,
            filters=[{"field": "parsed.error_severity", "operator": "=", "value": "ERROR"}],
            search="connection",
        )

        mock_build_where_clause.assert_called_once_with(
            collection="postgres",
            hours_ago=24,
            filters=[{"field": "parsed.error_severity", "operator": "=", "value": "ERROR"}],
            search="connection",
        )

        mock_get_logs_query.assert_called_once_with(
            collection="postgres",
            where_clause="WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)",
            limit=20,
        )

        assert (
            query == "SELECT * FROM postgres_logs WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), "
            "INTERVAL 24 HOUR) LIMIT 20"
        )

    @patch.object(SQLLoader, "get_logs_query")
    def test_build_logs_query_integration(self, mock_get_logs_query, sql_loader):
        """Test building a logs query with integration between components."""
        # Setup
        log_manager = LogManager()
        log_manager.sql_loader = sql_loader

        # Mock the SQL loader to return a predictable result
        mock_get_logs_query.return_value = (
            "SELECT id, postgres_logs.timestamp, event_message FROM postgres_logs "
            "WHERE postgres_logs.timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR) "
            "ORDER BY timestamp DESC LIMIT 10"
        )

        # Execute
        query = log_manager.build_logs_query(
            collection="postgres",
            limit=10,
            hours_ago=24,
        )

        # Verify
        assert "SELECT id, postgres_logs.timestamp, event_message FROM postgres_logs" in query
        assert "LIMIT 10" in query
        mock_get_logs_query.assert_called_once()

    def test_unknown_collection(self):
        """Test handling of unknown collections."""
        log_manager = LogManager()

        # Test with a collection that doesn't exist in the mapping
        where_clause = log_manager._build_where_clause(
            collection="unknown_collection",
            hours_ago=24,
        )

        # Should use the collection name as the table name
        assert (
            where_clause == "WHERE unknown_collection.timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)"
        )
