"""Shared measurement value objects (31A_VALUE_OBJECT_MODEL.md §5–§24).

Value Objects have no identity, are immutable, are compared by value, and
self-validate at construction (31A §3, §4). They are reusable across every
bounded context and remain storage-independent. Confidence, Score, UnitInterval,
Importance, ScoreRange and ProficiencyLevel already live in this package; this
module adds the remaining canonical measures.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from .scores import UnitInterval


class Priority(str, Enum):
    """Relative priority (31A §11)."""

    IMMEDIATE = "immediate"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    FUTURE = "future"


class RiskLevel(str, Enum):
    """Risk magnitude, e.g. automation risk (31A §22)."""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class DurationUnit(str, Enum):
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


class SalaryPeriod(str, Enum):
    HOURLY = "hourly"
    MONTHLY = "monthly"
    ANNUAL = "annual"


class CEFRLevel(str, Enum):
    """Common European Framework language proficiency (31A §19)."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


@dataclass(frozen=True, slots=True)
class QualityScore:
    """Normalized quality measure (31A §23)."""

    value: UnitInterval

    @classmethod
    def of(cls, value: float) -> "QualityScore":
        return cls(UnitInterval(value))


@dataclass(frozen=True, slots=True)
class FreshnessScore:
    """Temporal relevance; higher = newer (31A §24)."""

    value: UnitInterval

    @classmethod
    def of(cls, value: float) -> "FreshnessScore":
        return cls(UnitInterval(value))


@dataclass(frozen=True, slots=True)
class Duration:
    """Elapsed time with a unit (31A §13). Supports normalization to hours."""

    amount: float
    unit: DurationUnit

    _HOURS = {
        DurationUnit.HOURS: 1.0,
        DurationUnit.DAYS: 24.0,
        DurationUnit.WEEKS: 168.0,
        DurationUnit.MONTHS: 730.0,
        DurationUnit.YEARS: 8760.0,
    }

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Duration.amount must be >= 0")

    def to_hours(self) -> float:
        return self.amount * self._HOURS[self.unit]


@dataclass(frozen=True, slots=True)
class DateRange:
    """A calendar interval (31A §15). Must satisfy start <= end."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("DateRange.start must be <= end")

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass(frozen=True, slots=True)
class Money:
    """A monetary amount (31A §16). Arithmetic is currency-aware."""

    amount: float
    currency: str

    def __post_init__(self) -> None:
        if not self.currency.strip():
            raise ValueError("Money.currency must be provided")

    def __add__(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError("Cannot add Money of different currencies")
        return Money(self.amount + other.amount, self.currency)


@dataclass(frozen=True, slots=True)
class SalaryRange:
    """Compensation range (31A §17)."""

    minimum: float
    maximum: float
    currency: str
    period: SalaryPeriod = SalaryPeriod.ANNUAL
    typical: float | None = None

    def __post_init__(self) -> None:
        if not self.currency.strip():
            raise ValueError("SalaryRange.currency must be provided")
        if self.minimum > self.maximum:
            raise ValueError("SalaryRange.minimum must be <= maximum")
        if self.typical is not None and not (self.minimum <= self.typical <= self.maximum):
            raise ValueError("SalaryRange.typical must fall within [minimum, maximum]")


@dataclass(frozen=True, slots=True)
class Coordinate:
    """A geographic location (31A §18)."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError("latitude must be within [-90, 90]")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError("longitude must be within [-180, 180]")


@dataclass(frozen=True, slots=True)
class LanguageProficiency:
    """Language ability against a recognized framework (31A §19)."""

    language: str
    level: CEFRLevel

    def __post_init__(self) -> None:
        if not self.language.strip():
            raise ValueError("LanguageProficiency.language must be provided")
