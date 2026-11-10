import pytest


@pytest.fixture
def sample_dql_queries() -> dict[str, str]:
    """Sample DQL (SELECT) queries for testing."""
    return {
        "simple_select": "SELECT * FROM users",
        "select_with_where": "SELECT id, name FROM users WHERE age > 18",
        "select_with_join": "SELECT u.id, p.title FROM users u JOIN posts p ON u.id = p.user_id",
        "select_with_subquery": "SELECT * FROM users WHERE id IN (SELECT user_id FROM posts)",
        "select_with_cte": "WITH active_users AS (SELECT * FROM users WHERE active = true) SELECT * FROM active_users",
    }


@pytest.fixture
def sample_dml_queries() -> dict[str, str]:
    """Sample DML (INSERT, UPDATE, DELETE) queries for testing."""
    return {
        "simple_insert": "INSERT INTO users (name, email) VALUES ('John', 'john@example.com')",
        "insert_with_select": "INSERT INTO user_backup SELECT * FROM users",
        "simple_update": "UPDATE users SET active = true WHERE id = 1",
        "simple_delete": "DELETE FROM users WHERE id = 1",
        "merge_statement": "MERGE INTO users u USING temp_users t ON (u.id = t.id) WHEN MATCHED THEN UPDATE SET name = "
        "t.name",
    }


@pytest.fixture
def sample_ddl_queries() -> dict[str, str]:
    """Sample DDL (CREATE, ALTER, DROP) queries for testing."""
    return {
        "create_table": "CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT, email TEXT UNIQUE)",
        "alter_table": "ALTER TABLE users ADD COLUMN active BOOLEAN DEFAULT false",
        "drop_table": "DROP TABLE users",
        "truncate_table": "TRUNCATE TABLE users",
        "create_index": "CREATE INDEX idx_user_email ON users (email)",
    }


@pytest.fixture
def sample_dcl_queries() -> dict[str, str]:
    """Sample DCL (GRANT, REVOKE) queries for testing."""
    return {
        "grant_select": "GRANT SELECT ON users TO read_role",
        "grant_all": "GRANT ALL PRIVILEGES ON users TO admin_role",
        "revoke_select": "REVOKE SELECT ON users FROM read_role",
        "create_role": "CREATE ROLE read_role",
        "drop_role": "DROP ROLE read_role",
    }


@pytest.fixture
def sample_tcl_queries() -> dict[str, str]:
    """Sample TCL (BEGIN, COMMIT, ROLLBACK) queries for testing."""
    return {
        "begin_transaction": "BEGIN",
        "commit_transaction": "COMMIT",
        "rollback_transaction": "ROLLBACK",
        "savepoint": "SAVEPOINT my_savepoint",
        "mixed_case_transaction": "Begin Transaction",
    }


@pytest.fixture
def sample_postgres_specific_queries() -> dict[str, str]:
    """Sample PostgreSQL-specific queries for testing."""
    return {
        "vacuum": "VACUUM users",
        "analyze": "ANALYZE users",
        "copy_to": "COPY users TO '/tmp/users.csv' WITH CSV",
        "copy_from": "COPY users FROM '/tmp/users.csv' WITH CSV",
        "explain": "EXPLAIN ANALYZE SELECT * FROM users",
    }


@pytest.fixture
def sample_invalid_queries() -> dict[str, str]:
    """Sample invalid SQL queries for testing error handling."""
    return {
        "syntax_error": "SELECT * FORM users",
        "missing_parenthesis": "SELECT * FROM users WHERE id IN (1, 2, 3",
        "invalid_column": "SELECT nonexistent_column FROM users",
        "incomplete_statement": "SELECT * FROM",
        "invalid_table": "SELECT * FROM nonexistent_table",
    }


@pytest.fixture
def sample_multiple_statements() -> dict[str, str]:
    """Sample SQL with multiple statements for testing batch processing."""
    return {
        "multiple_safe": "SELECT * FROM users; SELECT * FROM posts;",
        "safe_and_write": "SELECT * FROM users; INSERT INTO logs (message) VALUES ('queried users');",
        "write_and_destructive": "INSERT INTO logs (message) VALUES ('dropping users'); DROP TABLE users;",
        "with_transaction": "BEGIN; INSERT INTO users (name) VALUES ('John'); COMMIT;",
        "mixed_categories": "SELECT * FROM users; UPDATE users SET active = true; DROP TABLE old_users;",
    }


@pytest.fixture
def sample_edge_cases() -> dict[str, str]:
    """Sample edge cases for testing."""
    return {
        "with_comments": "SELECT * FROM users; -- This is a comment\n/* Multi-line\ncomment */",
        "quoted_identifiers": 'SELECT * FROM "user table" WHERE "first name" = \'John\'',
        "special_characters": "SELECT * FROM users WHERE name LIKE 'O''Brien%'",
        "schema_qualified": "SELECT * FROM public.users",
        "with_dollar_quotes": "SELECT $$This is a dollar-quoted string with 'quotes'$$ AS message",
    }
