"""Диалоговый агент: решения модели не могут менять результат подбора."""

import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import agent
from app.agent import AgentSessionStore, agent_turn
from app.config import ExplanationSettings
from app.data import load_profiles
from app.main import app
from app.matcher import match
from app.schemas import AgentTurnRequest, MatchRequest, Profile


SETTINGS = ExplanationSettings(mode="auto", api_key="fake-key", model="gpt-6-sol")
FIELDS = ("city", "date", "event_format", "category", "budget_kzt", "language", "hours")
COMPLETE = {
    "city": "Алматы", "date": "2026-10-07", "event_format": "свадьба",
    "category": "Ведущий", "budget_kzt": 300_000,
}
COMPLETE_MESSAGE = "Нужен ведущий на свадьбу в Алматы 7 октября, бюджет 300000"
COMPLETE_EVIDENCE = {
    "city": "Алматы", "date": "7 октября", "event_format": "свадьбу",
    "category": "ведущий", "budget_kzt": "бюджет 300000",
}


def profile(profile_id: str, *, category: str = "Ведущий", city: str = "Алматы",
            price: int = 100_000, busy_dates=()) -> Profile:
    return Profile(
        id=profile_id, anon_name=f"Профиль {profile_id}", categories=(category,),
        city=city, city_imputed=False, synthetic=False,
        price_from_kzt=price, price_imputed=False,
        event_formats=("свадьба",), languages=("русский",), max_hours=6,
        busy_dates=busy_dates,
        description="Проводит церемонии и составляет сценарий вместе с организатором.",
        provenance="original_csv",
    )


@pytest.fixture
def profiles() -> tuple[Profile, ...]:
    return (
        profile("b", price=120_000),
        profile("a", price=100_000, busy_dates=(date(2026, 10, 10),)),
        profile("decor", category="Декоратор", city="Астана"),
    )


def tool(name="match_contractors", *, evidence=None, **changes):
    values = {field: changes.get(field) for field in FIELDS}
    cited = {field: (evidence or {}).get(field) for field in FIELDS}
    return SimpleNamespace(
        status="completed",
        output=[SimpleNamespace(
            type="function_call", name=name, call_id="test-call",
            arguments=json.dumps({"changes": values, "evidence": cited}, ensure_ascii=False),
        )],
    )


class FakeResponses:
    def __init__(self, *tool_results, parse_error=None, parse_delay=0,
                 parse_output=None):
        self.responses = self
        self.tool_results = list(tool_results)
        self.create_calls = []
        self.parse_calls = []
        self.parse_error = parse_error
        self.parse_delay = parse_delay
        self.parse_output = parse_output

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self.tool_results.pop(0)

    async def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        if self.parse_delay:
            await asyncio.sleep(self.parse_delay)
        if self.parse_error:
            raise self.parse_error
        if self.parse_output is not None:
            parsed = self.parse_output
        else:
            output = json.loads(kwargs["input"][-1]["output"])
            parsed = {"selections": [
                {
                    "id": card["id"],
                    "fragment_id": card["fragments"][0]["fragment_id"]
                    if card["fragments"] else None,
                }
                for card in output["cards"]
            ]}
        return SimpleNamespace(status="completed", output_parsed=parsed)


def turn(message: str, profiles: tuple[Profile, ...], sessions: AgentSessionStore,
         client: FakeResponses, session_id=None, settings=SETTINGS):
    return asyncio.run(agent_turn(
        AgentTurnRequest(message=message, session_id=session_id),
        profiles, sessions, settings=settings, client=client,
    ))


def direct(profiles, **changes):
    return match(profiles, MatchRequest(**(COMPLETE | changes)))


def assert_match_untouched(actual, expected):
    assert actual is not None
    for field in ("outcome", "total_matches", "primary_reason_counts", "rejected",
                  "excluded_by_date", "message"):
        assert getattr(actual, field) == getattr(expected, field)
    assert [card.id for card in actual.cards] == [card.id for card in expected.cards]
    for selected, original in zip(actual.cards, expected.cards):
        assert selected.anon_name == original.anon_name
        assert selected.price_from_kzt == original.price_from_kzt
        assert selected.rank_score == original.rank_score
        assert selected.rank_factors == original.rank_factors
        assert selected.facts.model_dump(exclude={"description_excerpt"}) == original.facts.model_dump(exclude={"description_excerpt"})


def test_complete_turn_calls_real_matcher_and_only_uses_own_fragments(profiles):
    client = FakeResponses(tool(evidence=COMPLETE_EVIDENCE, **COMPLETE))
    result = turn(COMPLETE_MESSAGE, profiles,
                  AgentSessionStore(), client)

    assert result.status == "matched"
    assert result.tool_name == "match_contractors"
    assert result.source == "ai"
    assert_match_untouched(result.match, direct(profiles))
    assert len(client.create_calls) == len(client.parse_calls) == 1
    assert client.create_calls[0]["tool_choice"] == "required"
    assert client.create_calls[0]["parallel_tool_calls"] is False
    assert client.create_calls[0]["store"] is False
    assert client.parse_calls[0]["store"] is False
    assert all(card.explanation_source == "ai_selected" for card in result.match.cards)
    assert all(card.evidence_excerpt in card.description for card in result.match.cards)


def test_incomplete_turn_clarifies_without_running_match(monkeypatch, profiles):
    def forbidden_match(*_args, **_kwargs):
        raise AssertionError("match must not run for incomplete parameters")

    monkeypatch.setattr(agent, "match", forbidden_match)
    client = FakeResponses(tool("request_clarification", evidence={"city": "Алматы"}, city="Алматы"))
    result = turn("Мероприятие в Алматы", profiles, AgentSessionStore(), client)

    assert result.status == "clarification"
    assert result.match is None
    assert result.parameters.city == "Алматы"
    assert result.parameters.category is None
    assert len(client.create_calls) == 1
    assert client.parse_calls == []


def test_no_recognized_fields_suggests_manual_form_without_match(monkeypatch, profiles):
    def forbidden_match(*_args, **_kwargs):
        raise AssertionError("match must not run without recognized parameters")

    monkeypatch.setattr(agent, "match", forbidden_match)
    client = FakeResponses(tool("request_clarification"))
    result = turn("Помогите найти что-нибудь", profiles, AgentSessionStore(), client)

    assert result.status == "clarification"
    assert result.match is None
    assert all(getattr(result.parameters, field) is None for field in FIELDS)
    assert "формой" in result.message.lower()
    assert client.parse_calls == []


def test_unknown_catalog_category_clarifies_without_running_match(monkeypatch, profiles):
    def forbidden_match(*_args, **_kwargs):
        raise AssertionError("match must not run for an unknown category")

    monkeypatch.setattr(agent, "match", forbidden_match)
    client = FakeResponses(tool(
        evidence=COMPLETE_EVIDENCE | {"category": "музыка"},
        **(COMPLETE | {"category": "Музыка"}),
    ))
    result = turn("Нужна музыка на свадьбу 7 октября в Алматы, бюджет 300000",
                  profiles, AgentSessionStore(), client)

    assert result.status == "clarification"
    assert result.match is None
    assert result.parameters.city == "Алматы"
    assert result.parameters.date == "2026-10-07"
    assert result.parameters.event_format == "свадьба"
    assert result.parameters.budget_kzt == 300_000
    assert result.parameters.category is None
    assert client.parse_calls == []


def test_multiple_unknown_catalog_values_are_all_rejected(monkeypatch, profiles):
    def forbidden_match(*_args, **_kwargs):
        raise AssertionError("match must not run for unknown catalog values")

    monkeypatch.setattr(agent, "match", forbidden_match)
    client = FakeResponses(tool(
        evidence=COMPLETE_EVIDENCE | {
            "city": "Несуществующий город", "category": "неизвестная категория",
        },
        **(COMPLETE | {"city": "Несуществующий город", "category": "Неизвестная категория"}),
    ))
    result = turn("Несуществующий город, неизвестная категория на свадьбу 7 октября, бюджет 300000",
                  profiles, AgentSessionStore(), client)

    assert result.status == "clarification"
    assert result.match is None
    assert result.parameters.city is None
    assert result.parameters.category is None
    assert result.parameters.date == "2026-10-07"
    assert result.parameters.budget_kzt == 300_000
    assert "город" in result.message
    assert "категорию" in result.message


def test_followup_preserves_parameters_then_changes_date_and_budget(profiles):
    client = FakeResponses(
        tool("request_clarification", evidence={"city": "Алматы", "category": "Ведущий"},
             city="Алматы", category="Ведущий"),
        tool(evidence={"date": "7 октября", "event_format": "Свадьба", "budget_kzt": "бюджет 300000"},
             date="2026-10-07", event_format="свадьба", budget_kzt=300_000),
        tool(evidence={"date": "10 октября"}, date="2026-10-10"),
        tool(evidence={"budget_kzt": "Бюджет теперь 50000"}, budget_kzt=50_000),
    )
    sessions = AgentSessionStore()
    first = turn("Ведущий в Алматы", profiles, sessions, client)
    second = turn("Свадьба 7 октября, бюджет 300000", profiles, sessions, client,
                  first.session_id)
    third = turn("А на 10 октября?", profiles, sessions, client, first.session_id)
    fourth = turn("Бюджет теперь 50000", profiles, sessions, client, first.session_id)

    assert first.status == "clarification"
    assert second.status == third.status == fourth.status == "matched"
    assert all(item.session_id == first.session_id for item in (second, third, fourth))
    assert_match_untouched(second.match, direct(profiles))
    assert_match_untouched(third.match, direct(profiles, date="2026-10-10"))
    assert_match_untouched(fourth.match, direct(profiles, date="2026-10-10", budget_kzt=50_000))
    assert third.parameters.city == fourth.parameters.city == "Алматы"
    assert third.parameters.category == fourth.parameters.category == "Ведущий"
    assert fourth.parameters.date == "2026-10-10"
    assert fourth.parameters.budget_kzt == 50_000
    assert len(client.parse_calls) == 3
    second_prompt = json.loads(client.create_calls[1]["input"][1]["content"])
    assert second_prompt["current_parameters"]["city"] == "Алматы"
    assert second_prompt["current_parameters"]["category"] == "Ведущий"


def test_real_catalog_three_turn_demo_uses_matcher_and_keeps_context():
    catalog = load_profiles()
    client = FakeResponses(
        tool(evidence=COMPLETE_EVIDENCE | {
            "event_format": "свадьбу", "date": "7 октября 2026 года", "budget_kzt": "миллиона",
        }, **(COMPLETE | {"budget_kzt": 1_000_000})),
        tool(evidence={"date": "10 октября"}, date="2026-10-10"),
        tool(evidence={"budget_kzt": "300 тысяч"}, budget_kzt=300_000),
    )
    sessions = AgentSessionStore()
    first = turn(
        "Нужен ведущий в Алматы на свадьбу 7 октября 2026 года, бюджет до миллиона тенге",
        catalog, sessions, client,
    )
    second = turn("А если 10 октября?", catalog, sessions, client, first.session_id)
    third = turn("Снизим бюджет до 300 тысяч", catalog, sessions, client, first.session_id)

    assert all(item.status == "matched" for item in (first, second, third))
    assert all(item.tool_name == "match_contractors" for item in (first, second, third))
    assert all(item.session_id == first.session_id for item in (second, third))
    assert_match_untouched(first.match, direct(catalog, budget_kzt=1_000_000))
    assert_match_untouched(second.match, direct(catalog, budget_kzt=1_000_000, date="2026-10-10"))
    assert_match_untouched(third.match, direct(catalog, budget_kzt=300_000, date="2026-10-10"))
    assert (first.match.outcome, first.match.total_matches, len(first.match.cards)) == ("matched", 5, 3)
    assert (second.match.outcome, second.match.total_matches, len(second.match.cards)) == ("matched", 2, 2)
    assert (third.match.outcome, third.match.total_matches, len(third.match.cards)) == ("all_filtered", 0, 0)
    assert first.source == second.source == third.source == "ai"
    assert second.parameters.budget_kzt == 1_000_000
    assert third.parameters.date == "2026-10-10"
    assert len(client.create_calls) == len(client.parse_calls) == 3


@pytest.mark.parametrize("changes", [
    COMPLETE,
    COMPLETE | {"category": "Декоратор"},
    COMPLETE | {"budget_kzt": 50_000},
])
def test_three_match_outcomes_are_identical_to_direct_match(profiles, changes):
    category = changes["category"].lower()
    budget = changes["budget_kzt"]
    message = f"Нужен {category} на свадьбу в Алматы 7 октября, бюджет {budget}"
    evidence = COMPLETE_EVIDENCE | {"category": category, "budget_kzt": f"бюджет {budget}"}
    client = FakeResponses(tool(evidence=evidence, **changes))
    result = turn(message, profiles, AgentSessionStore(), client)
    expected = match(profiles, MatchRequest(**changes))

    assert result.status == "matched"
    assert_match_untouched(result.match, expected)
    assert len(result.match.cards) <= 3
    assert len(client.parse_calls) == 1


@pytest.mark.parametrize("message, changes, evidence, rejected_field", [
    ("Подберите подрядчика", COMPLETE, COMPLETE_EVIDENCE, "city"),
    (COMPLETE_MESSAGE, COMPLETE, COMPLETE_EVIDENCE | {"city": "Нужен"}, "city"),
    (COMPLETE_MESSAGE, COMPLETE | {"date": "2026-10-10"}, COMPLETE_EVIDENCE, "date"),
    (COMPLETE_MESSAGE, COMPLETE | {"budget_kzt": 1_000_000}, COMPLETE_EVIDENCE, "budget_kzt"),
])
def test_unsupported_model_changes_cannot_run_match(
    monkeypatch, profiles, message, changes, evidence, rejected_field,
):
    def forbidden_match(*_args, **_kwargs):
        raise AssertionError("matcher must not run with unsupported changes")

    monkeypatch.setattr(agent, "match", forbidden_match)
    client = FakeResponses(tool(evidence=evidence, **changes))
    result = turn(message, profiles, AgentSessionStore(), client)

    assert result.status == "clarification"
    assert result.match is None
    assert getattr(result.parameters, rejected_field) is None
    assert len(client.create_calls) == 1
    assert client.parse_calls == []


def test_unsupported_followup_date_preserves_confirmed_date(profiles):
    client = FakeResponses(
        tool(evidence=COMPLETE_EVIDENCE, **COMPLETE),
        tool(evidence={"date": "10 октября"}, date="2026-10-07"),
    )
    sessions = AgentSessionStore()
    first = turn(COMPLETE_MESSAGE, profiles, sessions, client)
    second = turn("А если 10 октября?", profiles, sessions, client, first.session_id)

    assert first.status == "matched"
    assert second.status == "clarification"
    assert second.match is None
    assert second.parameters.date == "2026-10-07"
    assert len(client.parse_calls) == 1


@pytest.mark.parametrize("message, changed_field, value, span", [
    ("Мероприятие 7 октября 2026 года", "budget_kzt", 2026, "2026"),
    ("Мероприятие 7 октября", "hours", 7, "7 октября"),
])
def test_date_numbers_do_not_become_budget_or_hours(profiles, message, changed_field, value, span):
    client = FakeResponses(tool(evidence={changed_field: span}, **{changed_field: value}))
    result = turn(message, profiles, AgentSessionStore(), client)
    assert result.status == "clarification"
    assert getattr(result.parameters, changed_field) is None
    assert result.match is None


@pytest.mark.parametrize("amount, amount_span, budget", [
    ("1,5 млн тенге", "1,5 млн", 1_500_000),
    ("1.5 миллиона", "1.5 миллиона", 1_500_000),
    ("2 миллиона", "2 миллиона", 2_000_000),
    ("два миллиона", "два миллиона", 2_000_000),
    ("триста пятьдесят тысяч", "триста пятьдесят тысяч", 350_000),
    ("полмиллиона", "полмиллиона", 500_000),
])
def test_spoken_or_decimal_budget_is_grounded_before_matching(profiles, amount, amount_span, budget):
    message = f"Нужен ведущий на свадьбу в Алматы 7 октября, бюджет {amount}"
    client = FakeResponses(tool(
        evidence=COMPLETE_EVIDENCE | {"budget_kzt": amount_span},
        **(COMPLETE | {"budget_kzt": budget}),
    ))
    result = turn(message, profiles, AgentSessionStore(), client)
    assert result.status == "matched"
    assert result.parameters.budget_kzt == budget
    assert_match_untouched(result.match, direct(profiles, budget_kzt=budget))


@pytest.mark.parametrize("amount, amount_span, invented_budget", [
    ("2 миллиона", "2 миллиона", 1_000_000),
    ("2 миллиона", "миллиона", 1_000_000),
    ("два миллиона", "миллиона", 1_000_000),
    ("1,5 млн", "5 млн", 5_000_000),
    ("1.5 млн", "5 млн", 5_000_000),
])
def test_partial_quote_cannot_change_numeric_magnitude(profiles, amount, amount_span, invented_budget):
    message = f"Нужен ведущий на свадьбу в Алматы 7 октября, бюджет {amount}"
    client = FakeResponses(tool(
        evidence=COMPLETE_EVIDENCE | {"budget_kzt": amount_span},
        **(COMPLETE | {"budget_kzt": invented_budget}),
    ))
    result = turn(message, profiles, AgentSessionStore(), client)
    assert result.status == "clarification"
    assert result.parameters.budget_kzt is None
    assert result.match is None
    assert client.parse_calls == []


def test_number_only_reply_answers_pending_budget_question(profiles):
    initial = {key: value for key, value in COMPLETE.items() if key != "budget_kzt"}
    client = FakeResponses(
        tool("request_clarification", evidence=COMPLETE_EVIDENCE, **initial),
        tool(evidence={"budget_kzt": "300000"}, budget_kzt=300_000),
    )
    sessions = AgentSessionStore()
    first = turn("Нужен ведущий на свадьбу в Алматы 7 октября", profiles, sessions, client)
    assert first.status == "clarification"
    assert "бюджет" in first.message.lower()
    second = turn("300000", profiles, sessions, client, first.session_id)
    assert second.status == "matched"
    assert_match_untouched(second.match, direct(profiles))


def test_broad_evidence_cannot_use_event_day_as_budget(profiles):
    client = FakeResponses(tool(
        evidence=COMPLETE_EVIDENCE | {"budget_kzt": COMPLETE_MESSAGE},
        **(COMPLETE | {"budget_kzt": 7}),
    ))
    result = turn(COMPLETE_MESSAGE, profiles, AgentSessionStore(), client)
    assert result.status == "clarification"
    assert result.parameters.budget_kzt is None
    assert result.match is None


def test_similar_word_prefix_cannot_select_different_category():
    catalog = (profile("booth", category="Фото и видеобудки"),)
    client = FakeResponses(tool(
        evidence=COMPLETE_EVIDENCE | {"category": "фотограф и видеограф"},
        **(COMPLETE | {"category": "Фото и видеобудки"}),
    ))
    result = turn("Нужен фотограф и видеограф на свадьбу в Алматы 7 октября, бюджет 300000",
                  catalog, AgentSessionStore(), client)
    assert result.status == "clarification"
    assert result.parameters.category is None
    assert result.match is None


@pytest.mark.parametrize("category_phrase", ["ведущего", "тамаду"])
def test_ordinary_category_word_forms_keep_working(profiles, category_phrase):
    client = FakeResponses(tool(
        evidence=COMPLETE_EVIDENCE | {"category": category_phrase}, **COMPLETE,
    ))
    result = turn(f"Ищу {category_phrase} на свадьбу в Алматы 7 октября, бюджет 300000",
                  profiles, AgentSessionStore(), client)
    assert result.status == "matched"
    assert_match_untouched(result.match, direct(profiles))


@pytest.mark.parametrize("response", [
    tool("delete_database", **COMPLETE),
    SimpleNamespace(status="completed", output=[SimpleNamespace(
        type="function_call", name="match_contractors", call_id="call-1",
        arguments='{"changes":{"city":"Алматы","budget_kzt":-1}}',
    )]),
    SimpleNamespace(status="completed", output=[]),
])
def test_unknown_tool_or_invalid_arguments_cannot_run_match(response, profiles):
    client = FakeResponses(response)
    result = turn("Подберите", profiles, AgentSessionStore(), client)
    assert result.status == "error"
    assert result.match is None
    assert client.parse_calls == []


def test_model_supplied_card_edits_fail_and_real_cards_survive(profiles):
    client = FakeResponses(
        tool(evidence=COMPLETE_EVIDENCE, **COMPLETE),
        parse_output={"selections": [
            {"id": "a", "fragment_id": "a:f001", "price_from_kzt": 1},
        ]},
    )
    result = turn(COMPLETE_MESSAGE, profiles, AgentSessionStore(), client)
    expected = direct(profiles)
    assert result.status == "matched"
    assert result.source == "template"
    assert result.match == expected


@pytest.mark.parametrize("problem", ["failure", "timeout"])
def test_second_call_failure_or_timeout_keeps_real_template_cards(monkeypatch, profiles, problem):
    if problem == "timeout":
        monkeypatch.setattr(agent, "AGENT_DEADLINE_SECONDS", 0.01)
        client = FakeResponses(tool(evidence=COMPLETE_EVIDENCE, **COMPLETE), parse_delay=0.1)
    else:
        client = FakeResponses(tool(evidence=COMPLETE_EVIDENCE, **COMPLETE),
                               parse_error=RuntimeError("secret-like upstream error"))
    result = turn(COMPLETE_MESSAGE, profiles, AgentSessionStore(), client)

    assert result.status == "matched"
    assert result.source == "template"
    assert result.match == direct(profiles)
    assert len(client.parse_calls) == 1
    assert "upstream" not in result.message


def test_deadline_includes_waiting_for_session_lock(monkeypatch, profiles):
    monkeypatch.setattr(agent, "AGENT_DEADLINE_SECONDS", 0.01)
    sessions = AgentSessionStore()
    session = sessions.get_or_create(None)
    client = FakeResponses()

    async def blocked_turn():
        async with session.lock:
            return await agent_turn(
                AgentTurnRequest(message=COMPLETE_MESSAGE, session_id=session.session_id),
                profiles, sessions, settings=SETTINGS, client=client,
            )

    result = asyncio.run(blocked_turn())
    assert result.status == "error"
    assert session.history == []
    assert client.create_calls == []


@pytest.mark.parametrize("settings", [
    ExplanationSettings(mode="auto", api_key=None),
    ExplanationSettings(mode="template", api_key="fake-key"),
])
def test_no_key_or_template_mode_never_calls_model(profiles, settings):
    client = FakeResponses()
    result = turn("Подберите", profiles, AgentSessionStore(), client, settings=settings)
    assert result.status == "unavailable"
    assert result.match is None
    assert result.source == "unavailable"
    assert client.create_calls == client.parse_calls == []


def test_unknown_session_id_starts_isolated_dialogue(profiles):
    sessions = AgentSessionStore()
    client = FakeResponses(
        tool("request_clarification", evidence={"city": "Алматы"}, city="Алматы"),
        tool("request_clarification", evidence={"category": "Ведущий"}, category="Ведущий"),
    )
    first = turn("Алматы", profiles, sessions, client)
    other = turn("Ведущий", profiles, sessions, client, session_id="unknown-session")
    assert first.session_id != other.session_id
    assert other.parameters.city is None
    assert other.parameters.category == "Ведущий"


def test_agent_message_schema_and_http_validation():
    for message in ("", "   ", "x" * 701):
        with pytest.raises(ValidationError):
            AgentTurnRequest(message=message)

    with TestClient(app) as client:
        assert client.post("/api/agent", json={"message": "   "}).status_code == 422
        assert client.post("/api/agent", json={"message": "x" * 701}).status_code == 422
        assert client.post("/api/agent", json={"message": "Привет"}).json()["status"] == "unavailable"


@pytest.mark.parametrize("locale, message, evidence", [
    ("ru", "Нужен ведуший на свадьбу в Алматы, дата 2026-10-07. Бюджет до 1 000 000 ₸", {
        "city": "Алматы", "category": "ведуший", "event_format": "свадьбу",
        "date": "2026-10-07", "budget_kzt": "1 000 000 ₸",
    }),
    ("kk", "Алматыда 2026-10-07 күні өтетін үйлену тойына жүргізуші іздеймін. Бюджет 1 000 000 теңгеден аспасын", {
        "city": "Алматыда", "category": "жүргізуші", "event_format": "үйлену тойына",
        "date": "2026-10-07", "budget_kzt": "1 000 000 теңгеден",
    }),
    ("kk", "Almaty қаласында 2026-10-07 күні үйлену тойына жүргзуші керек. Бюджет ең көбі 1000000 KZT", {
        "city": "Almaty", "category": "жүргзуші", "event_format": "үйлену тойына",
        "date": "2026-10-07", "budget_kzt": "1000000 KZT",
    }),
    ("en", "Find an MC for a weddding in Almaty on 2026-10-07. My maximum budget is 1,000,000 KZT", {
        "city": "Almaty", "category": "MC", "event_format": "weddding",
        "date": "2026-10-07", "budget_kzt": "1,000,000 KZT",
    }),
    ("en", "I need an event hsot for a wedding in Алматы on 2026-10-07, up to 1000000 KZT", {
        "city": "Алматы", "category": "event hsot", "event_format": "wedding",
        "date": "2026-10-07", "budget_kzt": "1000000 KZT",
    }),
])
def test_multilingual_typo_examples_keep_canonical_match(profiles, locale, message, evidence):
    conditions = COMPLETE | {"budget_kzt": 1_000_000}
    client = FakeResponses(tool(evidence=evidence, **conditions))
    result = asyncio.run(agent_turn(
        AgentTurnRequest(message=message), profiles, AgentSessionStore(),
        settings=SETTINGS, client=client, locale=locale,
    ))
    assert result.status == "matched"
    assert result.parameters.model_dump(exclude_none=True) == conditions
    assert result.parameters.language is None
    expected = direct(profiles, budget_kzt=1_000_000)
    assert result.match.outcome == expected.outcome
    assert result.match.total_matches == expected.total_matches
    assert [card.id for card in result.match.cards] == [card.id for card in expected.cards]
    assert [card.price_from_kzt for card in result.match.cards] == [card.price_from_kzt for card in expected.cards]
    assert result.normalizations
    assert len(client.create_calls) == len(client.parse_calls) == 1


def test_ambiguous_slash_date_clarifies_without_changing_confirmed_date(profiles):
    client = FakeResponses(
        tool(evidence=COMPLETE_EVIDENCE, **COMPLETE),
        tool(evidence={"date": "07/10"}, date="2026-10-07"),
    )
    sessions = AgentSessionStore()
    first = turn(COMPLETE_MESSAGE, profiles, sessions, client)
    second = turn("А если 07/10?", profiles, sessions, client, first.session_id)
    assert first.status == "matched"
    assert second.status == "clarification"
    assert "07/10" in second.message
    assert second.parameters.date == "2026-10-07"
    assert second.match is None


def test_bare_toi_stays_toi_and_does_not_become_wedding(profiles):
    assert agent._same_catalog_value("той", "той", "event_format")
    assert not agent._same_catalog_value("свадьба", "той", "event_format")
    assert agent._same_catalog_value("свадьба", "үйлену тойына", "event_format")


def test_localized_clarification_does_not_turn_ui_language_into_service_filter(profiles):
    client = FakeResponses(tool("request_clarification", evidence={"city": "Almaty"}, city="Алматы"))
    result = asyncio.run(agent_turn(
        AgentTurnRequest(message="Almaty"), profiles, AgentSessionStore(),
        settings=SETTINGS, client=client, locale="en",
    ))
    assert result.status == "clarification"
    assert result.message.startswith("Which contractor category")
    assert result.parameters.language is None
    assert result.normalizations == [{"field": "city", "input": "Almaty", "canonical": "Алматы"}]


def test_english_input_with_kazakh_ui_keeps_service_language_unset(profiles):
    message = "Find an MC for a weddding in Almaty on 2026-10-07. My maximum budget is 1,000,000 KZT"
    evidence = {
        "city": "Almaty", "category": "MC", "event_format": "weddding",
        "date": "2026-10-07", "budget_kzt": "1,000,000 KZT",
    }
    client = FakeResponses(tool(evidence=evidence, **(COMPLETE | {"budget_kzt": 1_000_000})))
    result = asyncio.run(agent_turn(
        AgentTurnRequest(message=message), profiles, AgentSessionStore(),
        settings=SETTINGS, client=client, locale="kk",
    ))
    assert result.status == "matched"
    assert result.parameters.language is None
    assert result.parameters.city == "Алматы"
    assert result.parameters.category == "Ведущий"
    assert result.parameters.event_format == "свадьба"
    assert result.match.total_matches == direct(profiles, budget_kzt=1_000_000).total_matches
    assert "профиль" in result.message


@pytest.mark.parametrize("canonical, fragment, field", [
    ("Алматы", "  aLmAtY  ", "city"),
    ("Ведущий", "  EVENT   HSOT  ", "category"),
    ("свадьба", "  WeDDDinG  ", "event_format"),
])
def test_catalog_evidence_tolerates_case_and_extra_spaces(canonical, fragment, field):
    assert agent._same_catalog_value(canonical, fragment, field)


@pytest.mark.parametrize("amount, correct, wrong, clipped", [
    ("500,000 KZT", 500_000, 500, "500"),
    ("300,000 KZT", 300_000, 300, "300"),
    ("300 thousand KZT", 300_000, 300, "300"),
    ("1.5 million KZT", 1_500_000, 1_000_000, "million"),
    ("1,5 млн тенге", 1_500_000, 5_000_000, "5 млн"),
    ("300 мың теңге", 300_000, 300, "300"),
    ("1 000 000 ₸", 1_000_000, 1_000, "1 000"),
    ("1,000,000 KZT", 1_000_000, 1_000, "1,000"),
])
def test_entire_budget_quantity_is_grounded(amount, correct, wrong, clipped):
    message = f"Budget {amount}"
    assert agent._same_number(correct, amount, budget=True, message=message)
    assert not agent._same_number(wrong, clipped, budget=True, message=message)


@pytest.mark.parametrize("amount, correct, wrong, clipped", [
    ("500,000 KZT", 500_000, 500, "500"),
    ("300 thousand KZT", 300_000, 300, "300"),
])
def test_english_amount_cannot_be_truncated_in_agent_turn(profiles, amount, correct, wrong, clipped):
    message = f"MC for a wedding in Almaty on 2026-10-07, budget {amount}"
    evidence = {
        "city": "Almaty", "category": "MC", "event_format": "wedding",
        "date": "2026-10-07", "budget_kzt": amount,
    }
    right = turn(message, profiles, AgentSessionStore(), FakeResponses(tool(
        evidence=evidence, **(COMPLETE | {"budget_kzt": correct}),
    )))
    assert right.status == "matched"
    assert right.parameters.budget_kzt == correct

    wrong_client = FakeResponses(tool(
        evidence=evidence | {"budget_kzt": clipped},
        **(COMPLETE | {"budget_kzt": wrong}),
    ))
    rejected = turn(message, profiles, AgentSessionStore(), wrong_client)
    assert rejected.status == "clarification"
    assert rejected.parameters.budget_kzt is None
    assert rejected.match is None
    assert wrong_client.parse_calls == []


@pytest.mark.parametrize("message, fragment, valid", [
    ("Мероприятие 7 октября 2027 года", "7 октября", False),
    ("2027 жылғы 7 қазанда іс-шара", "7 қазанда", False),
    ("Event 7 October 2027", "7 October", False),
    ("Мероприятие 7 октября 2026 года", "7 октября", True),
    ("2026 жылғы 7 қазанда іс-шара", "7 қазанда", True),
    ("Event 7 October 2026", "7 October", True),
])
def test_explicit_year_survives_truncated_date_evidence(message, fragment, valid):
    assert agent._same_date("2026-10-07", fragment, message) is valid


@pytest.mark.parametrize("locale, message, fragment", [
    ("ru", "Мероприятие 7 октября 2027 года", "7 октября"),
    ("kk", "2027 жылғы 7 қазанда іс-шара", "7 қазанда"),
    ("en", "Event 7 October 2027", "7 October"),
])
def test_explicit_2027_cannot_be_rewritten_as_2026(locale, message, fragment, profiles):
    client = FakeResponses(tool(evidence={"date": fragment}, date="2026-10-07"))
    result = asyncio.run(agent_turn(
        AgentTurnRequest(message=message), profiles, AgentSessionStore(),
        settings=SETTINGS, client=client, locale=locale,
    ))
    assert result.status == "clarification"
    assert result.parameters.date is None
    assert result.match is None
    assert client.parse_calls == []


@pytest.mark.parametrize("locale, message", [
    ("ru", "Нужен ведущий на свадьбу в Алматы 7 октября 2027, бюджет 300000 тенге"),
    ("kk", "Алматыда 2027 жылғы 7 қазанда үйлену тойына жүргізуші керек, бюджет 300000 теңге"),
    ("en", "MC for a wedding in Almaty on 7 October 2027, budget 300 thousand KZT"),
])
def test_model_proposed_out_of_calendar_year_gets_clear_clarification(locale, message, profiles):
    client = FakeResponses(tool(evidence={"date": "7 October 2027"}, date="2027-10-07"))
    result = asyncio.run(agent_turn(
        AgentTurnRequest(message=message), profiles, AgentSessionStore(),
        settings=SETTINGS, client=client, locale=locale,
    ))
    assert result.status == "clarification"
    assert result.source == "template"
    assert "2026" in result.message
    assert result.parameters.date is None
    assert result.match is None
    assert client.parse_calls == []


def test_other_invalid_tool_arguments_remain_errors(profiles):
    client = FakeResponses(tool(evidence={"budget_kzt": "-1"}, budget_kzt=-1))
    result = turn("Бюджет -1", profiles, AgentSessionStore(), client)
    assert result.status == "error"
    assert result.match is None


@pytest.mark.parametrize("fragment, expected", [
    ("Астанада", True),
    ("Астанадағы", True),
    ("Астанаға", True),
    ("Алматыда", True),
    ("Алматыдағы", True),
    ("Астаналық", False),
    ("Астанадай", False),
])
def test_kazakh_city_forms_are_bounded(fragment, expected):
    canonical = "Алматы" if fragment.startswith("Алматы") else "Астана"
    assert agent._same_catalog_value(canonical, fragment, "city") is expected


def test_florist_in_astana_with_kazakh_city_form(profiles):
    catalog = (*profiles, profile("floral", category="Флорист", city="Астана"))
    message = "Астанадағы 2026-10-07 күнгі үйлену тойына флорист керек. Бюджет 500 000 теңге"
    client = FakeResponses(tool(evidence={
        "city": "Астанадағы", "date": "2026-10-07",
        "event_format": "үйлену тойына", "category": "флорист",
        "budget_kzt": "500 000 теңге",
    }, city="Астана", date="2026-10-07", event_format="свадьба",
        category="Флорист", budget_kzt=500_000))
    result = asyncio.run(agent_turn(
        AgentTurnRequest(message=message), catalog, AgentSessionStore(),
        settings=SETTINGS, client=client, locale="kk",
    ))
    assert result.status == "matched"
    assert result.parameters.city == "Астана"
    assert [card.id for card in result.match.cards] == ["floral"]
