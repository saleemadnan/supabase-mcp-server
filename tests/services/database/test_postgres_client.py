from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from supabase_mcp.exceptions import ConnectionError, QueryError
from supabase_mcp.services.database.postgres_client import PostgresClient, QueryResult, StatementResult
from supabase_mcp.services.database.sql.validator import (
    QueryValidationResults,
    SQLQueryCategory,
    SQLQueryCommand,
    SQLValidator,
    ValidatedStatement,
)
from supabase_mcp.services.safety.models import OperationRiskLevel


@pytest.mark.asyncio(loop_scope="class")
@pytest.mark.integration
class TestPostgresClient:
    """Integration tests for the Postgres client."""

    async def test_execute_simple_select(self, postgres_client_integration: PostgresClient):
        """Test executing a simple SELECT query."""
        # Create a simple validation result with a SELECT query
        query = "SELECT 1 as number;"
        statement = ValidatedStatement(
            query=query,
            command=SQLQueryCommand.SELECT,
            category=SQLQueryCategory.DQL,
            risk_level=OperationRiskLevel.LOW,
            needs_migration=False,
            object_type=None,
            schema_name=None,
        )
        validation_result = QueryValidationResults(
            statements=[statement],
            original_query=query,
            highest_risk_level=OperationRiskLevel.LOW,
        )

        # Execute the query
        result = await postgres_client_integration.execute_query(validation_result)

        # Verify the result
        assert isinstance(result, QueryResult)
        assert len(result.results) == 1
        assert isinstance(result.results[0], StatementResult)
        assert len(result.results[0].rows) == 1
        assert result.results[0].rows[0]["number"] == 1

    async def test_execute_multiple_statements(self, postgres_client_integration: PostgresClient):
        """Test executing multiple SQL statements in a single query."""
        # Create validation result with multiple statements
        query = "SELECT 1 as first; SELECT 2 as second;"
        statements = [
            ValidatedStatement(
                query="SELECT 1 as first;",
                command=SQLQueryCommand.SELECT,
                category=SQLQueryCategory.DQL,
                risk_level=OperationRiskLevel.LOW,
                needs_migration=False,
                object_type=None,
                schema_name=None,
            ),
            ValidatedStatement(
                query="SELECT 2 as second;",
                command=SQLQueryCommand.SELECT,
                category=SQLQueryCategory.DQL,
                risk_level=OperationRiskLevel.LOW,
                needs_migration=False,
                object_type=None,
                schema_name=None,
            ),
        ]
        validation_result = QueryValidationResults(
            statements=statements,
            original_query=query,
            highest_risk_level=OperationRiskLevel.LOW,
        )

        # Execute the query
        result = await postgres_client_integration.execute_query(validation_result)

        # Verify the result
        assert isinstance(result, QueryResult)
        assert len(result.results) == 2
        assert result.results[0].rows[0]["first"] == 1
        assert result.results[1].rows[0]["second"] == 2

    async def test_execute_query_with_parameters(self, postgres_client_integration: PostgresClient):
        """Test executing a query with parameters."""
        # This test would normally use parameterized queries, but since we're using the validation results
        # we'll just use a query that includes the parameter values directly
        query = "SELECT 'test' as name, 42 as value;"
        statement = ValidatedStatement(
            query=query,
            command=SQLQueryCommand.SELECT,
            category=SQLQueryCategory.DQL,
            risk_level=OperationRiskLevel.LOW,
            needs_migration=False,
            object_type=None,
            schema_name=None,
        )
        validation_result = QueryValidationResults(
            statements=[statement],
            original_query=query,
            highest_risk_level=OperationRiskLevel.LOW,
        )

        # Execute the query
        result = await postgres_client_integration.execute_query(validation_result)

        # Verify the result
        assert isinstance(result, QueryResult)
        assert len(result.results) == 1
        assert result.results[0].rows[0]["name"] == "test"
        assert result.results[0].rows[0]["value"] == 42

    async def test_permission_error(self, postgres_client_integration: PostgresClient):
        """Test handling a permission error."""
        # Create a mock error
        error = asyncpg.exceptions.InsufficientPrivilegeError("Permission denied")

        # Verify that the method raises PermissionError with the expected message
        try:
            await postgres_client_integration._handle_postgres_error(error)
            # If we get here, the test should fail
            assert False, "Expected PermissionError was not raised"
        except Exception as e:
            # Verify it's the right type of exception
            from supabase_mcp.exceptions import PermissionError as SupabasePermissionError

            assert isinstance(e, SupabasePermissionError)
            # Verify the error message
            assert "Access denied" in str(e)
            assert "Permission denied" in str(e)
            assert "live_dangerously" in str(e)

    async def test_query_error(self, postgres_client_integration: PostgresClient):
        """Test handling a query error."""
        # Create a validation result with a syntactically valid but semantically incorrect query
        query = "SELECT * FROM nonexistent_table;"
        statement = ValidatedStatement(
            query=query,
            command=SQLQueryCommand.SELECT,
            category=SQLQueryCategory.DQL,
            risk_level=OperationRiskLevel.LOW,
            needs_migration=False,
            object_type="TABLE",
            schema_name="public",
        )
        validation_result = QueryValidationResults(
            statements=[statement],
            original_query=query,
            highest_risk_level=OperationRiskLevel.LOW,
        )

        # Execute the query - should raise a QueryError
        with pytest.raises(QueryError) as excinfo:
            await postgres_client_integration.execute_query(validation_result)

        # Verify the error message contains the specific error
        assert "nonexistent_table" in str(excinfo.value)

    async def test_schema_error(self, postgres_client_integration: PostgresClient):
        """Test handling a schema error."""
        # Create a validation result with a query referencing a non-existent column
        query = "SELECT nonexistent_column FROM information_schema.tables;"
        statement = ValidatedStatement(
            query=query,
            command=SQLQueryCommand.SELECT,
            category=SQLQueryCategory.DQL,
            risk_level=OperationRiskLevel.LOW,
            needs_migration=False,
            object_type="TABLE",
            schema_name="information_schema",
        )
        validation_result = QueryValidationResults(
            statements=[statement],
            original_query=query,
            highest_risk_level=OperationRiskLevel.LOW,
        )

        # Execute the query - should raise a QueryError
        with pytest.raises(QueryError) as excinfo:
            await postgres_client_integration.execute_query(validation_result)

        # Verify the error message contains the specific error
        assert "nonexistent_column" in str(excinfo.value)

    async def test_write_operation(self, postgres_client_integration: PostgresClient):
        """Test a basic write operation (INSERT)."""
        # First drop the table if it exists
        drop_query = "DROP TABLE IF EXISTS test_write;"
        drop_statement = ValidatedStatement(
            query=drop_query,
            command=SQLQueryCommand.DROP,
            category=SQLQueryCategory.DDL,
            risk_level=OperationRiskLevel.HIGH,
            needs_migration=False,
            object_type="TABLE",
            schema_name="public",
        )
        drop_validation = QueryValidationResults(
            statements=[drop_statement],
            original_query=drop_query,
            highest_risk_level=OperationRiskLevel.HIGH,
        )

        # Execute the drop table query
        await postgres_client_integration.execute_query(drop_validation, readonly=False)

        # Create a temporary table
        create_query = "CREATE TEMPORARY TABLE test_write (id SERIAL PRIMARY KEY, name TEXT);"
        create_statement = ValidatedStatement(
            query=create_query,
            command=SQLQueryCommand.CREATE,
            category=SQLQueryCategory.DDL,
            risk_level=OperationRiskLevel.MEDIUM,
            needs_migration=False,
            object_type="TABLE",
            schema_name="public",
        )
        create_validation = QueryValidationResults(
            statements=[create_statement],
            original_query=create_query,
            highest_risk_level=OperationRiskLevel.MEDIUM,
        )

        # Execute the create table query
        await postgres_client_integration.execute_query(create_validation, readonly=False)

        # Now insert data
        insert_query = "INSERT INTO test_write (name) VALUES ('test_value') RETURNING id, name;"
        insert_statement = ValidatedStatement(
            query=insert_query,
            command=SQLQueryCommand.INSERT,
            category=SQLQueryCategory.DML,
            risk_level=OperationRiskLevel.MEDIUM,
            needs_migration=False,
            object_type="TABLE",
            schema_name="public",
        )
        insert_validation = QueryValidationResults(
            statements=[insert_statement],
            original_query=insert_query,
            highest_risk_level=OperationRiskLevel.MEDIUM,
        )

        # Execute the insert query
        result = await postgres_client_integration.execute_query(insert_validation, readonly=False)

        # Verify the result
        assert isinstance(result, QueryResult)
        assert len(result.results) == 1
        assert result.results[0].rows[0]["name"] == "test_value"
        assert "id" in result.results[0].rows[0]

    async def test_ddl_operation(self, postgres_client_integration: PostgresClient):
        """Test a basic DDL operation (CREATE and DROP TABLE)."""
        # First drop the table if it exists
        drop_query = "DROP TABLE IF EXISTS test_ddl;"
        drop_statement = ValidatedStatement(
            query=drop_query,
            command=SQLQueryCommand.DROP,
            category=SQLQueryCategory.DDL,
            risk_level=OperationRiskLevel.HIGH,
            needs_migration=False,
            object_type="TABLE",
            schema_name="public",
        )
        drop_validation = QueryValidationResults(
            statements=[drop_statement],
            original_query=drop_query,
            highest_risk_level=OperationRiskLevel.HIGH,
        )

        # Execute the drop table query
        await postgres_client_integration.execute_query(drop_validation, readonly=False)

        # Create a test table
        create_query = "CREATE TEMPORARY TABLE test_ddl (id SERIAL PRIMARY KEY, value TEXT);"
        create_statement = ValidatedStatement(
            query=create_query,
            command=SQLQueryCommand.CREATE,
            category=SQLQueryCategory.DDL,
            risk_level=OperationRiskLevel.MEDIUM,
            needs_migration=False,
            object_type="TABLE",
            schema_name="public",
        )
        create_validation = QueryValidationResults(
            statements=[create_statement],
            original_query=create_query,
            highest_risk_level=OperationRiskLevel.MEDIUM,
        )

        # Execute the create table query
        await postgres_client_integration.execute_query(create_validation, readonly=False)

        # Verify the table exists by inserting and querying data
        insert_query = "INSERT INTO test_ddl (value) VALUES ('test_ddl_value'); SELECT * FROM test_ddl;"
        insert_statements = [
            ValidatedStatement(
                query="INSERT INTO test_ddl (value) VALUES ('test_ddl_value');",
                command=SQLQueryCommand.INSERT,
                category=SQLQueryCategory.DML,
                risk_level=OperationRiskLevel.MEDIUM,
                needs_migration=False,
                object_type="TABLE",
                schema_name="public",
            ),
            ValidatedStatement(
                query="SELECT * FROM test_ddl;",
                command=SQLQueryCommand.SELECT,
                category=SQLQueryCategory.DQL,
                risk_level=OperationRiskLevel.LOW,
                needs_migration=False,
                object_type="TABLE",
                schema_name="public",
            ),
        ]
        insert_validation = QueryValidationResults(
            statements=insert_statements,
            original_query=insert_query,
            highest_risk_level=OperationRiskLevel.MEDIUM,
        )

        # Execute the insert and select queries
        result = await postgres_client_integration.execute_query(insert_validation, readonly=False)

        # Verify the result
        assert isinstance(result, QueryResult)
        assert len(result.results) == 2
        assert result.results[1].rows[0]["value"] == "test_ddl_value"

    async def test_execute_metadata_query(self, postgres_client_integration: PostgresClient):
        """Test executing a metadata query."""
        # Create a simple validation result with a SELECT query
        query = "SELECT schema_name FROM information_schema.schemata LIMIT 5;"
        statement = ValidatedStatement(
            query=query,
            command=SQLQueryCommand.SELECT,
            category=SQLQueryCategory.DQL,
            risk_level=OperationRiskLevel.LOW,
            needs_migration=False,
            object_type="schemata",
            schema_name="information_schema",
        )
        validation_result = QueryValidationResults(
            statements=[statement],
            original_query=query,
            highest_risk_level=OperationRiskLevel.LOW,
        )

        # Execute the query
        result = await postgres_client_integration.execute_query(validation_result)

        # Verify the result
        assert isinstance(result, QueryResult)
        assert len(result.results) == 1
        assert len(result.results[0].rows) == 5
        assert "schema_name" in result.results[0].rows[0]

    async def test_connection_retry_mechanism(self, monkeypatch, postgres_client_integration: PostgresClient):
        """Test that the tenacity retry mechanism works correctly for database connections."""

        # Create a simple mock that always raises a connection error
        async def mock_create_pool(*args, **kwargs):
            raise asyncpg.exceptions.ConnectionDoesNotExistError("Simulated connection failure")

        # Replace asyncpg's create_pool with our mock
        monkeypatch.setattr(asyncpg, "create_pool", mock_create_pool)

        # Close the existing pool to force a new connection
        await postgres_client_integration.close()

        # This should trigger the retry mechanism and eventually fail
        with pytest.raises(ConnectionError) as exc_info:
            await postgres_client_integration.ensure_pool()

        # Verify the error message indicates a connection failure after retries
        assert "Could not connect to database" in str(exc_info.value)


@pytest.mark.unit
class TestExecuteQueryUnit:
    """Unit tests for execute_query with a fake connection (no database needed)."""

    @staticmethod
    def _client_with_fake_connection(fetch_results: list[list[dict[str, int]]]) -> tuple[PostgresClient, AsyncMock]:
        @asynccontextmanager
        async def transaction(readonly: bool = False) -> AsyncIterator[None]:
            yield

        conn = MagicMock()
        conn.fetch = AsyncMock(side_effect=fetch_results)
        conn.transaction = transaction

        async def with_connection(operation):
            return await operation(conn)

        # Bypass __init__: no settings or pool are needed to exercise the statement loop
        client = PostgresClient.__new__(PostgresClient)
        client.with_connection = with_connection
        return client, conn.fetch

    async def test_unterminated_final_statement_is_executed(self, mock_validator: SQLValidator):
        client, fetch = self._client_with_fake_connection([[{"ok": 1}]])

        result = await client.execute_query(mock_validator.validate_query("SELECT 1 AS ok"))

        fetch.assert_awaited_once_with("SELECT 1 AS ok")
        assert result == QueryResult(results=[StatementResult(rows=[{"ok": 1}])])

    async def test_every_statement_of_an_unterminated_batch_is_executed(self, mock_validator: SQLValidator):
        client, fetch = self._client_with_fake_connection([[{"a": 1}], [{"b": 2}]])

        result = await client.execute_query(mock_validator.validate_query("SELECT 1 AS a; SELECT 2 AS b"))

        assert [call.args[0] for call in fetch.await_args_list] == ["SELECT 1 AS a", "SELECT 2 AS b"]
        assert len(result.results) == 2
