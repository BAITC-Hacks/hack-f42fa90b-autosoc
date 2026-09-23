"""Контракты HTTP API и внутреннего каталога."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


CALENDAR_START = date(2026, 9, 23)
CALENDAR_END = date(2026, 12, 31)
ReasonCode = Literal["date", "format", "budget", "language", "hours", "insufficient_data"]


class Profile(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    anon_name: str
    categories: tuple[str, ...]
    city: str
    city_imputed: bool
    synthetic: bool
    price_from_kzt: int | None
    price_imputed: bool
    event_formats: tuple[str, ...]
    languages: tuple[str, ...]
    max_hours: int | None
    busy_dates: tuple[date, ...]
    description: str
    provenance: Literal["original_csv", "synthetic_extra"]


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str = Field(min_length=1)
    date: date
    event_format: str = Field(min_length=1)
    category: str = Field(min_length=1)
    budget_kzt: int = Field(strict=True, gt=0)
    language: str | None = None
    hours: int | None = Field(default=None, strict=True, gt=0)

    @field_validator("date", mode="before")
    @classmethod
    def iso_date_only(cls, value: object) -> object:
        if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
            raise ValueError("Дата должна быть в формате YYYY-MM-DD")
        return value

    @field_validator("date")
    @classmethod
    def known_calendar(cls, value: date) -> date:
        if not CALENDAR_START <= value <= CALENDAR_END:
            raise ValueError("Доступность вне календаря 2026-09-23 — 2026-12-31 неизвестна")
        return value

    @field_validator("city", "event_format", "category", "language")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Пустое значение недопустимо")
        return value


class MatchFacts(BaseModel):
    budget_kzt: int
    price_from_kzt: int
    budget_headroom_kzt: int
    budget_headroom_percent: float
    event_format: str
    language: str | None
    requested_hours: int | None
    max_hours: int | None
    date: date
    not_marked_busy_on_date: bool
    description_excerpt: str | None


class MatchCard(BaseModel):
    id: str
    anon_name: str
    categories: tuple[str, ...]
    city: str
    price_from_kzt: int
    rank_score: float
    rank_factors: dict[str, int | float]
    facts: MatchFacts
    explanation: str
    description: str
    synthetic: bool
    city_imputed: bool
    price_imputed: bool
    provenance: Literal["original_csv", "synthetic_extra"]


class RejectionReason(BaseModel):
    code: ReasonCode
    detail: str


class Rejection(BaseModel):
    id: str
    primary_reason: ReasonCode
    detail: str
    all_reasons: list[RejectionReason]


class MatchResponse(BaseModel):
    outcome: Literal["matched", "no_category_in_city", "all_filtered"]
    total_matches: int
    cards: list[MatchCard]
    primary_reason_counts: dict[str, int]
    rejected: list[Rejection]
    excluded_by_date: int
    message: str


class OptionsResponse(BaseModel):
    cities: list[str]
    categories: list[str]
    categories_by_city: dict[str, list[str]]
    event_formats: list[str]
    languages: list[str]
    calendar_start: date
    calendar_end: date
