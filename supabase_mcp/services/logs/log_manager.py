from typing import Any

from supabase_mcp.logger import logger
from supabase_mcp.services.database.sql.loader import SQLLoader


class LogManager:
    """Manager for retrieving logs from Supabase services."""

    # Map collection names to table names
    COLLECTION_TO_TABLE = {
        "postgres": "postgres_logs",
        "api_gateway": "edge_logs",
        "auth": "auth_logs",
        "postgrest": "postgrest_logs",
        "pooler": "supavisor_logs",
        "storage": "storage_logs",
        "realtime": "realtime_logs",
        "edge_functions": "function_edge_logs",
        "cron": "postgres_logs",
        "pgbouncer": "pgbouncer_logs",
    }

    def __init__(self) -> None:
        """Initialize the LogManager."""
        self.sql_loader = SQLLoader()

    def _build_where_clause(
        self,
        collection: str,
        hours_ago: int | None = None,
        filters: list[dict[str, Any]] | None = None,
        search: str | None = None,
    ) -> str:
        """Build the WHERE clause for a log query.

        Args:
            collection: The log collection name
            hours_ago: Number of hours to look back
            filters: List of filter objects with field, operator, and value
            search: Text to search for in event messages

        Returns:
            The WHERE clause as a string
        """
        logger.debug(
            f"Building WHERE clause for collection={collection}, hours_ago={hours_ago}, "
            f"filters={filters}, search={search}"
        )

        clauses = []

        # Get the table name for this collection
        table_name = self.COLLECTION_TO_TABLE.get(collection, collection)

        # Add time filter using BigQuery's TIMESTAMP_SUB function
        if hours_ago:
            # Qualify the timestamp column with the table name to avoid ambiguity
            clauses.append(f"{table_name}.timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours_ago} HOUR)")

        # Add search filter
        if search:
            # Escape single quotes in search text
            search_escaped = search.replace("'", "''")
            clauses.append(f"event_message LIKE '%{search_escaped}%'")

        # Add custom filters
        if filters:
            for filter_obj in filters:
                field = filter_obj["field"]
                operator = filter_obj["operator"]
                value = filter_obj["value"]

                # Handle string values
                if isinstance(value, str) and not value.isdigit():
                    value = f"'{value.replace("'", "''")}'"

                clauses.append(f"{field} {operator} {value}")

        # For cron logs, we already have a WHERE clause in the template
        if collection == "cron":
            if clauses:
                where_clause = f"AND {' AND '.join(clauses)}"
            else:
                where_clause = ""
        else:
            if clauses:
                where_clause = f"WHERE {' AND '.join(clauses)}"
            else:
                where_clause = ""

        logger.debug(f"Built WHERE clause: {where_clause}")
        return where_clause

    def build_logs_query(
        self,
        collection: str,
        limit: int = 20,
        hours_ago: int | None = 1,
        filters: list[dict[str, Any]] | None = None,
        search: str | None = None,
        custom_query: str | None = None,
    ) -> str:
        """Build a query for retrieving logs from a Supabase service.

        Args:
            collection: The log collection to query
            limit: Maximum number of log entries to return
            hours_ago: Retrieve logs from the last N hours
            filters: List of filter objects with field, operator, and value
            search: Text to search for in event messages
            custom_query: Complete custom SQL query to execute

        Returns:
            The SQL query string

        Raises:
            ValueError: If the collection is unknown
        """
        if custom_query:
            return custom_query

        # Build the WHERE clause
        where_clause = self._build_where_clause(
            collection=collection, hours_ago=hours_ago, filters=filters, search=search
        )

        # Get the SQL query
        return self.sql_loader.get_logs_query(collection=collection, where_clause=where_clause, limit=limit)
