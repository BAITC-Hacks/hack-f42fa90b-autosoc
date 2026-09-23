"""Проверки необязательного AI-выбора цитат без сетевых запросов."""

import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest

from app import ai_explain
from app.ai_explain import apply_fragment_choices, enrich_match, fragment_catalog
from app.config import ExplanationSettings, get_settings
from app.data import load_profiles
from app.explain import make_card, valid_excerpt
from app.matcher import match
from app.schemas import MatchRequest, Profile


DESCRIPTION_A = "Проводит выездные церемонии и готовит сценарий вместе с организатором."
DESCRIPTION_B = "Подбирает музыкальные паузы для торжественных событий."


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


def fragment_id(id: str, index: int = 1) -> str:
    return f"{id}:f{index:03d}"


def selection(id: str, selected_fragment_id: str | None) -> dict[str, str | None]:
    return {"id": id, "fragment_id": selected_fragment_id}


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
    client = FakeClient([selection("a", fragment_id("a"))])

    enriched = enrich(response, profiles, request, client, settings=settings)

    assert enriched is response
    assert client.calls == []
    assert enriched.cards[0].explanation_source == "template"
    assert enriched.cards[0].facts.description_excerpt in DESCRIPTION_A


def test_valid_own_excerpt_is_accepted_and_request_contains_only_selected_profiles():
    profiles = [profile("a"), profile("not-selected", price_from_kzt=500_000)]
    request = query()
    response = match(profiles, request)
    client = FakeClient([selection("a", fragment_id("a"))])

    enriched = enrich(response, profiles, request, client)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["store"] is False
    assert call["text_format"] is ai_explain.QuoteBatch
    payload = json.loads(call["input"][1]["content"])
    assert [item["id"] for item in payload["selected_profiles"]] == ["a"]
    assert payload["selected_profiles"][0]["fragments"] == [
        {"id": fragment_id("a"), "text": DESCRIPTION_A.rstrip(".")}
    ]
    assert enriched.cards[0].explanation_source == "ai_selected"
    assert enriched.cards[0].evidence_excerpt == DESCRIPTION_A.rstrip(".")
    assert enriched.cards[0].facts.description_excerpt == DESCRIPTION_A.rstrip(".")
    assert DESCRIPTION_A.rstrip(".") in enriched.cards[0].explanation
    assert enriched.rejected == response.rejected


@pytest.mark.parametrize("invalid_fragment_id", [fragment_id("b"), "fabricated:f001"])
def test_foreign_or_fabricated_fragment_id_falls_back_for_its_card_only(invalid_fragment_id):
    profiles = [profile("a"), profile("b", description=DESCRIPTION_B)]
    request = query()
    response = match(profiles, request)
    client = FakeClient([
        selection("a", invalid_fragment_id),
        selection("b", fragment_id("b")),
    ])

    enriched = enrich(response, profiles, request, client)

    assert enriched.cards[0] == response.cards[0]
    assert enriched.cards[0].explanation_source == "template"
    assert DESCRIPTION_B.rstrip(".") not in enriched.cards[0].explanation
    assert enriched.cards[1].explanation_source == "ai_selected"
    assert enriched.cards[1].evidence_excerpt == DESCRIPTION_B.rstrip(".")


def test_unlisted_combined_sentence_id_falls_back_to_template():
    description = "Готовит сценарий с организатором. Проводит выездные церемонии на русском языке."
    profiles = [profile("a", description=description)]
    request = query()
    response = match(profiles, request)
    client = FakeClient([selection("a", "a:combined-sentences")])

    enriched = enrich(response, profiles, request, client)

    assert len(client.calls) == 1
    assert enriched.cards[0] == response.cards[0]
    assert enriched.cards[0].explanation_source == "template"
    assert enriched.cards[0].evidence_excerpt != description


def test_negative_and_conditional_fragments_keep_their_full_meaning():
    description = (
        "Не работает на русском языке. "
        "Работает на английском языке, только если переводчик предоставлен заказчиком."
    )
    candidate = profile("a", description=description)
    fragments = fragment_catalog(candidate)
    assert fragments == [
        {"fragment_id": fragment_id("a"), "text": "Не работает на русском языке"},
        {
            "fragment_id": fragment_id("a", 2),
            "text": "Работает на английском языке, только если переводчик предоставлен заказчиком",
        },
    ]
    assert not valid_excerpt("работает на русском языке", candidate)
    assert not valid_excerpt("Работает на английском языке", candidate)

    request = query()
    response = match([candidate], request)
    first = apply_fragment_choices(response, (candidate,), request, [selection("a", fragment_id("a"))])
    assert first.cards[0].evidence_excerpt == "Не работает на русском языке"
    assert "Не работает на русском языке" in first.cards[0].explanation
    second = apply_fragment_choices(response, (candidate,), request, [selection("a", fragment_id("a", 2))])
    assert "только если переводчик предоставлен заказчиком" in second.cards[0].evidence_excerpt


def test_model_supplied_text_is_rejected_even_with_valid_fragment_id():
    candidate = profile("a", description="Не работает на русском языке.")
    request = query()
    response = match([candidate], request)
    forged = {"id": "a", "fragment_id": fragment_id("a"), "excerpt": "работает на русском языке"}

    enriched = apply_fragment_choices(response, (candidate,), request, [forged])

    assert enriched is response


def test_foreign_fragment_cannot_be_applied_to_another_profile():
    candidates = [profile("a"), profile("b", description=DESCRIPTION_B)]
    request = query()
    response = match(candidates, request)

    enriched = apply_fragment_choices(
        response, tuple(candidates), request,
        [selection("a", fragment_id("b")), selection("b", fragment_id("b"))],
    )

    assert enriched.cards[0] == response.cards[0]
    assert enriched.cards[1].evidence_excerpt == DESCRIPTION_B.rstrip(".")
    assert enriched.cards[1].explanation_source == "ai_selected"


def test_long_fragment_is_omitted_instead_of_cutting_off_a_condition():
    description = "Работает на русском языке, " + "для важных мероприятий " * 20 + "только при наличии переводчика."
    candidate = profile("a", description=description)

    assert fragment_catalog(candidate) == []
    assert not valid_excerpt(description[:120].rstrip(), candidate)


def test_medium_fragment_preserves_its_final_condition():
    description = "Работает на русском языке, " + "для важных мероприятий " * 10 + "только при наличии переводчика."
    candidate = profile("a", description=description)

    assert fragment_catalog(candidate)[0]["text"] == description.rstrip(".")
    assert not valid_excerpt(description[:120].rstrip(), candidate)
    assert "только при наличии переводчика" in make_card(candidate, query()).explanation


@pytest.mark.parametrize("profile_id", ["HK-42352", "HK-26808"])
def test_real_catalog_long_paragraph_has_a_complete_own_excerpt(profile_id):
    candidate = next(item for item in load_profiles() if item.id == profile_id)

    card = make_card(candidate, query(budget_kzt=1_000_000))

    assert card.evidence_excerpt == candidate.description.rstrip(".!?")
    assert valid_excerpt(card.evidence_excerpt, candidate)
    assert "подробных сведений в описании нет" not in card.explanation
    assert card.evidence_excerpt in card.explanation


def test_nonempty_unselected_description_is_not_reported_missing():
    description = "Не проводит мероприятия без переводчика, " + "условия согласуются заранее " * 20
    candidate = profile("a", description=description)

    card = make_card(candidate, query())

    assert card.evidence_excerpt is None
    assert card.description == description
    assert "краткий фрагмент описания не выбран" in card.explanation
    assert "подробных сведений в описании нет" not in card.explanation


def test_extra_id_rejects_the_batch_without_changing_response():
    profiles = [profile("a")]
    request = query()
    response = match(profiles, request)
    client = FakeClient([
        selection("a", fragment_id("a")),
        selection("unknown", "unknown:f001"),
    ])

    enriched = enrich(response, profiles, request, client)

    assert enriched is response
    assert enriched.cards[0].explanation_source == "template"


@pytest.mark.parametrize("selections", [
    [selection("a", fragment_id("a")), selection("a", fragment_id("a")), selection("b", fragment_id("b"))],
    [selection("b", fragment_id("b"))],
])
def test_duplicate_or_missing_id_does_not_supply_an_unsafe_quote(selections):
    profiles = [profile("a"), profile("b", description=DESCRIPTION_B)]
    request = query()
    response = match(profiles, request)
    client = FakeClient(selections)

    enriched = enrich(response, profiles, request, client)

    assert enriched.cards[0] == response.cards[0]
    assert enriched.cards[1].explanation_source == "ai_selected"
    assert enriched.cards[1].evidence_excerpt == DESCRIPTION_B.rstrip(".")
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
        selection("b", fragment_id("b")),
        selection("a", fragment_id("a")),
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
    client = FakeClient([selection("empty", "empty:f001")])

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
        selection("empty", fragment_id("real")),
        selection("real", fragment_id("real")),
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
