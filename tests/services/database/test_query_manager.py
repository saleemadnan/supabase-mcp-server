from unittest.mock import AsyncMock, MagicMock

import pytest

from supabase_mcp.exceptions import SafetyError
from supabase_mcp.services.database.query_manager import QueryManager
from supabase_mcp.services.database.sql.loader import SQLLoader
from supabase_mcp.services.database.sql.validator import (
    QueryValidationResults,
    SQLQueryCategory,
    SQLQueryCommand,
    SQLValidator,
    ValidatedStatement,
)
from supabase_mcp.services.safety.models import ClientType, OperationRiskLevel, SafetyMode


@pytest.mark.asyncio(loop_scope="module")
class TestQueryManager:
    """Tests for the Query Manager."""

    @pytest.mark.unit
    async def test_query_execution(self, mock_query_manager: QueryManager):
        """Test query execution through the Query Manager."""

        query_manager = mock_query_manager

        # Ensure validator and safety_manager are proper mocks
        query_manager.validator = MagicMock()
        query_manager.safety_manager = MagicMock()

        # Create a mock validation result for a SELECT query
        validated_statement = ValidatedStatement(
            category=SQLQueryCategory.DQL,
            command=SQLQueryCommand.SELECT,
            risk_level=OperationRiskLevel.LOW,
            query="SELECT * FROM users",
            needs_migration=False,
            object_type="TABLE",
            schema_name="public",
        )

        validation_result = QueryValidationResults(
            statements=[validated_statement],
            highest_risk_level=OperationRiskLevel.LOW,
            has_transaction_control=False,
            original_query="SELECT * FROM users",
        )

        # Make the validator return our mock validation result
        query_manager.validator.validate_query.return_value = validation_result

        # Make the db_client return a mock query result
        mock_query_result = MagicMock()
        query_manager.db_client.execute_query = AsyncMock(return_value=mock_query_result)

        # Execute a query
        query = "SELECT * FROM users"
        result = await query_manager.handle_query(query)

        # Verify the validator was called with the query
        query_manager.validator.validate_query.assert_called_once_with(query)

        # Verify the db_client was called with the validation result
        query_manager.db_client.execute_query.assert_called_once_with(validation_result, False)

        # Verify the result is what we expect
        assert result == mock_query_result

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_safety_validation_blocks_dangerous_query(self, mock_query_manager: QueryManager):
        """Test that the safety validation blocks dangerous queries."""

        # Create a query manager with the mock dependencies
        query_manager = mock_query_manager

        # Ensure validator and safety_manager are proper mocks
        query_manager.validator = MagicMock()
        query_manager.safety_manager = MagicMock()

        # Create a mock validation result for a DROP TABLE query
        validated_statement = ValidatedStatement(
            category=SQLQueryCategory.DDL,
            command=SQLQueryCommand.DROP,
            risk_level=OperationRiskLevel.EXTREME,
            query="DROP TABLE users",
            needs_migration=False,
            object_type="TABLE",
            schema_name="public",
        )

        validation_result = QueryValidationResults(
            statements=[validated_statement],
            highest_risk_level=OperationRiskLevel.EXTREME,
            has_transaction_control=False,
            original_query="DROP TABLE users",
        )

        # Make the validator return our mock validation result
        query_manager.validator.validate_query.return_value = validation_result

        # Make the safety manager raise a SafetyError
        error_message = "Operation not allowed in SAFE mode"
        query_manager.safety_manager.validate_operation.side_effect = SafetyError(error_message)

        # Execute a query - should raise a SafetyError
        query = "DROP TABLE users"
        with pytest.raises(SafetyError) as excinfo:
            await query_manager.handle_query(query)

        # Verify the error message
        assert error_message in str(excinfo.value)

        # Verify the validator was called with the query
        query_manager.validator.validate_query.assert_called_once_with(query)

        # Verify the safety manager was called with the validation result
        query_manager.safety_manager.validate_operation.assert_called_once_with(
            ClientType.DATABASE, validation_result, False
        )

        # Verify the db_client was not called
        query_manager.db_client.execute_query.assert_not_called()

    @pytest.mark.unit
    async def test_get_migrations_query(self, query_manager_integration: QueryManager):
        """Test that get_migrations_query returns a valid query string."""
        # Test with default parameters
        query = query_manager_integration.get_migrations_query()
        assert isinstance(query, str)
        assert "supabase_migrations.schema_migrations" in query
        assert "LIMIT 50" in query

        # Test with custom parameters
        custom_query = query_manager_integration.get_migrations_query(
            limit=10, offset=5, name_pattern="test", include_full_queries=True
        )
        assert isinstance(custom_query, str)
        assert "supabase_migrations.schema_migrations" in custom_query
        assert "LIMIT 10" in custom_query
        assert "OFFSET 5" in custom_query
        assert "name ILIKE" in custom_query
        assert "statements" in custom_query  # Should include statements column when include_full_queries=True

    @pytest.mark.unit
    async def test_init_migration_schema(self):
        """Test that init_migration_schema initializes the migration schema correctly."""
        # Create minimal mocks
        postgres_client = MagicMock()
        postgres_client.execute_query = AsyncMock()

        safety_manager = MagicMock()

        # Create a real SQLLoader and SQLValidator
        sql_loader = SQLLoader()
        sql_validator = SQLValidator()

        # Create the QueryManager with minimal mocking
        query_manager = QueryManager(
            postgres_client=postgres_client,
            safety_manager=safety_manager,
            sql_validator=sql_validator,
            sql_loader=sql_loader,
        )

        # Call the method
        await query_manager.init_migration_schema()

        # Verify that the SQL loader was used to get the init migrations query
        # and that the query was executed
        assert postgres_client.execute_query.called

        # Get the arguments that execute_query was called with
        call_args = postgres_client.execute_query.call_args
        assert call_args is not None

        # The first argument should be a QueryValidationResults object
        args, _ = call_args  # Use _ to ignore unused kwargs
        assert len(args) > 0
        validation_result = args[0]
        assert isinstance(validation_result, QueryValidationResults)

        # Check that the validation result contains the expected SQL
        init_query = sql_loader.get_init_migrations_query()
        assert any(stmt.query and stmt.query in init_query for stmt in validation_result.statements)

    @pytest.mark.unit
    async def test_handle_migration(self):
        """Test that handle_migration correctly handles migrations when needed."""
        # Create minimal mocks
        postgres_client = MagicMock()
        postgres_client.execute_query = AsyncMock()

        safety_manager = MagicMock()

        # Create a real SQLLoader
        sql_loader = SQLLoader()

        # Create a mock MigrationManager
        migration_manager = MagicMock()
        migration_query = "INSERT INTO _migrations.migrations (name) VALUES ('test_migration')"
        migration_name = "test_migration"
        migration_manager.prepare_migration_query.return_value = (migration_query, migration_name)

        # Create a real SQLValidator
        sql_validator = SQLValidator()

        # Create the QueryManager with minimal mocking
        query_manager = QueryManager(
            postgres_client=postgres_client,
            safety_manager=safety_manager,
            sql_validator=sql_validator,
            sql_loader=sql_loader,
            migration_manager=migration_manager,
        )

        # Create a validation result that needs migration
        validated_statement = ValidatedStatement(
            category=SQLQueryCategory.DDL,
            command=SQLQueryCommand.CREATE,
            risk_level=OperationRiskLevel.MEDIUM,
            query="CREATE TABLE test (id INT)",
            needs_migration=True,
            object_type="TABLE",
            schema_name="public",
        )

        validation_result = QueryValidationResults(
            statements=[validated_statement],
            highest_risk_level=OperationRiskLevel.MEDIUM,
            has_transaction_control=False,
            original_query="CREATE TABLE test (id INT)",
        )

        # Call the method
        await query_manager.handle_migration(validation_result, "CREATE TABLE test (id INT)", "test_migration")

        # Verify that the migration manager was called to prepare the migration query
        migration_manager.prepare_migration_query.assert_called_once_with(
            validation_result, "CREATE TABLE test (id INT)", "test_migration"
        )

        # Verify that execute_query was called at least twice
        # Once for init_migration_schema and once for the migration query
        assert postgres_client.execute_query.call_count >= 2


@pytest.mark.unit
class TestUnterminatedStatements:
    """A final statement without a trailing semicolon must be executed and recorded with its own text."""

    @staticmethod
    def _build_query_manager() -> tuple[QueryManager, MagicMock]:
        postgres_client = MagicMock()
        postgres_client.execute_query = AsyncMock()
        safety_manager = MagicMock()
        safety_manager.get_safety_mode.return_value = SafetyMode.UNSAFE
        query_manager = QueryManager(postgres_client=postgres_client, safety_manager=safety_manager)
        return query_manager, postgres_client

    async def test_unterminated_select_is_sent_for_execution(self):
        query_manager, postgres_client = self._build_query_manager()

        await query_manager.handle_query("SELECT 1 AS ok")

        validated = postgres_client.execute_query.await_args.args[0]
        assert [statement.query for statement in validated.statements] == ["SELECT 1 AS ok"]

    async def test_unterminated_ddl_is_executed_and_its_migration_named_from_its_text(self):
        query_manager, postgres_client = self._build_query_manager()

        await query_manager.handle_query("CREATE TABLE t (id int)")

        executed = [call.args[0] for call in postgres_client.execute_query.await_args_list]
        # init migrations schema, record the migration, then run the DDL itself
        assert len(executed) == 3
        migration_record, ddl = executed[1], executed[2]

        assert [statement.query for statement in ddl.statements] == ["CREATE TABLE t (id int)"]
        assert ddl.statements[0].needs_migration is True

        record_sql = migration_record.statements[0].query
        assert "INSERT INTO supabase_migrations.schema_migrations" in record_sql
        assert "ARRAY['CREATE TABLE t (id int)']" in record_sql
        # With the empty statement text the generated name used to be "create_t_public_unknown"
        assert "'create_t_public_t'" in record_sql
