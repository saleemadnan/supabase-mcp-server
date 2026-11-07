"""Unit tests for FeatureManager.check_feature_access error mapping."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from supabase_mcp.clients.api_client import FeatureAccessResponse
from supabase_mcp.core.feature_manager import FeatureManager
from supabase_mcp.exceptions import APIConnectionError, FeatureAccessError, FeatureTemporaryError


def _feature_manager(**check_feature_access_kwargs: Any) -> FeatureManager:
    api_client = AsyncMock()
    api_client.check_feature_access = AsyncMock(**check_feature_access_kwargs)
    return FeatureManager(api_client=api_client)


@pytest.mark.unit
class TestCheckFeatureAccess:
    async def test_granted_access_returns_normally(self):
        manager = _feature_manager(return_value=FeatureAccessResponse(access_granted=True))

        await manager.check_feature_access("retrieve_logs")

    async def test_denied_access_raises_the_pro_plan_error_not_a_temporary_one(self):
        manager = _feature_manager(return_value=FeatureAccessResponse(access_granted=False))

        with pytest.raises(FeatureAccessError) as exc_info:
            await manager.check_feature_access("retrieve_logs")

        assert not isinstance(exc_info.value, FeatureTemporaryError)
        assert "Pro plan" in str(exc_info.value)
        assert "couldn't verify access" not in str(exc_info.value)

    async def test_feature_access_error_from_the_client_propagates_unchanged(self):
        denial = FeatureAccessError("retrieve_logs", status_code=403)
        manager = _feature_manager(side_effect=denial)

        with pytest.raises(FeatureAccessError) as exc_info:
            await manager.check_feature_access("retrieve_logs")

        assert exc_info.value is denial

    async def test_api_error_is_reported_as_temporary(self):
        manager = _feature_manager(side_effect=APIConnectionError("timeout", status_code=503))

        with pytest.raises(FeatureTemporaryError) as exc_info:
            await manager.check_feature_access("retrieve_logs")

        assert exc_info.value.status_code == 503
        assert "couldn't verify access to 'retrieve_logs'" in str(exc_info.value)

    async def test_unexpected_error_is_reported_as_temporary(self):
        manager = _feature_manager(side_effect=RuntimeError("boom"))

        with pytest.raises(FeatureTemporaryError):
            await manager.check_feature_access("retrieve_logs")
