"""Budget Plan B uses verified prices and never relaxes another filter."""

from datetime import date
from pathlib import Path
import re

from app.matcher import match
from app.schemas import MatchRequest, Profile


def profile(profile_id: str, price: int, **changes: object) -> Profile:
    values = dict(
        id=profile_id, anon_name=profile_id, categories=("Ведущий",),
        city="Алматы", city_imputed=False, synthetic=False,
        price_from_kzt=price, price_imputed=False,
        event_formats=("свадьба",), languages=("русский",),
        max_hours=6, busy_dates=(), description="Ведущий мероприятия.",
        provenance="original_csv",
    )
    values.update(changes)
    return Profile(**values)


def request(**changes: object) -> MatchRequest:
    values = dict(
        city="Алматы", date="2026-10-07", event_format="свадьба",
        category="Ведущий", budget_kzt=300_000,
        language="русский", hours=4,
    )
    values.update(changes)
    return MatchRequest(**values)


def test_minimum_starting_price_and_ordinary_match_keep_other_fields():
    catalog = (profile("higher", 500_000), profile("minimum", 420_000))
    original = request()
    result = match(catalog, original)
    assert result.outcome == "all_filtered"
    assert result.budget_suggestion is not None
    assert result.budget_suggestion.price_from_kzt == 420_000
    assert result.budget_suggestion.increase_kzt == 120_000
    changed = original.model_copy(update={"budget_kzt": result.budget_suggestion.price_from_kzt})
    assert changed.model_dump(exclude={"budget_kzt"}) == original.model_dump(exclude={"budget_kzt"})
    assert match(catalog, changed).matched_ids == ["minimum"]
    assert match(catalog, changed).budget_suggestion is None


def test_busy_and_over_budget_does_not_set_minimum():
    catalog = (
        profile("busy_cheaper", 310_000, busy_dates=(date(2026, 10, 7),)),
        profile("available", 450_000),
    )
    result = match(catalog, request())
    assert result.budget_suggestion is not None
    assert result.budget_suggestion.price_from_kzt == 450_000
    assert result.budget_suggestion.increase_kzt == 150_000
    assert result.primary_reason_counts["date"] == 1
    assert result.primary_reason_counts["budget"] == 1


def test_no_budget_option_when_any_other_requested_check_fails():
    blocked = (
        profile("busy", 350_000, busy_dates=(date(2026, 10, 7),)),
        profile("format", 350_000, event_formats=("той",)),
        profile("language", 350_000, languages=("казахский",)),
        profile("hours", 350_000, max_hours=2),
    )
    result = match(blocked, request())
    assert result.outcome == "all_filtered"
    assert result.budget_suggestion is None
    assert [item.primary_reason for item in result.rejected] == [
        "date", "format", "budget", "budget",
    ]
    assert [[reason.code for reason in item.all_reasons] for item in result.rejected] == [
        ["date", "budget"], ["format", "budget"],
        ["budget", "hours"], ["budget", "language"],
    ]
    # Increasing only the budget still leaves every candidate excluded.
    assert match(blocked, request(budget_kzt=350_000)).total_matches == 0


def test_no_suggestion_for_unrelated_failure_or_existing_match():
    assert match((profile("busy", 100_000, busy_dates=(date(2026, 10, 7),)),), request()).budget_suggestion is None
    assert match((profile("ok", 100_000),), request()).budget_suggestion is None


def test_budget_suggestion_ui_labels_exist_in_every_locale():
    script = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    expected = {"budgetSuggestionTitle", "budgetSuggestionIntro", "budgetSuggestionAction"}
    for locale in ("ru", "kk", "en"):
        block = re.search(rf"Object\.assign\(ui\.{locale}, \{{(.*?)\n\}}\);", script, re.S)
        assert block is not None
        assert set(re.findall(r"\b(budgetSuggestion\w+):\s*\"", block.group(1))) == expected
