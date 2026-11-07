import datetime
import hashlib
import re
import threading
from typing import ClassVar

from supabase_mcp.logger import logger
from supabase_mcp.services.database.sql.loader import SQLLoader
from supabase_mcp.services.database.sql.models import (
    QueryValidationResults,
    SQLQueryCategory,
    ValidatedStatement,
)


class MigrationManager:
    """Responsible for preparing migration scripts without executing them."""

    VERSION_FORMAT: ClassVar[str] = "%Y%m%d%H%M%S"

    # Shared by all instances so that versions are unique process-wide
    _version_lock: ClassVar[threading.Lock] = threading.Lock()
    _last_version: ClassVar[datetime.datetime | None] = None

    def __init__(self, loader: SQLLoader | None = None):
        """Initialize the migration manager with a SQL loader.

        Args:
            loader: The SQL loader to use for loading SQL queries
        """
        self.loader = loader or SQLLoader()

    def prepare_migration_query(
        self,
        validation_result: QueryValidationResults,
        original_query: str,
        migration_name: str = "",
    ) -> tuple[str, str]:
        """
        Prepare a migration script without executing it.

        Args:
            validation_result: The validation result
            original_query: The original query
            migration_name: The name of the migration, if provided by the client

        Returns:
            Complete SQL query to create the migration
            Migration name
        """
        # If client provided a name, use it directly without generating a new one
        if migration_name.strip():
            name = self.sanitize_name(migration_name)
        else:
            # Otherwise generate a descriptive name
            name = self.generate_descriptive_name(validation_result)

        # Generate migration version (timestamp)
        version = self.generate_query_timestamp()

        # Escape single quotes in the query for SQL safety
        statements = original_query.replace("'", "''")

        # Get the migration query using the loader
        migration_query = self.loader.get_create_migration_query(version, name, statements)

        logger.info(f"Prepared migration: {version}_{name}")

        # Return the complete query
        return migration_query, name

    def sanitize_name(self, name: str) -> str:
        """
        Generate a standardized name for a migration script.

        Args:
            name: Raw migration name

        Returns:
            str: Sanitized migration name
        """
        # Remove special characters and replace spaces with underscores
        sanitized_name = re.sub(r"[^\w\s]", "", name).lower()
        sanitized_name = re.sub(r"\s+", "_", sanitized_name)

        # Ensure the name is not too long (max 100 chars)
        if len(sanitized_name) > 100:
            sanitized_name = sanitized_name[:100]

        return sanitized_name

    def generate_descriptive_name(
        self,
        query_validation_result: QueryValidationResults,
    ) -> str:
        """
        Generate a descriptive name for a migration based on the validation result.

        This method should only be called when no client-provided name is available.

        Priority order:
        1. Auto-generated name based on SQL analysis
        2. Fallback to hash if no meaningful information can be extracted

        Args:
            query_validation_result: Validation result for a batch of SQL statements

        Returns:
            str: Descriptive migration name
        """
        # Case 1: No client-provided name, generate descriptive name
        # Find the first statement that needs migration
        statement = None
        for stmt in query_validation_result.statements:
            if stmt.needs_migration:
                statement = stmt
                break

        # If no statement found (unlikely), use a hash-based name
        if not statement:
            logger.warning(
                "No statement found in validation result, using hash-based name, statements: %s",
                query_validation_result.statements,
            )
            # Generate a short hash from the query text
            query_hash = self._generate_short_hash(query_validation_result.original_query)
            return f"migration_{query_hash}"

        # Generate name based on statement category and command
        logger.debug(f"Generating name for statement: {statement}")
        if statement.category == SQLQueryCategory.DDL:
            return self._generate_ddl_name(statement)
        elif statement.category == SQLQueryCategory.DML:
            return self._generate_dml_name(statement)
        elif statement.category == SQLQueryCategory.DCL:
            return self._generate_dcl_name(statement)
        else:
            # Fallback for other categories
            return self._generate_generic_name(statement)

    def _generate_short_hash(self, text: str) -> str:
        """Generate a short hash from text for use in migration names."""
        hash_object = hashlib.md5(text.encode())
        return hash_object.hexdigest()[:8]  # First 8 chars of MD5 hash

    def _generate_ddl_name(self, statement: ValidatedStatement) -> str:
        """
        Generate a name for DDL statements (CREATE, ALTER, DROP).
        Format: {command}_{object_type}_{schema}_{object_name}
        Examples:
        - create_table_public_users
        - alter_function_auth_authenticate
        - drop_index_public_users_email_idx
        """
        command = statement.command.value.lower()
        schema = statement.schema_name.lower() if statement.schema_name else "public"

        # Extract object type and name with enhanced detection
        object_type = "object"  # Default fallback
        object_name = "unknown"  # Default fallback

        # Enhanced object type detection based on command
        if statement.object_type:
            object_type = statement.object_type.lower()

            # Handle specific object types
            if object_type == "table" and statement.query:
                object_name = self._extract_table_name(statement.query)
            elif (object_type == "function" or object_type == "procedure") and statement.query:
                object_name = self._extract_function_name(statement.query)
            elif object_type == "trigger" and statement.query:
                object_name = self._extract_trigger_name(statement.query)
            elif object_type == "index" and statement.query:
                object_name = self._extract_index_name(statement.query)
            elif object_type == "view" and statement.query:
                object_name = self._extract_view_name(statement.query)
            elif object_type == "materialized_view" and statement.query:
                object_name = self._extract_materialized_view_name(statement.query)
            elif object_type == "sequence" and statement.query:
                object_name = self._extract_sequence_name(statement.query)
            elif object_type == "constraint" and statement.query:
                object_name = self._extract_constraint_name(statement.query)
            elif object_type == "foreign_table" and statement.query:
                object_name = self._extract_foreign_table_name(statement.query)
            elif object_type == "extension" and statement.query:
                object_name = self._extract_extension_name(statement.query)
            elif object_type == "type" and statement.query:
                object_name = self._extract_type_name(statement.query)
            elif statement.query:
                # For other object types (the validator reports the relation name for table statements),
                # prefer the table name before falling back to a generic extraction
                object_name = self._extract_table_name(statement.query)
                if object_name == "unknown":
                    object_name = self._extract_generic_object_name(statement.query)

        # Combine parts into a descriptive name
        name = f"{command}_{object_type}_{schema}_{object_name}"
        return self.sanitize_name(name)

    def _generate_dml_name(self, statement: ValidatedStatement) -> str:
        """
        Generate a name for DML statements (INSERT, UPDATE, DELETE).
        Format: {command}_{schema}_{table_name}
        Examples:
        - insert_public_users
        - update_auth_users
        - delete_public_logs
        """
        command = statement.command.value.lower()
        schema = statement.schema_name.lower() if statement.schema_name else "public"

        # Extract table name
        table_name = "unknown"
        if statement.query:
            table_name = self._extract_table_name(statement.query) or "unknown"

        # For UPDATE and DELETE, add what's being modified if possible
        if command == "update" and statement.query:
            # Try to extract column names being updated
            columns = self._extract_update_columns(statement.query)
            if columns:
                return self.sanitize_name(f"{command}_{columns}_in_{schema}_{table_name}")

        # Default format
        name = f"{command}_{schema}_{table_name}"
        return self.sanitize_name(name)

    def _generate_dcl_name(self, statement: ValidatedStatement) -> str:
        """
        Generate a name for DCL statements (GRANT, REVOKE).
        Format: {command}_{privilege}_{schema}_{object_name}
        Examples:
        - grant_select_public_users
        - revoke_all_public_items
        """
        command = statement.command.value.lower()
        schema = statement.schema_name.lower() if statement.schema_name else "public"

        # Extract privilege and object name
        privilege = "privilege"
        object_name = "unknown"

        if statement.query:
            privilege = self._extract_privilege(statement.query) or "privilege"
            object_name = self._extract_dcl_object_name(statement.query) or "unknown"

        name = f"{command}_{privilege}_{schema}_{object_name}"
        return self.sanitize_name(name)

    def _generate_generic_name(self, statement: ValidatedStatement) -> str:
        """
        Generate a name for other statement types.
        Format: {command}_{schema}_{object_type}
        """
        command = statement.command.value.lower()
        schema = statement.schema_name.lower() if statement.schema_name else "public"
        object_type = statement.object_type.lower() if statement.object_type else "object"

        name = f"{command}_{schema}_{object_type}"
        return self.sanitize_name(name)

    # Helper methods for extracting specific parts from SQL queries

    def _extract_table_name(self, query: str) -> str:
        """Extract table name from a query."""
        if not query:
            return "unknown"

        # Simple regex-based extraction for demonstration
        # In a real implementation, this would use more sophisticated parsing
        import re

        # For CREATE TABLE
        match = re.search(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(2)

        # For ALTER TABLE
        match = re.search(r"ALTER\s+TABLE\s+(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(2)

        # For DROP TABLE
        match = re.search(r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(2)

        # For INSERT, UPDATE, DELETE
        match = re.search(r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(2)

        return "unknown"

    def _extract_function_name(self, query: str) -> str:
        """Extract function name from a query."""
        if not query:
            return "unknown"

        import re

        match = re.search(
            r"(?:CREATE|ALTER|DROP)\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:(\w+)\.)?(\w+)", query, re.IGNORECASE
        )
        if match:
            return match.group(2)

        return "unknown"

    def _extract_trigger_name(self, query: str) -> str:
        """Extract trigger name from a query."""
        if not query:
            return "unknown"

        import re

        match = re.search(r"(?:CREATE|ALTER|DROP)\s+TRIGGER\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(1)

        return "unknown"

    def _extract_view_name(self, query: str) -> str:
        """Extract view name from a query."""
        if not query:
            return "unknown"

        import re

        match = re.search(r"(?:CREATE|ALTER|DROP)\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(2)

        return "unknown"

    def _extract_index_name(self, query: str) -> str:
        """Extract index name from a query."""
        if not query:
            return "unknown"

        import re

        match = re.search(r"(?:CREATE|DROP)\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(2)

        return "unknown"

    def _extract_sequence_name(self, query: str) -> str:
        """Extract sequence name from a query."""
        if not query:
            return "unknown"

        import re

        match = re.search(
            r"(?:CREATE|ALTER|DROP)\s+SEQUENCE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:(\w+)\.)?(\w+)", query, re.IGNORECASE
        )
        if match:
            return match.group(2)

        return "unknown"

    def _extract_constraint_name(self, query: str) -> str:
        """Extract constraint name from a query."""
        if not query:
            return "unknown"

        import re

        match = re.search(r"CONSTRAINT\s+(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(1)

        return "unknown"

    def _extract_update_columns(self, query: str) -> str:
        """Extract columns being updated in an UPDATE statement."""
        if not query:
            return ""

        import re

        # This is a simplified approach - a real implementation would use proper SQL parsing
        match = re.search(r"UPDATE\s+(?:\w+\.)?(?:\w+)\s+SET\s+([\w\s,=]+)\s+WHERE", query, re.IGNORECASE)
        if match:
            # Extract column names from the SET clause
            set_clause = match.group(1)
            columns = re.findall(r"(\w+)\s*=", set_clause)
            if columns and len(columns) <= 3:  # Limit to 3 columns to keep name reasonable
                return "_".join(columns)
            elif columns:
                return f"{columns[0]}_and_others"

        return ""

    def _extract_privilege(self, query: str) -> str:
        """Extract privilege from a GRANT or REVOKE statement."""
        if not query:
            return "privilege"

        import re

        match = re.search(r"(?:GRANT|REVOKE)\s+([\w\s,]+)\s+ON", query, re.IGNORECASE)
        if match:
            privileges = match.group(1).strip().lower()
            if "all" in privileges:
                return "all"
            elif "select" in privileges:
                return "select"
            elif "insert" in privileges:
                return "insert"
            elif "update" in privileges:
                return "update"
            elif "delete" in privileges:
                return "delete"

        return "privilege"

    def _extract_dcl_object_name(self, query: str) -> str:
        """Extract object name from a GRANT or REVOKE statement."""
        if not query:
            return "unknown"

        import re

        match = re.search(r"ON\s+(?:TABLE\s+)?(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(2)

        return "unknown"

    def _extract_generic_object_name(self, query: str) -> str:
        """Extract a generic object name when specific extractors don't apply."""
        if not query:
            return "unknown"

        import re

        # Look for common patterns of object names in SQL
        patterns = [
            r"(?:CREATE|ALTER|DROP)\s+(?:\w+\s+)+(?:(\w+)\.)?(\w+)",  # General DDL pattern
            r"ON\s+(?:(\w+)\.)?(\w+)",  # ON clause
            r"FROM\s+(?:(\w+)\.)?(\w+)",  # FROM clause
            r"INTO\s+(?:(\w+)\.)?(\w+)",  # INTO clause
        ]

        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match and match.group(2):
                return match.group(2)

        return "unknown"

    def _extract_materialized_view_name(self, query: str) -> str:
        """Extract materialized view name from a query."""
        if not query:
            return "unknown"

        import re

        match = re.search(
            r"(?:CREATE|ALTER|DROP|REFRESH)\s+(?:MATERIALIZED\s+VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:(\w+)\.)?(\w+)",
            query,
            re.IGNORECASE,
        )
        if match:
            return match.group(2)

        return "unknown"

    def _extract_foreign_table_name(self, query: str) -> str:
        """Extract foreign table name from a query."""
        if not query:
            return "unknown"

        import re

        match = re.search(
            r"(?:CREATE|ALTER|DROP)\s+(?:FOREIGN\s+TABLE)\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:(\w+)\.)?(\w+)",
            query,
            re.IGNORECASE,
        )
        if match:
            return match.group(2)

        return "unknown"

    def _extract_extension_name(self, query: str) -> str:
        """Extract extension name from a query."""
        if not query:
            return "unknown"

        import re

        match = re.search(r"(?:CREATE|ALTER|DROP)\s+EXTENSION\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(1)

        return "unknown"

    def _extract_type_name(self, query: str) -> str:
        """Extract custom type name from a query."""
        if not query:
            return "unknown"

        import re

        # For ENUM types
        match = re.search(r"(?:CREATE|ALTER|DROP)\s+TYPE\s+(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(2)

        # For DOMAIN types
        match = re.search(r"(?:CREATE|ALTER|DROP)\s+DOMAIN\s+(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            return match.group(2)

        return "unknown"

    def generate_query_timestamp(self) -> str:
        """
        Generate a unique migration version in the format YYYYMMDDHHMMSS.

        The version is the primary key of ``supabase_migrations.schema_migrations``, so two schema
        changes within the same second must not share it, or the second migration record is lost.
        Versions are therefore strictly increasing within the process: when the current second was
        already used (or the clock moved backwards), the last issued version is bumped by one second.
        The 14-digit format is kept for compatibility with Supabase CLI migration versions, and stays
        sortable both numerically and as text.

        Returns:
            str: Timestamp string
        """
        now = datetime.datetime.now().replace(microsecond=0)
        with MigrationManager._version_lock:
            last = MigrationManager._last_version
            if last is not None and now <= last:
                now = last + datetime.timedelta(seconds=1)
            MigrationManager._last_version = now
        return now.strftime(self.VERSION_FORMAT)
