"""Meta Ads campaign management service."""

from __future__ import annotations

from typing import Any

from supabase_mcp.clients.meta_ads_client import MetaAdsClient
from supabase_mcp.logger import logger
from supabase_mcp.services.meta_ads.models import (
    CreateAdRequest,
    CreateAdSetRequest,
    CreateCampaignRequest,
    InsightsRequest,
    UpdateCampaignRequest,
)

# Default fields to request for campaign objects
CAMPAIGN_FIELDS = "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time,created_time,updated_time,spend_cap,budget_remaining"
ADSET_FIELDS = "id,name,status,campaign_id,daily_budget,lifetime_budget,billing_event,optimization_goal,bid_amount,start_time,end_time,targeting,created_time,updated_time"
AD_FIELDS = "id,name,status,adset_id,campaign_id,creative,created_time,updated_time"
ACCOUNT_FIELDS = "id,name,account_status,currency,timezone_name,business,spend_cap,amount_spent,balance"


class MetaAdsCampaignManager:
    """Service for managing Meta advertising campaigns via the Marketing API."""

    _instance: MetaAdsCampaignManager | None = None

    def __init__(self, client: MetaAdsClient, ad_account_id: str) -> None:
        self._client = client
        # Ensure the account id has 'act_' prefix
        self._account_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"

    @classmethod
    def get_instance(cls, client: MetaAdsClient, ad_account_id: str) -> MetaAdsCampaignManager:
        if cls._instance is None:
            cls._instance = cls(client, ad_account_id)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ─── Account ────────────────────────────────────────────────────────────────

    async def get_account_info(self) -> dict[str, Any]:
        """Return basic info about the ad account."""
        logger.info(f"Fetching account info for {self._account_id}")
        return await self._client.get(f"/{self._account_id}", params={"fields": ACCOUNT_FIELDS})

    # ─── Campaigns ──────────────────────────────────────────────────────────────

    async def list_campaigns(self, status_filter: str | None = None, limit: int = 25) -> dict[str, Any]:
        """List all campaigns for the ad account."""
        params: dict[str, Any] = {"fields": CAMPAIGN_FIELDS, "limit": limit}
        if status_filter:
            params["effective_status"] = [status_filter]
        logger.info(f"Listing campaigns for {self._account_id}")
        return await self._client.get(f"/{self._account_id}/campaigns", params=params)

    async def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Get details for a specific campaign."""
        logger.info(f"Getting campaign {campaign_id}")
        return await self._client.get(f"/{campaign_id}", params={"fields": CAMPAIGN_FIELDS})

    async def create_campaign(self, request: CreateCampaignRequest) -> dict[str, Any]:
        """Create a new campaign."""
        body: dict[str, Any] = {
            "name": request.name,
            "objective": request.objective.value,
            "status": request.status.value,
            "special_ad_categories": request.special_ad_categories,
        }
        if request.daily_budget is not None:
            body["daily_budget"] = request.daily_budget
        if request.lifetime_budget is not None:
            body["lifetime_budget"] = request.lifetime_budget

        logger.info(f"Creating campaign '{request.name}' for {self._account_id}")
        return await self._client.post(f"/{self._account_id}/campaigns", body=body)

    async def update_campaign(self, campaign_id: str, request: UpdateCampaignRequest) -> dict[str, Any]:
        """Update an existing campaign."""
        body: dict[str, Any] = {}
        if request.name is not None:
            body["name"] = request.name
        if request.status is not None:
            body["status"] = request.status.value
        if request.daily_budget is not None:
            body["daily_budget"] = request.daily_budget
        if request.lifetime_budget is not None:
            body["lifetime_budget"] = request.lifetime_budget

        logger.info(f"Updating campaign {campaign_id}")
        return await self._client.post(f"/{campaign_id}", body=body)

    async def delete_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Delete a campaign."""
        logger.info(f"Deleting campaign {campaign_id}")
        return await self._client.delete(f"/{campaign_id}")

    async def toggle_campaign(self, campaign_id: str, active: bool) -> dict[str, Any]:
        """Pause or activate a campaign."""
        status = "ACTIVE" if active else "PAUSED"
        logger.info(f"Setting campaign {campaign_id} to {status}")
        return await self._client.post(f"/{campaign_id}", body={"status": status})

    # ─── Ad Sets ────────────────────────────────────────────────────────────────

    async def list_adsets(self, campaign_id: str | None = None, limit: int = 25) -> dict[str, Any]:
        """List ad sets, optionally filtered by campaign."""
        params: dict[str, Any] = {"fields": ADSET_FIELDS, "limit": limit}
        if campaign_id:
            logger.info(f"Listing adsets for campaign {campaign_id}")
            return await self._client.get(f"/{campaign_id}/adsets", params=params)
        logger.info(f"Listing all adsets for account {self._account_id}")
        return await self._client.get(f"/{self._account_id}/adsets", params=params)

    async def get_adset(self, adset_id: str) -> dict[str, Any]:
        """Get details for a specific ad set."""
        logger.info(f"Getting adset {adset_id}")
        return await self._client.get(f"/{adset_id}", params={"fields": ADSET_FIELDS})

    async def create_adset(self, request: CreateAdSetRequest) -> dict[str, Any]:
        """Create a new ad set."""
        body: dict[str, Any] = {
            "campaign_id": request.campaign_id,
            "name": request.name,
            "billing_event": request.billing_event.value,
            "optimization_goal": request.optimization_goal.value,
            "status": request.status.value,
            "targeting": request.targeting,
        }
        if request.bid_amount is not None:
            body["bid_amount"] = request.bid_amount
        if request.daily_budget is not None:
            body["daily_budget"] = request.daily_budget
        if request.lifetime_budget is not None:
            body["lifetime_budget"] = request.lifetime_budget
        if request.start_time:
            body["start_time"] = request.start_time
        if request.end_time:
            body["end_time"] = request.end_time

        logger.info(f"Creating adset '{request.name}' under campaign {request.campaign_id}")
        return await self._client.post(f"/{self._account_id}/adsets", body=body)

    async def update_adset(self, adset_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update an ad set with arbitrary field changes."""
        logger.info(f"Updating adset {adset_id}")
        return await self._client.post(f"/{adset_id}", body=updates)

    async def delete_adset(self, adset_id: str) -> dict[str, Any]:
        """Delete an ad set."""
        logger.info(f"Deleting adset {adset_id}")
        return await self._client.delete(f"/{adset_id}")

    # ─── Ads ────────────────────────────────────────────────────────────────────

    async def list_ads(self, adset_id: str | None = None, limit: int = 25) -> dict[str, Any]:
        """List ads, optionally filtered by ad set."""
        params: dict[str, Any] = {"fields": AD_FIELDS, "limit": limit}
        if adset_id:
            logger.info(f"Listing ads for adset {adset_id}")
            return await self._client.get(f"/{adset_id}/ads", params=params)
        logger.info(f"Listing all ads for account {self._account_id}")
        return await self._client.get(f"/{self._account_id}/ads", params=params)

    async def get_ad(self, ad_id: str) -> dict[str, Any]:
        """Get details for a specific ad."""
        logger.info(f"Getting ad {ad_id}")
        return await self._client.get(f"/{ad_id}", params={"fields": AD_FIELDS})

    async def create_ad(self, request: CreateAdRequest) -> dict[str, Any]:
        """Create a new ad."""
        body: dict[str, Any] = {
            "adset_id": request.adset_id,
            "name": request.name,
            "creative": request.creative,
            "status": request.status.value,
        }
        logger.info(f"Creating ad '{request.name}' under adset {request.adset_id}")
        return await self._client.post(f"/{self._account_id}/ads", body=body)

    async def update_ad(self, ad_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update an ad with arbitrary field changes."""
        logger.info(f"Updating ad {ad_id}")
        return await self._client.post(f"/{ad_id}", body=updates)

    async def delete_ad(self, ad_id: str) -> dict[str, Any]:
        """Delete an ad."""
        logger.info(f"Deleting ad {ad_id}")
        return await self._client.delete(f"/{ad_id}")

    # ─── Insights / Analytics ───────────────────────────────────────────────────

    async def get_account_insights(self, request: InsightsRequest) -> dict[str, Any]:
        """Get performance insights for the whole ad account."""
        params = self._build_insights_params(request)
        logger.info(f"Fetching account insights for {self._account_id}")
        return await self._client.get(f"/{self._account_id}/insights", params=params)

    async def get_campaign_insights(self, campaign_id: str, request: InsightsRequest) -> dict[str, Any]:
        """Get performance insights for a specific campaign."""
        params = self._build_insights_params(request)
        logger.info(f"Fetching insights for campaign {campaign_id}")
        return await self._client.get(f"/{campaign_id}/insights", params=params)

    async def get_adset_insights(self, adset_id: str, request: InsightsRequest) -> dict[str, Any]:
        """Get performance insights for a specific ad set."""
        params = self._build_insights_params(request)
        logger.info(f"Fetching insights for adset {adset_id}")
        return await self._client.get(f"/{adset_id}/insights", params=params)

    async def get_ad_insights(self, ad_id: str, request: InsightsRequest) -> dict[str, Any]:
        """Get performance insights for a specific ad."""
        params = self._build_insights_params(request)
        logger.info(f"Fetching insights for ad {ad_id}")
        return await self._client.get(f"/{ad_id}/insights", params=params)

    def _build_insights_params(self, request: InsightsRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "fields": ",".join(request.fields),
            "date_preset": request.date_preset,
        }
        if request.time_increment is not None:
            params["time_increment"] = request.time_increment
        if request.breakdowns:
            params["breakdowns"] = ",".join(request.breakdowns)
        return params

    # ─── Ad Creatives ────────────────────────────────────────────────────────────

    async def list_creatives(self, limit: int = 25) -> dict[str, Any]:
        """List ad creatives for the account."""
        params: dict[str, Any] = {
            "fields": "id,name,title,body,image_url,video_id,object_type,status",
            "limit": limit,
        }
        logger.info(f"Listing creatives for account {self._account_id}")
        return await self._client.get(f"/{self._account_id}/adcreatives", params=params)

    async def create_creative(self, creative_data: dict[str, Any]) -> dict[str, Any]:
        """Create an ad creative."""
        logger.info(f"Creating creative for account {self._account_id}")
        return await self._client.post(f"/{self._account_id}/adcreatives", body=creative_data)
