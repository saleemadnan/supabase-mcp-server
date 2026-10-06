import json
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import httpx
import pytest

from supabase_mcp.services.api.spec_manager import ApiSpecManager

# Test data
SAMPLE_SPEC = {"openapi": "3.0.0", "paths": {"/v1/test": {"get": {"operationId": "test"}}}}


class TestApiSpecManager:
    """Integration tests for api spec manager tools."""

    # Local Spec Tests
    def test_load_local_spec_success(self, spec_manager_integration: ApiSpecManager):
        """Test successful loading of local spec file"""
        mock_file = mock_open(read_data=json.dumps(SAMPLE_SPEC))

        with patch("builtins.open", mock_file):
            result = spec_manager_integration._load_local_spec()

        assert result == SAMPLE_SPEC
        mock_file.assert_called_once()

    def test_load_local_spec_file_not_found(self, spec_manager_integration: ApiSpecManager):
        """Test handling of missing local spec file"""
        with patch("builtins.open", side_effect=FileNotFoundError), pytest.raises(FileNotFoundError):
            spec_manager_integration._load_local_spec()

    def test_load_local_spec_invalid_json(self, spec_manager_integration: ApiSpecManager):
        """Test handling of invalid JSON in local spec"""
        mock_file = mock_open(read_data="invalid json")

        with patch("builtins.open", mock_file), pytest.raises(json.JSONDecodeError):
            spec_manager_integration._load_local_spec()

    # Remote Spec Tests
    @pytest.mark.asyncio
    async def test_fetch_remote_spec_success(self, spec_manager_integration: ApiSpecManager):
        """Test successful remote spec fetch"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_SPEC

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client  # Mock async context manager

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await spec_manager_integration._fetch_remote_spec()

        assert result == SAMPLE_SPEC
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_remote_spec_api_error(self, spec_manager_integration: ApiSpecManager):
        """Test handling of API error during remote fetch"""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client  # Mock async context manager

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await spec_manager_integration._fetch_remote_spec()

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_remote_spec_network_error(self, spec_manager_integration: ApiSpecManager):
        """Test handling of network error during remote fetch"""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.NetworkError("Network error")

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await spec_manager_integration._fetch_remote_spec()

        assert result is None

    # Startup Flow Tests
    @pytest.mark.asyncio
    async def test_startup_remote_success(self, spec_manager_integration: ApiSpecManager):
        """Test successful startup with remote fetch"""
        # Reset spec to None to ensure we're testing the fetch
        spec_manager_integration.spec = None

        # Mock the fetch method to return sample spec
        mock_fetch = AsyncMock(return_value=SAMPLE_SPEC)

        with patch.object(spec_manager_integration, "_fetch_remote_spec", mock_fetch):
            result = await spec_manager_integration.get_spec()

        assert result == SAMPLE_SPEC
        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_spec_remote_fail_local_fallback(self, spec_manager_integration: ApiSpecManager):
        """Test get_spec with remote failure and local fallback"""
        # Reset spec to None to ensure we're testing the fetch and fallback
        spec_manager_integration.spec = None

        # Mock fetch to fail and local to succeed
        mock_fetch = AsyncMock(return_value=None)
        mock_local = MagicMock(return_value=SAMPLE_SPEC)

        with (
            patch.object(spec_manager_integration, "_fetch_remote_spec", mock_fetch),
            patch.object(spec_manager_integration, "_load_local_spec", mock_local),
        ):
            result = await spec_manager_integration.get_spec()

        assert result == SAMPLE_SPEC
        mock_fetch.assert_called_once()
        mock_local.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_spec_both_fail(self, spec_manager_integration: ApiSpecManager):
        """Test get_spec with both remote and local failure"""
        # Reset spec to None to ensure we're testing the fetch and fallback
        spec_manager_integration.spec = None

        # Mock both fetch and local to fail
        mock_fetch = AsyncMock(return_value=None)
        mock_local = MagicMock(side_effect=FileNotFoundError("Test file not found"))

        with (
            patch.object(spec_manager_integration, "_fetch_remote_spec", mock_fetch),
            patch.object(spec_manager_integration, "_load_local_spec", mock_local),
            pytest.raises(FileNotFoundError),
        ):
            await spec_manager_integration.get_spec()

        mock_fetch.assert_called_once()
        mock_local.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_spec_cached(self, spec_manager_integration: ApiSpecManager):
        """Test that get_spec returns cached spec if available"""
        # Set the spec directly
        spec_manager_integration.spec = SAMPLE_SPEC

        # Mock the fetch method to verify it's not called
        mock_fetch = AsyncMock()

        with patch.object(spec_manager_integration, "_fetch_remote_spec", mock_fetch):
            result = await spec_manager_integration.get_spec()

        assert result == SAMPLE_SPEC
        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_spec_not_loaded(self, spec_manager_integration: ApiSpecManager):
        """Test behavior when spec is not loaded but can be loaded"""
        # Reset spec to None
        spec_manager_integration.spec = None

        # Mock fetch to succeed
        mock_fetch = AsyncMock(return_value=SAMPLE_SPEC)

        with patch.object(spec_manager_integration, "_fetch_remote_spec", mock_fetch):
            result = await spec_manager_integration.get_spec()

        assert result == SAMPLE_SPEC
        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_comprehensive_spec_retrieval(self, spec_manager_integration: ApiSpecManager):
        """
        Comprehensive test of API spec retrieval and functionality.
        This test exactly mirrors the main() function to ensure all aspects work correctly.
        """
        # Create a fresh instance to avoid any cached data from other tests
        from supabase_mcp.services.api.spec_manager import LOCAL_SPEC_PATH, ApiSpecManager

        spec_manager = ApiSpecManager()

        # Print the path being used (for debugging)
        print(f"\nTest is looking for spec at: {LOCAL_SPEC_PATH}")

        # Load the bundled spec rather than the live one at SPEC_URL: the live spec
        # changes upstream (e.g. schemas get renamed), which would make this test
        # depend on network access and on Supabase's current API surface.
        with patch.object(spec_manager, "_fetch_remote_spec", AsyncMock(return_value=None)):
            spec = await spec_manager.get_spec()
        assert spec is not None, "Spec should be loaded successfully"

        # 1. Test get_all_domains
        all_domains = spec_manager.get_all_domains()
        print(f"\nAll domains: {all_domains}")
        assert len(all_domains) > 0, "Should have at least one domain"

        # Verify all expected domains are present
        expected_domains = [
            "Analytics",
            "Auth",
            "Database",
            "Domains",
            "Edge Functions",
            "Environments",
            "OAuth",
            "Organizations",
            "Projects",
            "Rest",
            "Secrets",
            "Storage",
        ]
        for domain in expected_domains:
            assert domain in all_domains, f"Domain '{domain}' should be in the list of domains"

        # 2. Test get_all_paths_and_methods
        all_paths = spec_manager.get_all_paths_and_methods()
        assert len(all_paths) > 0, "Should have at least one path"

        # Sample a few paths to verify
        sample_paths = list(all_paths.keys())[:5]
        print("\nSample paths:")
        for path in sample_paths:
            print(f"  {path}:")
            assert path.startswith("/v1/"), f"Path {path} should start with /v1/"
            assert len(all_paths[path]) > 0, f"Path {path} should have at least one method"
            for method, operation_id in all_paths[path].items():
                print(f"    {method}: {operation_id}")
                assert method.lower() in ["get", "post", "put", "patch", "delete"], f"Method {method} should be valid"
                assert operation_id.startswith("v1-"), f"Operation ID {operation_id} should start with v1-"

        # 3. Test get_paths_and_methods_by_domain for each domain
        for domain in expected_domains:
            domain_paths = spec_manager.get_paths_and_methods_by_domain(domain)
            assert len(domain_paths) > 0, f"Domain {domain} should have at least one path"
            print(f"\n{domain} domain has {len(domain_paths)} paths")

        # 4. Test Edge Functions domain specifically
        edge_paths = spec_manager.get_paths_and_methods_by_domain("Edge Functions")
        print("\nEdge Functions Paths and Methods:")
        for path in edge_paths:
            print(f"  {path}")
            for method, operation_id in edge_paths[path].items():
                print(f"    {method}: {operation_id}")

        # Verify specific Edge Functions paths exist
        expected_edge_paths = [
            "/v1/projects/{ref}/functions",
            "/v1/projects/{ref}/functions/{function_slug}",
            "/v1/projects/{ref}/functions/deploy",
        ]
        for path in expected_edge_paths:
            assert path in edge_paths, f"Expected path {path} should be in Edge Functions domain"

        # 5. Test get_spec_for_path_and_method
        # Test for Edge Functions
        path = "/v1/projects/{ref}/functions"
        method = "GET"
        full_spec = spec_manager.get_spec_for_path_and_method(path, method)
        assert full_spec is not None, f"Should find spec for {method} {path}"
        assert "operationId" in full_spec, "Spec should include operationId"
        assert full_spec["operationId"] == "v1-list-all-functions", "Should have correct operationId"

        # Test for another domain (Auth)
        auth_path = "/v1/projects/{ref}/config/auth"
        auth_method = "GET"
        auth_spec = spec_manager.get_spec_for_path_and_method(auth_path, auth_method)
        assert auth_spec is not None, f"Should find spec for {auth_method} {auth_path}"
        assert "operationId" in auth_spec, "Auth spec should include operationId"

        # 6. Test get_spec_part
        # Get a specific schema
        schema = spec_manager.get_spec_part("components", "schemas", "FunctionResponse")
        assert schema is not None, "Should find FunctionResponse schema"
        assert "properties" in schema, "Schema should have properties"

        # 7. Test caching behavior
        # Call get_spec again - should use cached version
        import time

        start_time = time.time()
        await spec_manager.get_spec()
        end_time = time.time()
        assert (end_time - start_time) < 0.1, "Cached spec retrieval should be fast"
