"""Meta Marketing API HTTP client."""

from __future__ import annotations

from typing import Any

import httpx

from supabase_mcp.clients.base_http_client import AsyncHTTPClient
from supabase_mcp.exceptions import APIClientError, APIConnectionError
from supabase_mcp.logger import logger

META_GRAPH_API_BASE = "https://graph.facebook.com"


class MetaAdsClient(AsyncHTTPClient):
    """HTTP client for the Meta Marketing (Graph) API."""

    _instance: MetaAdsClient | None = None

    def __init__(
        self,
        access_token: str,
        app_id: str,
        app_secret: str,
        api_version: str = "v21.0",
        timeout: float = 30.0,
    ) -> None:
        self._access_token = access_token
        self._app_id = app_id
        self._app_secret = app_secret
        self._api_version = api_version
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def get_instance(
        cls,
        access_token: str,
        app_id: str,
        app_secret: str,
        api_version: str = "v21.0",
        timeout: float = 30.0,
    ) -> MetaAdsClient:
        if cls._instance is None:
            cls._instance = cls(access_token, app_id, app_secret, api_version=api_version, timeout=timeout)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{META_GRAPH_API_BASE}/{self._api_version}",
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    def _inject_token(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Inject access_token into query parameters."""
        base = dict(params) if params else {}
        base["access_token"] = self._access_token
        return base

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.execute_request("GET", path, request_params=self._inject_token(params))

    async def post(self, path: str, body: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.execute_request("POST", path, request_params=self._inject_token(params), request_body=body)

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.execute_request("DELETE", path, request_params=self._inject_token(params))

    async def exchange_token(self, short_lived_token: str) -> dict[str, Any]:
        """Exchange a short-lived token for a long-lived token."""
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self._app_id,
            "client_secret": self._app_secret,
            "fb_exchange_token": short_lived_token,
        }
        try:
            client = await self._ensure_client()
            request = self.prepare_request(client, "GET", "/oauth/access_token", request_params=params)
            response = await self.send_request(client, request)
            parsed = self.parse_response(response)
            if not response.is_success:
                self.handle_error_response(response, parsed)
            logger.info("Token exchange successful")
            return parsed
        except (APIClientError, APIConnectionError):
            raise
        except Exception as e:
            raise APIClientError(message="Token exchange failed", status_code=None) from e

    async def get_app_token(self) -> dict[str, Any]:
        """Get an app-level access token."""
        params = {
            "client_id": self._app_id,
            "client_secret": self._app_secret,
            "grant_type": "client_credentials",
        }
        client = await self._ensure_client()
        request = self.prepare_request(client, "GET", "/oauth/access_token", request_params=params)
        response = await self.send_request(client, request)
        parsed = self.parse_response(response)
        if not response.is_success:
            self.handle_error_response(response, parsed)
        return parsed
