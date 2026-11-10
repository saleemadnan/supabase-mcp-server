from typing import Any

from pglast.parser import ParseError, parse_sql

from supabase_mcp.exceptions import ValidationError
from supabase_mcp.logger import logger
from supabase_mcp.services.database.sql.models import (
    QueryValidationResults,
    SQLQueryCategory,
    SQLQueryCommand,
    ValidatedStatement,
)
from supabase_mcp.services.safety.safety_configs import SQLSafetyConfig


class SQLValidator:
    """SQL validator class that is based on pglast library.

    Responsible for:
    - SQL query syntax validation
    - SQL query categorization"""

    # Mapping from statement types to object types
    STATEMENT_TYPE_TO_OBJECT_TYPE = {
        "CreateFunctionStmt": "function",
        "ViewStmt": "view",
        "CreateTableAsStmt": "materialized_view",  # When relkind is 'm', otherwise 'table'
        "CreateEnumStmt": "type",
        "CreateTypeStmt": "type",
        "CreateExtensionStmt": "extension",
        "CreateForeignTableStmt": "foreign_table",
        "CreatePolicyStmt": "policy",
        "CreateTrigStmt": "trigger",
        "IndexStmt": "index",
        "CreateStmt": "table",
        "AlterTableStmt": "table",
        "GrantStmt": "privilege",
        "RevokeStmt": "privilege",
        "CreateProcStmt": "procedure",  # For CREATE PROCEDURE
    }

    def __init__(self, safety_config: SQLSafetyConfig | None = None) -> None:
        self.safety_config = safety_config or SQLSafetyConfig()

    def validate_schema_name(self, schema_name: str) -> str:
        """Validate schema name.

        Rules:
        - Must be a string
        - Cannot be empty
        - Cannot contain spaces or special characters
        """
        if not schema_name.strip():
            raise ValidationError("Schema name cannot be empty")
        if " " in schema_name:
            raise ValidationError("Schema name cannot contain spaces")
        return schema_name

    def validate_table_name(self, table: str) -> str:
        """Validate table name.

        Rules:
        - Must be a string
        - Cannot be empty
        - Cannot contain spaces or special characters
        """
        if not table.strip():
            raise ValidationError("Table name cannot be empty")
        if " " in table:
            raise ValidationError("Table name cannot contain spaces")
        return table

    def basic_query_validation(self, query: str) -> str:
        """Validate SQL query.

        Rules:
        - Must be a string
        - Cannot be empty
        """
        if not query.strip():
            raise ValidationError("Query cannot be empty")
        return query

    @classmethod
    def validate_transaction_control(cls, query: str) -> bool:
        """Check if the query contains transaction control statements.

        Args:
            query: SQL query string

        Returns:
            bool: True if the query contains any transaction control statements
        """
        return any(x in query.upper() for x in ["BEGIN", "COMMIT", "ROLLBACK"])

    def validate_query(self, sql_query: str) -> QueryValidationResults:
        """
        Identify the type of SQL query using PostgreSQL's parser.

        Args:
            sql_query: A SQL query string to parse

        Returns:
            QueryValidationResults: A validation result object containing information about the SQL statements
        Raises:
            ValidationError: If the query is not valid or contains TCL statements
        """
        try:
            # Validate raw input
            sql_query = self.basic_query_validation(sql_query)

            # Parse the SQL using PostgreSQL's parser
            parse_tree = parse_sql(sql_query)
            if parse_tree is None:
                logger.debug("No statements found in the query")
            # logger.debug(f"Parse tree generated with {parse_tree} statements")

            # Validate statements
            result = self.validate_statements(original_query=sql_query, parse_tree=parse_tree)

            # Check if the query contains transaction control statements and reject them
            for statement in result.statements:
                if statement.category == SQLQueryCategory.TCL:
                    logger.warning(f"Transaction control statement detected: {statement.command}")
                    raise ValidationError(
                        "Transaction control statements (BEGIN, COMMIT, ROLLBACK) are not allowed. "
                        "Queries will be automatically wrapped in transactions by the system."
                    )

            return result
        except ParseError as e:
            logger.exception(f"SQL syntax error: {str(e)}")
            raise ValidationError(f"SQL syntax error: {str(e)}") from e
        except ValidationError:
            # let it propagate
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during SQL validation: {str(e)}")
            raise ValidationError(f"Unexpected error during SQL validation: {str(e)}") from e

    def _map_to_command(self, stmt_type: str) -> SQLQueryCommand:
        """Map a pglast statement type to our SQLQueryCommand enum."""

        mapping = {
            # DQL Commands
            "SelectStmt": SQLQueryCommand.SELECT,
            # DML Commands
            "InsertStmt": SQLQueryCommand.INSERT,
            "UpdateStmt": SQLQueryCommand.UPDATE,
            "DeleteStmt": SQLQueryCommand.DELETE,
            "MergeStmt": SQLQueryCommand.MERGE,
            # DDL Commands
            "CreateStmt": SQLQueryCommand.CREATE,
            "CreateTableAsStmt": SQLQueryCommand.CREATE,
            "CreateSchemaStmt": SQLQueryCommand.CREATE,
            "CreateExtensionStmt": SQLQueryCommand.CREATE,
            "CreateFunctionStmt": SQLQueryCommand.CREATE,
            "CreateTrigStmt": SQLQueryCommand.CREATE,
            "ViewStmt": SQLQueryCommand.CREATE,
            "IndexStmt": SQLQueryCommand.CREATE,
            # Additional DDL Commands
            "CreateEnumStmt": SQLQueryCommand.CREATE,
            "CreateTypeStmt": SQLQueryCommand.CREATE,
            "CreateDomainStmt": SQLQueryCommand.CREATE,
            "CreateSeqStmt": SQLQueryCommand.CREATE,
            "CreateForeignTableStmt": SQLQueryCommand.CREATE,
            "CreatePolicyStmt": SQLQueryCommand.CREATE,
            "CreateCastStmt": SQLQueryCommand.CREATE,
            "CreateOpClassStmt": SQLQueryCommand.CREATE,
            "CreateOpFamilyStmt": SQLQueryCommand.CREATE,
            "AlterTableStmt": SQLQueryCommand.ALTER,
            "AlterDomainStmt": SQLQueryCommand.ALTER,
            "AlterEnumStmt": SQLQueryCommand.ALTER,
            "AlterSeqStmt": SQLQueryCommand.ALTER,
            "AlterOwnerStmt": SQLQueryCommand.ALTER,
            "AlterObjectSchemaStmt": SQLQueryCommand.ALTER,
            "DropStmt": SQLQueryCommand.DROP,
            "TruncateStmt": SQLQueryCommand.TRUNCATE,
            "CommentStmt": SQLQueryCommand.COMMENT,
            "RenameStmt": SQLQueryCommand.RENAME,
            # DCL Commands
            "GrantStmt": SQLQueryCommand.GRANT,
            "GrantRoleStmt": SQLQueryCommand.GRANT,
            "RevokeStmt": SQLQueryCommand.REVOKE,
            "RevokeRoleStmt": SQLQueryCommand.REVOKE,
            "CreateRoleStmt": SQLQueryCommand.CREATE,
            "AlterRoleStmt": SQLQueryCommand.ALTER,
            "DropRoleStmt": SQLQueryCommand.DROP,
            # TCL Commands
            "TransactionStmt": SQLQueryCommand.BEGIN,  # Will need refinement for different transaction types
            # PostgreSQL-specific Commands
            "VacuumStmt": SQLQueryCommand.VACUUM,
            "ExplainStmt": SQLQueryCommand.EXPLAIN,
            "CopyStmt": SQLQueryCommand.COPY,
            "ListenStmt": SQLQueryCommand.LISTEN,
            "NotifyStmt": SQLQueryCommand.NOTIFY,
            "PrepareStmt": SQLQueryCommand.PREPARE,
            "ExecuteStmt": SQLQueryCommand.EXECUTE,
            "DeallocateStmt": SQLQueryCommand.DEALLOCATE,
        }

        # Try to map the statement type, default to UNKNOWN
        return mapping.get(stmt_type, SQLQueryCommand.UNKNOWN)

    @staticmethod
    def extract_statement_text(original_query: str, stmt_location: int, stmt_len: int) -> str:
        """Extract the SQL text of a single statement from the original query.

        libpg_query (via pglast) reports ``stmt_len == 0`` for the last statement when it is not
        terminated by a semicolon, meaning "up to the end of the input". Slicing with a zero length
        would yield an empty string and the statement would silently never run.

        pglast reports positions as character offsets (not UTF-8 byte offsets), so they can be used
        directly to slice the Python string.

        Args:
            original_query: The full SQL text that was parsed
            stmt_location: Start offset of the statement
            stmt_len: Length of the statement, or 0 for "to the end of the input"

        Returns:
            str: The statement text without surrounding whitespace or a trailing semicolon
        """
        end = len(original_query) if stmt_len == 0 else stmt_location + stmt_len
        return original_query[stmt_location:end].strip().rstrip(";").rstrip()

    def validate_statements(self, original_query: str, parse_tree: Any) -> QueryValidationResults:
        """Validate the statements in the parse tree.

        Args:
            parse_tree: The parse tree to validate

        Returns:
            SQLBatchValidationResult: A validation result object containing information about the SQL statements
        Raises:
            ValidationError: If the query is not valid
        """
        result = QueryValidationResults(original_query=original_query)

        if parse_tree is None:
            return result

        try:
            for stmt in parse_tree:
                if not hasattr(stmt, "stmt"):
                    continue

                stmt_node = stmt.stmt
                stmt_type = stmt_node.__class__.__name__
                logger.debug(f"Processing statement node type: {stmt_type}")
                # logger.debug(f"DEBUGGING stmt_node: {stmt_node}")
                logger.debug(f"DEBUGGING stmt_node.stmt_location: {stmt.stmt_location}")

                # Extract the object type if available
                object_type = None
                schema_name = None
                if hasattr(stmt_node, "relation") and stmt_node.relation is not None:
                    if hasattr(stmt_node.relation, "relname"):
                        object_type = stmt_node.relation.relname
                    if hasattr(stmt_node.relation, "schemaname"):
                        schema_name = stmt_node.relation.schemaname
                # For statements with 'relations' list (like TRUNCATE)
                elif hasattr(stmt_node, "relations") and stmt_node.relations:
                    for relation in stmt_node.relations:
                        if hasattr(relation, "relname"):
                            object_type = relation.relname
                        if hasattr(relation, "schemaname"):
                            schema_name = relation.schemaname
                        break

                # Simple approach: Set object_type based on statement type if not already set
                if object_type is None and stmt_type in self.STATEMENT_TYPE_TO_OBJECT_TYPE:
                    object_type = self.STATEMENT_TYPE_TO_OBJECT_TYPE[stmt_type]

                # Default schema to public if not set
                if schema_name is None:
                    schema_name = "public"

                # Get classification for this statement type
                classification = self.safety_config.classify_statement(stmt_type, stmt_node)
                logger.debug(
                    f"Statement category classified as: {classification.get('category', 'UNKNOWN')} - "
                    f"risk level: {classification.get('risk_level', 'UNKNOWN')}"
                )
                logger.debug(f"DEBUGGING QUERY EXTRACTION LOCATION: {stmt.stmt_location} - {stmt.stmt_len}")

                # Create validation result
                query_result = ValidatedStatement(
                    category=classification["category"],
                    command=self._map_to_command(stmt_type),
                    risk_level=classification["risk_level"],
                    needs_migration=classification["needs_migration"],
                    object_type=object_type,
                    schema_name=schema_name,
                    query=self.extract_statement_text(original_query, stmt.stmt_location, stmt.stmt_len)
                    if hasattr(stmt, "stmt_location") and hasattr(stmt, "stmt_len")
                    else None,
                )
                # logger.debug(f"Isolated query: {query_result.query}")
                logger.debug(
                    "Query validation result:",
                    {
                        "statement_category": query_result.category,
                        "risk_level": query_result.risk_level,
                        "needs_migration": query_result.needs_migration,
                        "object_type": query_result.object_type,
                        "schema_name": query_result.schema_name,
                        "query": query_result.query,
                    },
                )

                # Add result to the batch
                result.statements.append(query_result)

                # Update highest risk level
                if query_result.risk_level > result.highest_risk_level:
                    result.highest_risk_level = query_result.risk_level
                    logger.debug(f"Updated batch validation result to: {query_result.risk_level}")
            if len(result.statements) == 0:
                logger.debug("No valid statements found in the query")
                raise ValidationError("No queries were parsed - please check correctness of your query")
            logger.debug(
                f"Validated a total of {len(result.statements)} with the highest risk level of: "
                f"{result.highest_risk_level}"
            )
            return result

        except AttributeError as e:
            # Handle attempting to access missing attributes in the parse tree
            raise ValidationError(f"Error accessing parse tree structure: {str(e)}") from e
        except KeyError as e:
            # Handle missing keys in classification dictionary
            raise ValidationError(f"Missing classification key: {str(e)}") from e
