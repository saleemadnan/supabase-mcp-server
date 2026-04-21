"""Pydantic models for Meta Marketing API entities."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CampaignStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"


class CampaignObjective(str, Enum):
    AWARENESS = "AWARENESS"
    TRAFFIC = "TRAFFIC"
    ENGAGEMENT = "ENGAGEMENT"
    LEADS = "LEADS"
    APP_PROMOTION = "APP_PROMOTION"
    SALES = "SALES"
    # Legacy objectives still supported
    LINK_CLICKS = "LINK_CLICKS"
    CONVERSIONS = "CONVERSIONS"
    BRAND_AWARENESS = "BRAND_AWARENESS"
    REACH = "REACH"
    VIDEO_VIEWS = "VIDEO_VIEWS"
    MESSAGES = "MESSAGES"


class BillingEvent(str, Enum):
    APP_INSTALLS = "APP_INSTALLS"
    CLICKS = "CLICKS"
    IMPRESSIONS = "IMPRESSIONS"
    LINK_CLICKS = "LINK_CLICKS"
    NONE = "NONE"
    OFFER_CLAIMS = "OFFER_CLAIMS"
    PAGE_LIKES = "PAGE_LIKES"
    POST_ENGAGEMENT = "POST_ENGAGEMENT"
    VIDEO_VIEWS = "VIDEO_VIEWS"
    THRUPLAY = "THRUPLAY"


class OptimizationGoal(str, Enum):
    NONE = "NONE"
    APP_INSTALLS = "APP_INSTALLS"
    AD_RECALL_LIFT = "AD_RECALL_LIFT"
    ENGAGED_USERS = "ENGAGED_USERS"
    EVENT_RESPONSES = "EVENT_RESPONSES"
    IMPRESSIONS = "IMPRESSIONS"
    LEAD_GENERATION = "LEAD_GENERATION"
    QUALITY_LEAD = "QUALITY_LEAD"
    LINK_CLICKS = "LINK_CLICKS"
    OFFSITE_CONVERSIONS = "OFFSITE_CONVERSIONS"
    PAGE_LIKES = "PAGE_LIKES"
    POST_ENGAGEMENT = "POST_ENGAGEMENT"
    QUALITY_CALL = "QUALITY_CALL"
    REACH = "REACH"
    LANDING_PAGE_VIEWS = "LANDING_PAGE_VIEWS"
    VISIT_INSTAGRAM_PROFILE = "VISIT_INSTAGRAM_PROFILE"
    VALUE = "VALUE"
    THRUPLAY = "THRUPLAY"
    DERIVED_EVENTS = "DERIVED_EVENTS"
    APP_INSTALLS_AND_OFFSITE_CONVERSIONS = "APP_INSTALLS_AND_OFFSITE_CONVERSIONS"
    CONVERSATIONS = "CONVERSATIONS"
    IN_APP_VALUE = "IN_APP_VALUE"
    MESSAGING_PURCHASE_CONVERSION = "MESSAGING_PURCHASE_CONVERSION"
    SUBSCRIBERS = "SUBSCRIBERS"
    REMINDERS_SET = "REMINDERS_SET"
    VIDEO_VIEWS = "VIDEO_VIEWS"


class AdStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"
    IN_PROCESS = "IN_PROCESS"
    WITH_ISSUES = "WITH_ISSUES"


class TargetingAge(BaseModel):
    age_min: int = Field(default=18, ge=13, le=65)
    age_max: int = Field(default=65, ge=13, le=65)


class GeoLocation(BaseModel):
    countries: list[str] = Field(default_factory=list)
    cities: list[dict[str, Any]] = Field(default_factory=list)
    regions: list[dict[str, Any]] = Field(default_factory=list)


class Targeting(BaseModel):
    age_min: int = Field(default=18, ge=13, le=65)
    age_max: int = Field(default=65, ge=13, le=65)
    genders: list[int] = Field(default_factory=list)  # 1=male, 2=female
    geo_locations: GeoLocation = Field(default_factory=GeoLocation)
    interests: list[dict[str, Any]] = Field(default_factory=list)
    behaviors: list[dict[str, Any]] = Field(default_factory=list)


class BudgetType(str, Enum):
    DAILY = "daily_budget"
    LIFETIME = "lifetime_budget"


class CreateCampaignRequest(BaseModel):
    name: str
    objective: CampaignObjective
    status: CampaignStatus = CampaignStatus.PAUSED
    special_ad_categories: list[str] = Field(default_factory=list)
    daily_budget: int | None = None  # in cents
    lifetime_budget: int | None = None  # in cents


class UpdateCampaignRequest(BaseModel):
    name: str | None = None
    status: CampaignStatus | None = None
    daily_budget: int | None = None
    lifetime_budget: int | None = None


class CreateAdSetRequest(BaseModel):
    campaign_id: str
    name: str
    billing_event: BillingEvent
    optimization_goal: OptimizationGoal
    bid_amount: int | None = None  # in cents
    daily_budget: int | None = None  # in cents
    lifetime_budget: int | None = None  # in cents
    start_time: str | None = None  # ISO 8601
    end_time: str | None = None  # ISO 8601
    targeting: dict[str, Any] = Field(default_factory=dict)
    status: CampaignStatus = CampaignStatus.PAUSED


class CreateAdRequest(BaseModel):
    adset_id: str
    name: str
    creative: dict[str, Any]
    status: AdStatus = AdStatus.PAUSED


class InsightsRequest(BaseModel):
    fields: list[str] = Field(
        default_factory=lambda: [
            "impressions",
            "clicks",
            "spend",
            "reach",
            "cpc",
            "cpm",
            "ctr",
        ]
    )
    date_preset: str = "last_7d"
    time_increment: int | None = None
    breakdowns: list[str] = Field(default_factory=list)
