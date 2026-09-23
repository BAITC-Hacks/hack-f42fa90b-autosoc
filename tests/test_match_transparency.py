"""Метаданные воронки, локали и альтернативы не меняют подбор."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.i18n import localize_match, normalize_locale
from app.main import app
from app.matcher import match
from app.schemas import CALENDAR_END, CALENDAR_START, MatchRequest, Profile


def profile(profile_id: str, **changes: object) -> Profile:
    values = dict(
        id=profile_id, anon_name=f"Профиль {profile_id}", categories=("Ведущий",),
        city="Алматы", city_imputed=False, synthetic=False,
        price_from_kzt=100_000, price_imputed=False, event_formats=("свадьба",),
        languages=("русский",), max_hours=6, busy_dates=(),
        description="Проводит церемонии и составляет сценарий.", provenance="original_csv",
    )
    values.update(changes)
    return Profile(**values)


def query(**changes: object) -> MatchRequest:
    values = dict(
        city="Алматы", date="2026-10-07", event_format="свадьба",
        category="Ведущий", budget_kzt=300_000,
    )
    values.update(changes)
    return MatchRequest(**values)


def steps(result):
    return {item.step: (item.count, item.applied) for item in result.funnel}


def test_funnel_counts_each_primary_reason_once_and_adds_data_step():
    profiles = (
        profile("elsewhere", city="Астана"),
        profile("other_category", categories=("Флорист",)),
        profile("busy_and_expensive", busy_dates=(date(2026, 10, 7),), price_from_kzt=400_000),
        profile("format", event_formats=("той",)),
        profile("budget", price_from_kzt=400_000),
        profile("language", languages=("английский",)),
        profile("hours", max_hours=2),
        profile("missing", event_formats=()),
        profile("good"),
    )
    result = match(profiles, query(language="русский", hours=4))
    assert result.total_matches == 1
    assert [item.id for item in result.cards] == ["good"]
    assert steps(result) == {
        "catalog": (9, True), "city": (8, True), "category": (7, True),
        "date": (6, True), "format": (5, True), "budget": (4, True),
        "language": (3, True), "hours": (2, True), "insufficient_data": (1, True),
    }
    assert sum(result.primary_reason_counts.values()) + result.total_matches == 7
    busy = next(item for item in result.rejected if item.id == "busy_and_expensive")
    assert busy.anon_name == "Профиль busy_and_expensive"
    assert [reason.code for reason in busy.all_reasons] == ["date", "budget"]
    assert busy.primary_reason == "date"
    assert result.primary_reason_counts["budget"] == 1


def test_funnel_unset_optional_filters_and_no_category():
    catalog = (profile("one"), profile("other", categories=("Флорист",)))
    result = match(catalog, query())
    assert steps(result)["language"] == (1, False)
    assert steps(result)["hours"] == (1, False)
    assert "insufficient_data" not in steps(result)
    absent = match(catalog, query(category="Декоратор"))
    assert absent.outcome == "no_category_in_city"
    assert steps(absent)["catalog"] == (2, True)
    assert steps(absent)["city"] == (2, True)
    assert steps(absent)["category"] == (0, True)
    assert absent.nearby_dates == []


def test_nearby_dates_are_nearest_future_first_and_real_matches():
    busy_on_query = profile("busy", busy_dates=(date(2026, 10, 7),))
    too_expensive = profile("price", busy_dates=(date(2026, 10, 7),), price_from_kzt=400_000)
    result = match((busy_on_query, too_expensive), query())
    assert result.outcome == "all_filtered"
    assert [item.date.isoformat() for item in result.nearby_dates] == [
        "2026-10-08", "2026-10-06", "2026-10-09",
    ]
    for item in result.nearby_dates:
        assert item.total_matches == match(
            (busy_on_query, too_expensive), query(date=item.date.isoformat())
        ).total_matches == 1
    assert result.total_matches == 0


def test_no_nearby_date_when_every_profile_also_fails_budget():
    result = match(
        (profile("both", busy_dates=(date(2026, 10, 7),), price_from_kzt=400_000),),
        query(),
    )
    assert result.nearby_dates == []


def test_nearby_date_respects_calendar_boundaries_and_no_available_date():
    all_dates = tuple(CALENDAR_START + timedelta(days=offset) for offset in range(15))
    result = match((profile("busy", busy_dates=all_dates),), query(date=CALENDAR_START.isoformat()))
    assert result.nearby_dates == []
    near_end = match(
        (profile("end", busy_dates=(CALENDAR_END,)),), query(date=CALENDAR_END.isoformat())
    )
    assert [item.date for item in near_end.nearby_dates] == [
        CALENDAR_END - timedelta(days=1), CALENDAR_END - timedelta(days=2),
        CALENDAR_END - timedelta(days=3),
    ]
    assert all(CALENDAR_START <= item.date <= CALENDAR_END for item in near_end.nearby_dates)


def test_localized_text_keeps_facts_ids_order_sources_and_reasons():
    catalog = (
        profile("busy", busy_dates=(date(2026, 10, 7),)),
        profile("good", price_from_kzt=80_000),
    )
    request = query()
    original = match(catalog, request)
    for locale, phrase in (("kk", "табылды"), ("en", "Found")):
        localized = localize_match(original, catalog, request, locale)
        assert phrase in localized.message
        assert localized.total_matches == original.total_matches
        assert localized.primary_reason_counts == original.primary_reason_counts
        assert localized.funnel == original.funnel
        assert localized.nearby_dates == original.nearby_dates
        assert [card.id for card in localized.cards] == [card.id for card in original.cards]
        assert localized.cards[0].facts == original.cards[0].facts
        assert localized.cards[0].description == original.cards[0].description
        assert localized.cards[0].evidence_excerpt == original.cards[0].evidence_excerpt
        assert localized.cards[0].price_from_kzt == original.cards[0].price_from_kzt
        assert localized.cards[0].explanation != original.cards[0].explanation
        assert [item.primary_reason for item in localized.rejected] == [item.primary_reason for item in original.rejected]
        assert localized.rejected[0].all_reasons[0].detail != original.rejected[0].all_reasons[0].detail


def test_accept_language_parser_and_match_endpoint():
    assert normalize_locale(None) == "ru"
    assert normalize_locale("kk-KZ, en;q=0.8") == "kk"
    assert normalize_locale("xx, en-US;q=0.9, ru;q=0.5") == "en"
    assert normalize_locale("en;q=0, kk;q=0.7") == "kk"
    assert normalize_locale("unknown") == "ru"
    with TestClient(app) as client:
        body = query(budget_kzt=1_000_000).model_dump(mode="json")
        ru = client.post("/api/match", json=body).json()
        en = client.post("/api/match", json=body, headers={"Accept-Language": "en"}).json()
        kk = client.post("/api/match", json=body, headers={"Accept-Language": "kk"}).json()
    for localized in (en, kk):
        assert localized["outcome"] == ru["outcome"]
        assert localized["total_matches"] == ru["total_matches"]
        assert [card["id"] for card in localized["cards"]] == [card["id"] for card in ru["cards"]]
        assert [card["price_from_kzt"] for card in localized["cards"]] == [card["price_from_kzt"] for card in ru["cards"]]
        assert localized["cards"][0]["description"] == ru["cards"][0]["description"]
        assert localized["cards"][0]["evidence_excerpt"] == ru["cards"][0]["evidence_excerpt"]
        assert localized["message"] != ru["message"]
