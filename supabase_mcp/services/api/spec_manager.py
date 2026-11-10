import json
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from supabase_mcp.logger import logger

# Constants
SPEC_URL = "https://api.supabase.com/api/v1-json"
LOCAL_SPEC_PATH = Path(__file__).parent / "specs" / "api_spec.json"


class ApiDomain(str, Enum):
    """Enum of all possible domains in the Supabase Management API."""

    ANALYTICS = "Analytics"
    AUTH = "Auth"
    DATABASE = "Database"
    DOMAINS = "Domains"
    EDGE_FUNCTIONS = "Edge Functions"
    ENVIRONMENTS = "Environments"
    OAUTH = "OAuth"
    ORGANIZATIONS = "Organizations"
    PROJECTS = "Projects"
    REST = "Rest"
    SECRETS = "Secrets"
    STORAGE = "Storage"

    @classmethod
    def list(cls) -> list[str]:
        """Return a list of all domain values."""
        return [domain.value for domain in cls]


class ApiSpecManager:
    """
    Manages the OpenAPI specification for the Supabase Management API.
    Handles spec loading, caching, and validation.
    """

    def __init__(self) -> None:
        self.spec: dict[str, Any] | None = None
        self._paths_cache: dict[str, dict[str, str]] | None = None
        self._domains_cache: list[str] | None = None

    async def _fetch_remote_spec(self) -> dict[str, Any] | None:
        """
        Fetch latest OpenAPI spec from Supabase API.
        Returns None if fetch fails.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(SPEC_URL)
                if response.status_code == 200:
                    return response.json()
                logger.warning(f"Failed to fetch API spec: {response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Error fetching API spec: {e}")
            return None

    def _load_local_spec(self) -> dict[str, Any]:
        """
        Load OpenAPI spec from local file.
        This is our fallback spec shipped with the server.
        """
        try:
            with open(LOCAL_SPEC_PATH) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Local spec not found at {LOCAL_SPEC_PATH}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in local spec: {e}")
            raise

    async def get_spec(self) -> dict[str, Any]:
        """Retrieve the enriched spec."""
        if self.spec is None:
            raw_spec = await self._fetch_remote_spec()
            if not raw_spec:
                # If remote fetch fails, use our fallback spec
                logger.info("Using fallback API spec")
                raw_spec = self._load_local_spec()
            self.spec = raw_spec

        return self.spec

    def get_all_paths_and_methods(self) -> dict[str, dict[str, str]]:
        """
        Returns a dictionary of all paths and their methods with operation IDs.

        Returns:
            Dict[str, Dict[str, str]]:  {path: {method: operationId}}
        """
        if self._paths_cache is None:
            self._build_caches()
        return self._paths_cache or {}

    def get_paths_and_methods_by_domain(self, domain: str) -> dict[str, dict[str, str]]:
        """
        Returns paths and methods within a specific domain (tag).

        Args:
            domain (str): The domain name (e.g., "Auth", "Projects").

        Returns:
            Dict[str, Dict[str, str]]: {path: {method: operationId}}
        """

        if self._paths_cache is None:
            self._build_caches()

        # Validate domain using enum
        try:
            valid_domain = ApiDomain(domain).value
        except ValueError as e:
            raise ValueError(f"Invalid domain: {domain}") from e

        domain_paths: dict[str, dict[str, str]] = {}
        if self.spec:
            for path, methods in self.spec.get("paths", {}).items():
                for method, details in methods.items():
                    if valid_domain in details.get("tags", []):
                        if path not in domain_paths:
                            domain_paths[path] = {}
                        domain_paths[path][method] = details.get("operationId", "")
        return domain_paths

    def get_all_domains(self) -> list[str]:
        """
        Returns a list of all available domains (tags).

        Returns:
            List[str]:  List of domain names.
        """
        if self._domains_cache is None:
            self._build_caches()
        return self._domains_cache or []

    def get_spec_for_path_and_method(self, path: str, method: str) -> dict[str, Any] | None:
        """
        Returns the full specification for a given path and HTTP method.

        Args:
            path (str): The API path (e.g., "/v1/projects").
            method (str): The HTTP method (e.g., "get", "post").

        Returns:
            Optional[Dict[str, Any]]: The full spec for the operation, or None if not found.
        """
        if self.spec is None:
            return None

        path_spec = self.spec.get("paths", {}).get(path)
        if path_spec:
            return path_spec.get(method.lower())  # Ensure lowercase method
        return None

    def get_spec_part(self, part: str, *args: str | int) -> Any:
        """
        Safely retrieves a nested part of the OpenAPI spec.

        Args:
            part: The top-level key (e.g., 'paths', 'components').
            *args:  Subsequent keys or indices to traverse the spec.

        Returns:
            The value at the specified location in the spec, or None if not found.
        """
        if self.spec is None:
            return None

        current = self.spec.get(part)
        for key in args:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
                current = current[key]
            else:
                return None  # Key not found or invalid index
        return current

    def _build_caches(self) -> None:
        """
        Build internal caches for faster lookups.
        This populates _paths_cache and _domains_cache.
        """
        if self.spec is None:
            logger.error("Cannot build caches: OpenAPI spec not loaded")
            return

        # Build paths cache
        paths_cache: dict[str, dict[str, str]] = {}
        domains_set = set()

        for path, methods in self.spec.get("paths", {}).items():
            for method, details in methods.items():
                # Add to paths cache
                if path not in paths_cache:
                    paths_cache[path] = {}
                paths_cache[path][method] = details.get("operationId", "")

                # Collect domains (tags)
                for tag in details.get("tags", []):
                    domains_set.add(tag)

        self._paths_cache = paths_cache
        self._domains_cache = sorted(domains_set)


# Example usage (assuming you have an instance of ApiSpecManager called 'spec_manager'):
async def main() -> None:
    """Test function to demonstrate ApiSpecManager functionality."""
    # Create a new instance of ApiSpecManager
    spec_manager = ApiSpecManager()

    # Load the spec
    await spec_manager.get_spec()

    # Print the path to help debug
    print(f"Looking for spec at: {LOCAL_SPEC_PATH}")

    # 1. Get all domains
    all_domains = spec_manager.get_all_domains()
    print("\nAll Domains:")
    print(all_domains)

    # 2. Get all paths and methods
    all_paths = spec_manager.get_all_paths_and_methods()
    print("\nAll Paths and Methods (sample):")
    # Just print a few to avoid overwhelming output
    for i, (path, methods) in enumerate(all_paths.items()):
        if i >= 5:  # Limit to 5 paths
            break
        print(f"  {path}:")
        for method, operation_id in methods.items():
            print(f"    {method}: {operation_id}")

    # 3. Get paths and methods for the "Edge Functions" domain
    edge_paths = spec_manager.get_paths_and_methods_by_domain("Edge Functions")
    print("\nEdge Functions Paths and Methods:")
    for path, methods in edge_paths.items():
        print(f"  {path}:")
        for method, operation_id in methods.items():
            print(f"    {method}: {operation_id}")

    # 4. Get the full spec for a specific path and method
    path = "/v1/projects/{ref}/functions"
    method = "GET"
    full_spec = spec_manager.get_spec_for_path_and_method(path, method)
    print(f"\nFull Spec for {method} {path}:")
    if full_spec:
        print(json.dumps(full_spec, indent=2)[:500] + "...")  # Truncate for readability
    else:
        print("Spec not found for this path/method")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
