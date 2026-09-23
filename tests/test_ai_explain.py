"""Проверки необязательного AI-выбора цитат без сетевых запросов."""

import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest

from app import ai_explain
from app.ai_explain import enrich_match
from app.config import ExplanationSettings, get_settings
from app.matcher import match
from app.schemas import MatchRequest, Profile


DESCRIPTION_A = "Проводит выездные церемонии и готовит сценарий вместе с организатором."
DESCRIPTION_B = "Подбирает музыкальные паузы для торжественных событий."
FABRICATED_EXCERPT = "Организует полёты на воздушном шаре для гостей."


def profile(id: str, *, description: str = DESCRIPTION_A, **changes: object) -> Profile:
    values = dict(
        id=id,
        anon_name=f"Профиль {id}",
        categories=("Ведущий",),
        city="Алматы",
        city_imputed=False,
        synthetic=False,
        price_from_kzt=100_000,
        price_imputed=False,
        event_formats=("свадьба",),
        languages=("русский",),
        max_hours=6,
        busy_dates=(),
        description=description,
        provenance="original_csv",
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


class FakeClient:
    """Только интерфейс responses.parse, используемый приложением."""

    def __init__(self, selections=(), *, error=None, delay=0, status="completed"):
        self.responses = self
        self.selections = selections
        self.error = error
        self.delay = delay
        self.status = status
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            status=self.status,
            output_parsed={"selections": self.selections},
        )


def selection(id: str, excerpt: str | None) -> dict[str, str | None]:
    return {"id": id, "excerpt": excerpt}


def enrich(response, profiles, request, client, *, settings=None):
    if settings is None:
        settings = ExplanationSettings(mode="auto", api_key="test-key")
    return asyncio.run(enrich_match(response, tuple(profiles), request, settings=settings, client=client))


def test_get_settings_reads_local_env_without_key(tmp_path, monkeypatch):
    for name in ("EXPLANATION_MODE", "OPENAI_MODEL", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "EXPLANATION_MODE=auto\nOPENAI_MODEL=local-test-model\n",
        encoding="utf-8",
    )

    settings = get_settings(root=tmp_path)

    assert settings.mode == "auto"
    assert settings.model == "local-test-model"
    assert settings.api_key is None


def test_get_settings_process_variables_override_local_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "EXPLANATION_MODE=auto\nOPENAI_MODEL=local-test-model\nOPENAI_API_KEY=local-placeholder\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EXPLANATION_MODE", "template")
    monkeypatch.setenv("OPENAI_MODEL", "process-test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "process-placeholder")

    settings = get_settings(root=tmp_path)

    assert settings.mode == "template"
    assert settings.model == "process-test-model"
    assert settings.api_key == "process-placeholder"
    assert settings.api_key not in repr(settings)


@pytest.mark.parametrize("settings", [
    ExplanationSettings(mode="auto", api_key=None),
    ExplanationSettings(mode="template", api_key="test-key"),
])
def test_disabled_ai_keeps_template_and_never_calls_client(settings):
    profiles = [profile("a")]
    request = query()
    response = match(profiles, request)
    client = FakeClient([selection("a", DESCRIPTION_A)])

    enriched = enrich(response, profiles, request, client, settings=settings)

    assert enriched is response
    assert client.calls == []
    assert enriched.cards[0].explanation_source == "template"
    assert enriched.cards[0].facts.description_excerpt in DESCRIPTION_A


def test_valid_own_excerpt_is_accepted_and_request_contains_only_selected_profiles():
    profiles = [profile("a"), profile("not-selected", price_from_kzt=500_000)]
    request = query()
    response = match(profiles, request)
    client = FakeClient([selection("a", DESCRIPTION_A)])

    enriched = enrich(response, profiles, request, client)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["store"] is False
    assert call["text_format"] is ai_explain.QuoteBatch
    payload = json.loads(call["input"][1]["content"])
    assert [item["id"] for item in payload["selected_profiles"]] == ["a"]
    assert payload["selected_profiles"][0]["description"] == DESCRIPTION_A
    assert enriched.cards[0].explanation_source == "ai_selected"
    assert enriched.cards[0].evidence_excerpt == DESCRIPTION_A
    assert enriched.cards[0].facts.description_excerpt == DESCRIPTION_A
    assert DESCRIPTION_A in enriched.cards[0].explanation
    assert enriched.rejected == response.rejected


@pytest.mark.parametrize("invalid_excerpt", [DESCRIPTION_B, FABRICATED_EXCERPT])
def test_foreign_or_fabricated_excerpt_falls_back_for_its_card_only(invalid_excerpt):
    profiles = [profile("a"), profile("b", description=DESCRIPTION_B)]
    request = query()
    response = match(profiles, request)
    client = FakeClient([
        selection("a", invalid_excerpt),
        selection("b", DESCRIPTION_B),
    ])

    enriched = enrich(response, profiles, request, client)

    assert enriched.cards[0] == response.cards[0]
    assert enriched.cards[0].explanation_source == "template"
    assert invalid_excerpt not in enriched.cards[0].explanation
    assert enriched.cards[1].explanation_source == "ai_selected"
    assert enriched.cards[1].evidence_excerpt == DESCRIPTION_B


def test_exact_two_sentence_excerpt_falls_back_to_template():
    description = "Готовит сценарий с организатором. Проводит выездные церемонии на русском языке."
    profiles = [profile("a", description=description)]
    request = query()
    response = match(profiles, request)
    client = FakeClient([selection("a", description)])

    enriched = enrich(response, profiles, request, client)

    assert len(client.calls) == 1
    assert enriched.cards[0] == response.cards[0]
    assert enriched.cards[0].explanation_source == "template"
    assert enriched.cards[0].evidence_excerpt != description


def test_extra_id_rejects_the_batch_without_changing_response():
    profiles = [profile("a")]
    request = query()
    response = match(profiles, request)
    client = FakeClient([
        selection("a", DESCRIPTION_A),
        selection("unknown", FABRICATED_EXCERPT),
    ])

    enriched = enrich(response, profiles, request, client)

    assert enriched is response
    assert enriched.cards[0].explanation_source == "template"


@pytest.mark.parametrize("selections", [
    [selection("a", DESCRIPTION_A), selection("a", DESCRIPTION_A), selection("b", DESCRIPTION_B)],
    [selection("b", DESCRIPTION_B)],
])
def test_duplicate_or_missing_id_does_not_supply_an_unsafe_quote(selections):
    profiles = [profile("a"), profile("b", description=DESCRIPTION_B)]
    request = query()
    response = match(profiles, request)
    client = FakeClient(selections)

    enriched = enrich(response, profiles, request, client)

    assert enriched.cards[0] == response.cards[0]
    assert enriched.cards[1].explanation_source == "ai_selected"
    assert enriched.cards[1].evidence_excerpt == DESCRIPTION_B
    assert [card.id for card in enriched.cards] == ["a", "b"]


def test_service_exception_falls_back_to_original_response():
    profiles = [profile("a")]
    request = query()
    response = match(profiles, request)
    client = FakeClient(error=RuntimeError("service unavailable"))

    assert enrich(response, profiles, request, client) is response
    assert len(client.calls) == 1


def test_timeout_falls_back_to_original_response(monkeypatch):
    profiles = [profile("a")]
    request = query()
    response = match(profiles, request)
    client = FakeClient(delay=0.1)
    monkeypatch.setattr(ai_explain, "AI_DEADLINE_SECONDS", 0.001)

    assert enrich(response, profiles, request, client) is response
    assert len(client.calls) == 1


def test_enrichment_preserves_order_filter_result_rejections_and_card_facts():
    profiles = [
        profile("b", description=DESCRIPTION_B),
        profile("a"),
        profile("busy", busy_dates=(date(2026, 10, 7),)),
    ]
    request = query(language="русский", hours=4)
    response = match(profiles, request)
    client = FakeClient([
        selection("b", DESCRIPTION_B),
        selection("a", DESCRIPTION_A),
    ])

    enriched = enrich(response, profiles, request, client)

    assert [card.id for card in enriched.cards] == [card.id for card in response.cards] == ["a", "b"]
    for field in ("outcome", "total_matches", "primary_reason_counts", "rejected", "excluded_by_date", "message"):
        assert getattr(enriched, field) == getattr(response, field)
    for before, after in zip(response.cards, enriched.cards):
        for field in before.__class__.model_fields:
            if field not in {"facts", "explanation", "explanation_source", "evidence_excerpt"}:
                assert getattr(after, field) == getattr(before, field)
        assert after.facts.model_dump(exclude={"description_excerpt"}) == before.facts.model_dump(exclude={"description_excerpt"})
        assert after.evidence_excerpt in after.description
        assert after.explanation_source == "ai_selected"


def test_same_price_profiles_get_distinct_own_template_details_without_ai():
    profiles = [profile("a"), profile("b", description=DESCRIPTION_B)]
    request = query()
    response = match(profiles, request)
    client = FakeClient()

    enriched = enrich(
        response, profiles, request, client,
        settings=ExplanationSettings(mode="template", api_key="test-key"),
    )

    assert client.calls == []
    assert enriched.cards[0].price_from_kzt == enriched.cards[1].price_from_kzt
    assert [card.evidence_excerpt for card in enriched.cards] == [DESCRIPTION_A.rstrip("."), DESCRIPTION_B.rstrip(".")]
    assert DESCRIPTION_B.rstrip(".") not in enriched.cards[0].explanation
    assert DESCRIPTION_A.rstrip(".") not in enriched.cards[1].explanation
    assert all(card.explanation_source == "template" for card in enriched.cards)


def test_empty_description_skips_ai_when_no_other_profile_has_text():
    profiles = [profile("empty", description="")]
    request = query()
    response = match(profiles, request)
    client = FakeClient([selection("empty", FABRICATED_EXCERPT)])

    enriched = enrich(response, profiles, request, client)

    assert enriched is response
    assert client.calls == []
    assert enriched.cards[0].evidence_excerpt is None
    assert enriched.cards[0].facts.description_excerpt is None


def test_empty_description_cannot_borrow_another_profiles_excerpt():
    profiles = [profile("empty", description=""), profile("real", description=DESCRIPTION_B)]
    request = query()
    response = match(profiles, request)
    client = FakeClient([
        selection("empty", DESCRIPTION_B),
        selection("real", DESCRIPTION_B),
    ])

    enriched = enrich(response, profiles, request, client)

    assert enriched.cards[0] == response.cards[0]
    assert enriched.cards[0].evidence_excerpt is None
    assert enriched.cards[1].explanation_source == "ai_selected"


@pytest.mark.parametrize("search_request", [
    query(category="Декоратор"),
    query(budget_kzt=50_000),
])
def test_empty_results_never_call_ai(search_request):
    profiles = [profile("a")]
    response = match(profiles, search_request)
    client = FakeClient()

    assert response.cards == []
    assert enrich(response, profiles, search_request, client) is response
    assert client.calls == []
