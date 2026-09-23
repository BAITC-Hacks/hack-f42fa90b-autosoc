"""Two dates are compared by eligible profile IDs, not by the three visible cards."""

from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.matcher import match
from app.schemas import MatchRequest, Profile


def _profile(identifier: str, *, busy_dates: tuple[date, ...] = (), price: int = 100_000) -> Profile:
    return Profile(
        id=identifier, anon_name=f"Profile {identifier}", categories=("Ведущий",),
        city="Алматы", city_imputed=False, synthetic=False, price_from_kzt=price,
        price_imputed=False, event_formats=("свадьба",), languages=("русский",),
        max_hours=6, busy_dates=busy_dates, description="Source description.",
        provenance="original_csv",
    )


def _request(day: str) -> MatchRequest:
    return MatchRequest(
        city="Алматы", category="Ведущий", date=day,
        event_format="свадьба", budget_kzt=300_000,
    )


def test_full_eligible_ids_expose_top_three_displacement_without_false_busy_claim() -> None:
    profiles = [
        _profile("a", busy_dates=(date(2026, 10, 10),)),
        _profile("b"), _profile("c"), _profile("d"),
    ]
    first = match(profiles, _request("2026-10-07"))
    second = match(reversed(profiles), _request("2026-10-10"))
    assert first.total_matches == 4
    assert first.matched_ids == ["a", "b", "c", "d"]
    assert [card.id for card in first.cards] == ["a", "b", "c"]
    assert second.matched_ids == ["b", "c", "d"]
    assert [card.id for card in second.cards] == ["b", "c", "d"]
    assert "d" not in {item.id for item in first.rejected}
    assert {item.id: item for item in second.rejected}["a"].primary_reason == "date"


def test_visible_profile_falls_out_of_top_three_but_remains_eligible() -> None:
    profiles = [
        _profile("a", price=200_000), _profile("b", price=200_000),
        _profile("c", price=200_000),
        _profile("x", busy_dates=(date(2026, 10, 7),), price=100_000),
        _profile("y", busy_dates=(date(2026, 10, 7),), price=100_000),
    ]
    first = match(profiles, _request("2026-10-07"))
    second = match(reversed(profiles), _request("2026-10-10"))
    assert [card.id for card in first.cards] == ["a", "b", "c"]
    assert second.matched_ids == ["x", "y", "a", "b", "c"]
    assert [card.id for card in second.cards] == ["x", "y", "a"]
    assert not {"b", "c"} & {item.id for item in second.rejected}


def test_busy_and_over_budget_are_both_reported_across_dates() -> None:
    profiles = [
        _profile("both", busy_dates=(date(2026, 10, 10),), price=400_000),
        _profile("eligible"),
    ]
    first = match(profiles, _request("2026-10-07"))
    second = match(profiles, _request("2026-10-10"))
    assert first.matched_ids == second.matched_ids == ["eligible"]
    assert [reason.code for reason in first.rejected[0].all_reasons] == ["budget"]
    assert [reason.code for reason in second.rejected[0].all_reasons] == ["date", "budget"]
    assert second.primary_reason_counts["date"] == 1
    assert sum(second.primary_reason_counts.values()) == 1


def test_real_catalog_date_pair_and_api_id_contract(monkeypatch) -> None:
    payload = {
        "city": "Алматы", "category": "Ведущий", "event_format": "свадьба",
        "date": "2026-10-10", "budget_kzt": 1_000_000,
    }
    async def fail_if_enrichment_called(*_args, **_kwargs):
        raise AssertionError("Comparison must not call AI enrichment")

    monkeypatch.setattr("app.main.enrich_match", fail_if_enrichment_called)
    with TestClient(app) as client:
        first = client.post("/api/match?explain=template", json=payload)
        second = client.post("/api/match?explain=template", json={**payload, "date": "2026-12-12"})
        invalid = client.post("/api/match?explain=unexpected", json=payload)
    assert first.status_code == second.status_code == 200
    assert invalid.status_code == 422
    first_body, second_body = first.json(), second.json()
    assert first_body["total_matches"] == len(first_body["matched_ids"]) == 2
    assert second_body["total_matches"] == len(second_body["matched_ids"]) == 1
    for body in (first_body, second_body):
        assert {card["id"] for card in body["cards"]} <= set(body["matched_ids"])
        assert not ({rejection["id"] for rejection in body["rejected"]} & set(body["matched_ids"]))
