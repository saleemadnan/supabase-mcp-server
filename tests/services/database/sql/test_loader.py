import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from supabase_mcp.services.database.sql.loader import SQLLoader


@pytest.mark.unit
class TestSQLLoader:
    """Unit tests for the SQLLoader class."""

    def test_load_sql_with_extension(self):
        """Test loading SQL with file extension provided."""
        mock_sql = "SELECT * FROM test;"

        with patch("builtins.open", mock_open(read_data=mock_sql)):
            with patch.object(Path, "exists", return_value=True):
                result = SQLLoader.load_sql("test.sql")

        assert result == mock_sql

    def test_load_sql_without_extension(self):
        """Test loading SQL without file extension provided."""
        mock_sql = "SELECT * FROM test;"

        with patch("builtins.open", mock_open(read_data=mock_sql)):
            with patch.object(Path, "exists", return_value=True):
                result = SQLLoader.load_sql("test")

        assert result == mock_sql

    def test_load_sql_file_not_found(self):
        """Test loading SQL when file doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                SQLLoader.load_sql("nonexistent")

    def test_get_schemas_query(self):
        """Test getting schemas query."""
        mock_sql = "SELECT * FROM schemas;"

        with patch.object(SQLLoader, "load_sql", return_value=mock_sql):
            result = SQLLoader.get_schemas_query()

        assert result == mock_sql

    def test_get_tables_query(self):
        """Test getting tables query with schema replacement."""
        mock_sql = "SELECT * FROM {schema_name}.tables;"
        expected = "SELECT * FROM test_schema.tables;"

        with patch.object(SQLLoader, "load_sql", return_value=mock_sql):
            result = SQLLoader.get_tables_query("test_schema")

        assert result == expected

    def test_get_table_schema_query(self):
        """Test getting table schema query with replacements."""
        mock_sql = "SELECT * FROM {schema_name}.{table};"
        expected = "SELECT * FROM test_schema.test_table;"

        with patch.object(SQLLoader, "load_sql", return_value=mock_sql):
            result = SQLLoader.get_table_schema_query("test_schema", "test_table")

        assert result == expected

    def test_get_migrations_query(self):
        """Test getting migrations query with all parameters."""
        mock_sql = (
            "SELECT * FROM migrations WHERE name LIKE '%{name_pattern}%' LIMIT {limit} OFFSET "
            "{offset} AND include_queries = {include_full_queries};"
        )
        expected = "SELECT * FROM migrations WHERE name LIKE '%test%' LIMIT 10 OFFSET 5 AND include_queries = true;"

        with patch.object(SQLLoader, "load_sql", return_value=mock_sql):
            result = SQLLoader.get_migrations_query(limit=10, offset=5, name_pattern="test", include_full_queries=True)

        assert result == expected

    def test_get_init_migrations_query(self):
        """Test getting init migrations query."""
        mock_sql = "CREATE SCHEMA IF NOT EXISTS migrations;"

        with patch.object(SQLLoader, "load_sql", return_value=mock_sql):
            result = SQLLoader.get_init_migrations_query()

        assert result == mock_sql

    def test_get_create_migration_query(self):
        """Test getting create migration query with replacements."""
        mock_sql = "INSERT INTO migrations VALUES ('{version}', '{name}', ARRAY['{statements}']);"
        expected = "INSERT INTO migrations VALUES ('20230101', 'test_migration', ARRAY['SELECT 1;']);"

        with patch.object(SQLLoader, "load_sql", return_value=mock_sql):
            result = SQLLoader.get_create_migration_query(
                version="20230101", name="test_migration", statements="SELECT 1;"
            )

        assert result == expected

    def test_sql_dir_path(self):
        """Test that SQL_DIR points to the correct location."""
        expected_path = Path(SQLLoader.__module__.replace(".", os.sep)).parent / "queries"
        assert str(SQLLoader.SQL_DIR).endswith(str(expected_path))
