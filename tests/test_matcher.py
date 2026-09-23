from datetime import date

import pytest

from app.matcher import match
from app.schemas import MatchRequest, Profile


def profile(id: str, **changes: object) -> Profile:
    values = dict(
        id=id, anon_name=f"Профиль {id}", categories=("Ведущий",), city="Алматы",
        city_imputed=False, synthetic=False, price_from_kzt=100000, price_imputed=False,
        event_formats=("свадьба",), languages=("русский",), max_hours=6,
        busy_dates=(), description="Подтверждённый текст профиля.", provenance="original_csv",
    )
    values.update(changes)
    return Profile(**values)


def query(**changes: object) -> MatchRequest:
    values = dict(city="Алматы", date="2026-10-07", event_format="свадьба", category="Ведущий", budget_kzt=300000)
    values.update(changes)
    return MatchRequest(**values)


def test_busy_contractor_and_venue_are_excluded():
    profiles = [
        profile("person", busy_dates=(date(2026, 10, 7),)),
        profile("venue", categories=("Банкетный зал", "Ведущий"), busy_dates=(date(2026, 10, 7),)),
        profile("free"),
    ]
    result = match(profiles, query())
    assert [card.id for card in result.cards] == ["free"]
    assert result.excluded_by_date == 2
    assert result.primary_reason_counts["date"] == 2
    assert "меньше трёх" in result.message
    venue_result = match(profiles, query(category="Банкетный зал"))
    assert venue_result.outcome == "all_filtered"
    assert venue_result.excluded_by_date == 1


def test_multiple_categories_and_three_distinct_outcomes():
    profiles = [profile("one", categories=("Ведущий", "Шоу-программа"))]
    assert match(profiles, query(category="Шоу-программа")).outcome == "matched"
    assert match(profiles, query(category="Флорист")).outcome == "no_category_in_city"
    assert match(profiles, query(budget_kzt=50000)).outcome == "all_filtered"


def test_order_is_stable_and_limit_is_three():
    profiles = [profile(str(id), price_from_kzt=100000) for id in (5, 4, 3, 2, 1)]
    first = match(profiles, query())
    second = match(list(reversed(profiles)), query())
    assert first.total_matches == second.total_matches == 5
    assert [card.id for card in first.cards] == ["1", "2", "3"]
    assert [card.id for card in second.cards] == ["1", "2", "3"]
    assert first == match(profiles, query())


def test_more_supported_formats_are_not_penalized():
    profiles = [
        profile("a", event_formats=("свадьба", "юбилей")),
        profile("b", event_formats=("свадьба",)),
    ]
    assert [card.id for card in match(profiles, query()).cards] == ["a", "b"]


def test_budget_language_hours_and_unknown_price():
    profiles = [
        profile("price", price_from_kzt=400000),
        profile("unknown_price", price_from_kzt=None),
        profile("language", languages=("английский",)),
        profile("hours", max_hours=2),
        profile("unbounded", max_hours=None, synthetic=True, city_imputed=True, price_imputed=True),
    ]
    result = match(profiles, query(language="русский", hours=4))
    assert [card.id for card in result.cards] == ["unbounded"]
    assert result.primary_reason_counts == {
        "date": 0, "format": 0, "budget": 1, "language": 1,
        "hours": 1, "insufficient_data": 1,
    }
    card = result.cards[0]
    assert (card.synthetic, card.city_imputed, card.price_imputed) == (True, True, True)
    assert card.facts.requested_hours == 4 and card.facts.max_hours is None
    assert card.facts.budget_headroom_kzt == 200000
    assert card.facts.budget_headroom_percent == pytest.approx(66.7)
    assert "не привязана к часам" in card.explanation
    assert "неограниченн" not in card.explanation


def test_one_primary_reason_even_when_many_filters_fail():
    profiles = [profile(
        "all", busy_dates=(date(2026, 10, 7),), event_formats=("юбилей",),
        price_from_kzt=500000, languages=("английский",), max_hours=2,
    )]
    result = match(profiles, query(language="русский", hours=4))
    assert result.primary_reason_counts["date"] == 1
    assert sum(result.primary_reason_counts.values()) == 1
    rejection = result.rejected[0]
    assert rejection.primary_reason == "date"
    assert rejection.detail == "Занят на 2026-10-07"
    assert [reason.code for reason in rejection.all_reasons] == ["date", "format", "budget", "language", "hours"]
    assert "юбилей" in rejection.all_reasons[1].detail
    assert "500000" in rejection.all_reasons[2].detail and "300000" in rejection.all_reasons[2].detail
    assert "английский" in rejection.all_reasons[3].detail
    assert "4 ч" in rejection.all_reasons[4].detail and "2 ч" in rejection.all_reasons[4].detail


def test_missing_fields_are_reported_alongside_other_reasons():
    result = match(
        [profile("missing", busy_dates=(date(2026, 10, 7),), event_formats=(), price_from_kzt=None, languages=())],
        query(language="русский"),
    )
    rejection = result.rejected[0]
    assert [reason.code for reason in rejection.all_reasons] == ["date", "insufficient_data"]
    assert "свадьба" in rejection.all_reasons[1].detail
    assert "300000 ₸" in rejection.all_reasons[1].detail
    assert "русский" in rejection.all_reasons[1].detail
    assert sum(result.primary_reason_counts.values()) == 1


def test_explanation_uses_own_data_only():
    profiles = [
        profile("a", anon_name="Первый", description="Только собственный текст."),
        profile("b", anon_name="Второй", description="Чужой уникальный факт."),
    ]
    cards = match(profiles, query()).cards
    assert cards[0].facts.description_excerpt == "Только собственный текст"
    assert "Чужой уникальный факт" not in cards[0].explanation
    assert "отзыв" not in cards[0].explanation.lower()
    assert cards[0].facts.not_marked_busy_on_date


@pytest.mark.parametrize("changes", [
    {"date": "2026-09-22"}, {"date": "2027-01-01"}, {"date": "not-a-date"},
    {"budget_kzt": 0}, {"budget_kzt": -1}, {"budget_kzt": 1.5},
    {"hours": 0}, {"hours": -2}, {"hours": 1.5},
])
def test_invalid_requests(changes):
    with pytest.raises(ValueError):
        query(**changes)
