import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, TypeVar

from supabase_mcp.services.database.sql.models import (
    QueryValidationResults,
    SQLQueryCategory,
)
from supabase_mcp.services.safety.models import OperationRiskLevel, SafetyMode

T = TypeVar("T")


class SafetyConfigBase(Generic[T], ABC):
    """Abstract base class for all SafetyConfig classes of specific clients.

    Provides methods:
    - register safety configuration
    - to get / set safety level
    - check safety level of operation
    """

    @abstractmethod
    def get_risk_level(self, operation: T) -> OperationRiskLevel:
        """Get the risk level for an operation.

        Args:
            operation: The operation to check

        Returns:
            The risk level for the operation
        """
        pass

    def is_operation_allowed(self, risk_level: OperationRiskLevel, mode: SafetyMode) -> bool:
        """Check if an operation is allowed based on its risk level and the current safety mode.

        Args:
            risk_level: The risk level of the operation
            mode: The current safety mode

        Returns:
            True if the operation is allowed, False otherwise
        """
        # LOW risk operations are always allowed
        if risk_level == OperationRiskLevel.LOW:
            return True

        # MEDIUM risk operations are allowed only in UNSAFE mode
        if risk_level == OperationRiskLevel.MEDIUM:
            return mode == SafetyMode.UNSAFE

        # HIGH risk operations are allowed only in UNSAFE mode with confirmation
        if risk_level == OperationRiskLevel.HIGH:
            return mode == SafetyMode.UNSAFE

        # EXTREME risk operations are never allowed
        return False

    def needs_confirmation(self, risk_level: OperationRiskLevel) -> bool:
        """Check if an operation needs confirmation based on its risk level.

        Args:
            risk_level: The risk level of the operation

        Returns:
            True if the operation needs confirmation, False otherwise
        """
        # Only HIGH and EXTREME risk operations require confirmation
        return risk_level >= OperationRiskLevel.HIGH


# ========
# API Safety Config
# ========


class HTTPMethod(str, Enum):
    """HTTP methods used in API operations."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class APISafetyConfig(SafetyConfigBase[tuple[str, str, dict[str, Any], dict[str, Any], dict[str, Any]]]):
    """Safety configuration for API operations.

    The operation type is a tuple of (method, path).
    """

    # Maps risk levels to operations (method + path patterns)
    PATH_SAFETY_CONFIG = {
        OperationRiskLevel.EXTREME: {
            HTTPMethod.DELETE: [
                "/v1/projects/{ref}",  # Delete project.  Irreversible, complete data loss.
            ]
        },
        OperationRiskLevel.HIGH: {
            HTTPMethod.DELETE: [
                "/v1/projects/{ref}/branches/{branch_id}",  # Delete a database branch.  Data loss on branch.
                "/v1/projects/{ref}/branches",  # Disables preview branching. Disruptive to development workflows.
                "/v1/projects/{ref}/custom-hostname",  # Deletes custom hostname config.  Can break production access.
                "/v1/projects/{ref}/vanity-subdomain",  # Deletes vanity subdomain config.  Breaks vanity URL access.
                "/v1/projects/{ref}/network-bans",  # Remove network bans (can expose database to wider network).
                "/v1/projects/{ref}/secrets",  # Bulk delete secrets. Can break application functionality if critical secrets are removed.
                "/v1/projects/{ref}/functions/{function_slug}",  # Delete function.  Breaks functionality relying on the function.
                "/v1/projects/{ref}/api-keys/{id}",  # Delete api key.  Can break API access.
                "/v1/projects/{ref}/config/auth/sso/providers/{provider_id}",  # Delete SSO Provider.  Breaks SSO login.
                "/v1/projects/{ref}/config/auth/signing-keys/{id}",  # Delete signing key. Can break JWT verification.
            ],
            HTTPMethod.POST: [
                "/v1/projects/{ref}/pause",  # Pause project - Impacts production, database becomes unavailable.
                "/v1/projects/{ref}/restore",  # Restore project - Can overwrite existing data with backup.
                "/v1/projects/{ref}/upgrade",  # Upgrades the project's Postgres version - potential downtime/compatibility issues.
                "/v1/projects/{ref}/read-replicas/remove",  # Remove a read replica.  Can impact read scalability.
                "/v1/projects/{ref}/restore/cancel",  # Cancels the given project restoration. Can leave project in inconsistent state.
                "/v1/projects/{ref}/readonly/temporary-disable",  # Disables readonly mode. Allows potentially destructive operations.
            ],
        },
        OperationRiskLevel.MEDIUM: {
            HTTPMethod.POST: [
                "/v1/projects",  # Create project.  Significant infrastructure change.
                "/v1/organizations",  # Create org. Significant infrastructure change.
                "/v1/projects/{ref}/branches",  # Create a database branch.  Could potentially impact production if misused.
                "/v1/projects/{ref}/branches/{branch_id}/push",  # Push a database branch.  Could overwrite production data if pushed to the wrong branch.
                "/v1/projects/{ref}/branches/{branch_id}/reset",  # Reset a database branch. Data loss on the branch.
                "/v1/projects/{ref}/custom-hostname/initialize",  # Updates custom hostname configuration, potentially breaking existing config.
                "/v1/projects/{ref}/custom-hostname/reverify",  # Attempts to verify DNS configuration.  Could disrupt custom hostname if misconfigured.
                "/v1/projects/{ref}/custom-hostname/activate",  # Activates custom hostname. Could lead to downtime during switchover.
                "/v1/projects/{ref}/network-bans/retrieve",  # Gets project's network bans. Information disclosure, though less risky than removing bans.
                "/v1/projects/{ref}/network-restrictions/apply",  # Updates project's network restrictions. Could block legitimate access if misconfigured.
                "/v1/projects/{ref}/secrets",  # Bulk create secrets.  Could overwrite existing secrets if names collide.
                "/v1/projects/{ref}/upgrade/status",  # get status for upgrade
                "/v1/projects/{ref}/database/webhooks/enable",  # Enables Database Webhooks.  Could expose data if webhooks are misconfigured.
                "/v1/projects/{ref}/functions",  # Create a function (deprecated).
                "/v1/projects/{ref}/functions/deploy",  # Deploy a function. Could break functionality if deployed code has errors.
                "/v1/projects/{ref}/config/auth/sso/providers",  # Create SSO provider.  Could impact authentication if misconfigured.
                "/v1/projects/{ref}/database/backups/restore-pitr",  # Restore a PITR backup.  Can overwrite data.
                "/v1/projects/{ref}/read-replicas/setup",  # Setup a read replica
                "/v1/projects/{ref}/database/query",  # Run SQL query.  *Crucially*, this allows arbitrary SQL, including `DROP TABLE`, `DELETE`, etc.
                "/v1/projects/{ref}/config/auth/signing-keys",  # Create a new signing key, requires key rotation.
                "/v1/oauth/token",  # Exchange auth code for user's access token. Security-sensitive.
                "/v1/oauth/revoke",  # Revoke oauth app authorization.  Can break application access.
                "/v1/projects/{ref}/api-keys",  # Create an API key
            ],
            HTTPMethod.PATCH: [
                "/v1/projects/{ref}/config/auth",  # Auth config.  Could lock users out or introduce vulnerabilities if misconfigured.
                "/v1/projects/{ref}/config/database/pooler",  # Connection pooling changes.  Can impact database performance.
                "/v1/projects/{ref}/postgrest",  # Update Postgrest config.  Can impact API behavior.
                "/v1/projects/{ref}/functions/{function_slug}",  # Updates a function.  Can break functionality.
                "/v1/projects/{ref}/config/storage",  # Update Storage config.  Can change file size limits, etc.
                "/v1/branches/{branch_id}",  # Update database branch config.
                "/v1/projects/{ref}/api-keys/{id}",  # Updates a API key
                "/v1/projects/{ref}/config/auth/signing-keys/{id}",  # updates signing key.
            ],
            HTTPMethod.PUT: [
                "/v1/projects/{ref}/config/database/postgres",  # Postgres config changes.  Can significantly impact database performance/behavior.
                "/v1/projects/{ref}/pgsodium",  # Update pgsodium config.  *Critical*: Updating the `root_key` can cause data loss.
                "/v1/projects/{ref}/ssl-enforcement",  # Update SSL enforcement config.  Could break access if misconfigured.
                "/v1/projects/{ref}/functions",  # Bulk update Edge Functions. Could break multiple functions at once.
                "/v1/projects/{ref}/config/auth/sso/providers/{provider_id}",  # Update sso provider.
            ],
        },
    }

    def get_risk_level(
        self, operation: tuple[str, str, dict[str, Any], dict[str, Any], dict[str, Any]]
    ) -> OperationRiskLevel:
        """Get the risk level for an API operation.

        Args:
            operation: Tuple of (method, path)

        Returns:
            The risk level for the operation
        """
        method, path, _, _, _ = operation

        # Check each risk level from highest to lowest
        for risk_level in sorted(self.PATH_SAFETY_CONFIG.keys(), reverse=True):
            if self._path_matches_risk_level(method, path, risk_level):
                return risk_level

        # Default to low risk
        return OperationRiskLevel.LOW

    def _path_matches_risk_level(self, method: str, path: str, risk_level: OperationRiskLevel) -> bool:
        """Check if the method and path match any pattern for the given risk level."""
        patterns = self.PATH_SAFETY_CONFIG.get(risk_level, {})

        if method not in patterns:
            return False

        for pattern in patterns[method]:
            # Convert placeholder pattern to regex
            regex_pattern = self._convert_pattern_to_regex(pattern)
            if re.match(regex_pattern, path):
                return True

        return False

    def _convert_pattern_to_regex(self, pattern: str) -> str:
        """Convert a placeholder pattern to a regex pattern.

        Replaces placeholders like {ref} with regex patterns for matching.
        """
        # Replace common placeholders with regex patterns
        regex_pattern = pattern
        regex_pattern = regex_pattern.replace("{ref}", r"[^/]+")
        regex_pattern = regex_pattern.replace("{id}", r"[^/]+")
        regex_pattern = regex_pattern.replace("{slug}", r"[^/]+")
        regex_pattern = regex_pattern.replace("{table}", r"[^/]+")
        regex_pattern = regex_pattern.replace("{branch_id}", r"[^/]+")
        regex_pattern = regex_pattern.replace("{function_slug}", r"[^/]+")

        # Add end anchor to ensure full path matching
        if not regex_pattern.endswith("$"):
            regex_pattern += "$"

        return regex_pattern


# ========
# SQL Safety Config
# ========


class SQLSafetyConfig(SafetyConfigBase[QueryValidationResults]):
    """Safety configuration for SQL operations."""

    STATEMENT_CONFIG = {
        # DQL - all LOW risk, no migrations
        "SelectStmt": {
            "category": SQLQueryCategory.DQL,
            "risk_level": OperationRiskLevel.LOW,
            "needs_migration": False,
        },
        "ExplainStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.LOW,
            "needs_migration": False,
        },
        # DML - all MEDIUM risk, no migrations
        "InsertStmt": {
            "category": SQLQueryCategory.DML,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": False,
        },
        "UpdateStmt": {
            "category": SQLQueryCategory.DML,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": False,
        },
        "DeleteStmt": {
            "category": SQLQueryCategory.DML,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": False,
        },
        "MergeStmt": {
            "category": SQLQueryCategory.DML,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": False,
        },
        # DDL - mix of MEDIUM and HIGH risk, need migrations
        "CreateStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateTableAsStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateSchemaStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateExtensionStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "AlterTableStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "AlterDomainStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateFunctionStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "IndexStmt": {  # CREATE INDEX
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateTrigStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "ViewStmt": {  # CREATE VIEW
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CommentStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        # Additional DDL statements
        "CreateEnumStmt": {  # CREATE TYPE ... AS ENUM
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateTypeStmt": {  # CREATE TYPE (composite)
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateDomainStmt": {  # CREATE DOMAIN
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateSeqStmt": {  # CREATE SEQUENCE
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateForeignTableStmt": {  # CREATE FOREIGN TABLE
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreatePolicyStmt": {  # CREATE POLICY
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateCastStmt": {  # CREATE CAST
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateOpClassStmt": {  # CREATE OPERATOR CLASS
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateOpFamilyStmt": {  # CREATE OPERATOR FAMILY
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "AlterEnumStmt": {  # ALTER TYPE ... ADD VALUE
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "AlterSeqStmt": {  # ALTER SEQUENCE
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "AlterOwnerStmt": {  # ALTER ... OWNER TO
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "AlterObjectSchemaStmt": {  # ALTER ... SET SCHEMA
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "RenameStmt": {  # RENAME operations
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        # DESTRUCTIVE DDL - HIGH risk, need migrations and confirmation
        "DropStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.HIGH,
            "needs_migration": True,
        },
        "TruncateStmt": {
            "category": SQLQueryCategory.DDL,
            "risk_level": OperationRiskLevel.HIGH,
            "needs_migration": True,
        },
        # DCL - MEDIUM risk, need migrations
        "GrantStmt": {
            "category": SQLQueryCategory.DCL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "GrantRoleStmt": {
            "category": SQLQueryCategory.DCL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "RevokeStmt": {
            "category": SQLQueryCategory.DCL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "RevokeRoleStmt": {
            "category": SQLQueryCategory.DCL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "CreateRoleStmt": {
            "category": SQLQueryCategory.DCL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "AlterRoleStmt": {
            "category": SQLQueryCategory.DCL,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": True,
        },
        "DropRoleStmt": {
            "category": SQLQueryCategory.DCL,
            "risk_level": OperationRiskLevel.HIGH,
            "needs_migration": True,
        },
        # TCL - LOW risk, no migrations
        "TransactionStmt": {
            "category": SQLQueryCategory.TCL,
            "risk_level": OperationRiskLevel.LOW,
            "needs_migration": False,
        },
        # PostgreSQL-specific
        "VacuumStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": False,
        },
        "AnalyzeStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.LOW,
            "needs_migration": False,
        },
        "ClusterStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": False,
        },
        "CheckPointStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": False,
        },
        "PrepareStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.LOW,
            "needs_migration": False,
        },
        "ExecuteStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.MEDIUM,  # Could be LOW or MEDIUM based on prepared statement
            "needs_migration": False,
        },
        "DeallocateStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.LOW,
            "needs_migration": False,
        },
        "ListenStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.LOW,
            "needs_migration": False,
        },
        "NotifyStmt": {
            "category": SQLQueryCategory.POSTGRES_SPECIFIC,
            "risk_level": OperationRiskLevel.MEDIUM,
            "needs_migration": False,
        },
    }

    def classify_statement(self, stmt_type: str, stmt_node: Any) -> dict[str, Any]:
        """Get classification rules for a given statement type from our config."""
        config = self.STATEMENT_CONFIG.get(
            stmt_type,
            # if not found - default to MEDIUM risk
            {
                "category": SQLQueryCategory.OTHER,
                "risk_level": OperationRiskLevel.MEDIUM,  # Default to MEDIUM risk for unknown
                "needs_migration": False,
            },
        )

        # Special case: CopyStmt can be read or write
        if stmt_type == "CopyStmt" and stmt_node:
            # Check if it's COPY TO (read) or COPY FROM (write)
            if hasattr(stmt_node, "is_from") and not stmt_node.is_from:
                # COPY TO - it's a read operation (LOW risk)
                config["category"] = SQLQueryCategory.DQL
                config["risk_level"] = OperationRiskLevel.LOW
            else:
                # COPY FROM - it's a write operation (MEDIUM risk)
                config["category"] = SQLQueryCategory.DML
                config["risk_level"] = OperationRiskLevel.MEDIUM

        # Other special cases can be added here

        return config

    def get_risk_level(self, operation: QueryValidationResults) -> OperationRiskLevel:
        """Get the risk level for an SQL batch operation.

        Args:
            operation: The SQL batch validation result to check

        Returns:
            The highest risk level found in the batch
        """
        # Simply return the highest risk level that's already tracked in the batch
        return operation.highest_risk_level


# ========
# Meta Safety Config
# ========

# Operation name → risk level mapping for Meta Marketing API tools
_META_RISK_MAP: dict[str, OperationRiskLevel] = {
    # Read-only — always allowed
    "meta_get_account_info": OperationRiskLevel.LOW,
    "meta_list_campaigns": OperationRiskLevel.LOW,
    "meta_get_campaign": OperationRiskLevel.LOW,
    "meta_list_adsets": OperationRiskLevel.LOW,
    "meta_get_adset": OperationRiskLevel.LOW,
    "meta_list_ads": OperationRiskLevel.LOW,
    "meta_get_ad": OperationRiskLevel.LOW,
    "meta_get_account_insights": OperationRiskLevel.LOW,
    "meta_get_campaign_insights": OperationRiskLevel.LOW,
    "meta_get_adset_insights": OperationRiskLevel.LOW,
    "meta_get_ad_insights": OperationRiskLevel.LOW,
    "meta_list_creatives": OperationRiskLevel.LOW,
    "meta_exchange_token": OperationRiskLevel.LOW,
    # Write / reversible — require UNSAFE mode
    "meta_create_campaign": OperationRiskLevel.MEDIUM,
    "meta_update_campaign": OperationRiskLevel.MEDIUM,
    "meta_toggle_campaign": OperationRiskLevel.MEDIUM,
    "meta_create_adset": OperationRiskLevel.MEDIUM,
    "meta_update_adset": OperationRiskLevel.MEDIUM,
    "meta_create_ad": OperationRiskLevel.MEDIUM,
    "meta_update_ad": OperationRiskLevel.MEDIUM,
    "meta_create_creative": OperationRiskLevel.MEDIUM,
    # Destructive / irreversible — require UNSAFE mode + confirmation
    "meta_delete_campaign": OperationRiskLevel.HIGH,
    "meta_delete_adset": OperationRiskLevel.HIGH,
    "meta_delete_ad": OperationRiskLevel.HIGH,
}


class MetaSafetyConfig(SafetyConfigBase[Any]):
    """Safety configuration for Meta Marketing API operations.

    The operation value can be a plain tool-name string, or a
    ``(tool_name, kwargs)`` tuple when args must survive the confirmation
    round-trip (used for delete operations).
    """

    def get_risk_level(self, operation: Any) -> OperationRiskLevel:
        tool_name = operation[0] if isinstance(operation, tuple) else operation
        return _META_RISK_MAP.get(tool_name, OperationRiskLevel.MEDIUM)
