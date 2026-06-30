"""Labour market enumerations (15_LABOUR_MARKET_MODEL.md §6, §14, §15, §20)."""

from __future__ import annotations

from enum import Enum


class GeographicLevel(str, Enum):
    """Geographic granularity of a market observation (15 §6)."""

    GLOBAL = "global"
    CONTINENT = "continent"
    COUNTRY = "country"
    STATE = "state"
    REGION = "region"
    CITY = "city"


class TimeHorizon(str, Enum):
    """Whether an observation is historical, current or projected (15 §7)."""

    HISTORICAL = "historical"
    CURRENT = "current"
    PROJECTED = "projected"


class OutlookCategory(str, Enum):
    """Future outlook for a career (15 §14)."""

    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    EMERGING = "emerging"
    TRANSFORMING = "transforming"


class RemoteWorkMode(str, Enum):
    """Remote work characteristics (15 §15)."""

    FULLY_REMOTE = "fully_remote"
    HYBRID = "hybrid"
    OFFICE = "office"
    FIELD = "field"
    LABORATORY = "laboratory"
    ON_SITE = "on_site"
    TRAVEL_REQUIRED = "travel_required"


class MarketEventType(str, Enum):
    """Events that shift the market (15 §20)."""

    RECESSION = "recession"
    GOVERNMENT_POLICY = "government_policy"
    TECHNOLOGY_BREAKTHROUGH = "technology_breakthrough"
    PANDEMIC = "pandemic"
    INDUSTRY_REGULATION = "industry_regulation"
    MAJOR_INVESTMENT = "major_investment"
    NEW_LEGISLATION = "new_legislation"
