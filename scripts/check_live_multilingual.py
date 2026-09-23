"""Opt-in six-turn live check for multilingual agent behavior; never prints secrets."""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import AsyncOpenAI

from app.agent import AgentSessionStore, agent_turn
from app.config import get_settings
from app.data import load_profiles
from app.matcher import match
from app.schemas import AgentTurnRequest, MatchRequest


class ObservedResponses:
    def __init__(self, responses):
        self.responses = responses
        self.events = []

    async def _call(self, method, kwargs):
        event = {"method": method}
        self.events.append(event)
        try:
            response = await getattr(self.responses, method)(**kwargs)
            event["status"] = getattr(response, "status", None)
            event["tools"] = [
                item.name for item in getattr(response, "output", [])
                if getattr(item, "type", None) == "function_call"
            ]
            return response
        except Exception as exc:
            event["error_type"] = type(exc).__name__
            event["http_status"] = getattr(exc, "status_code", None)
            raise

    async def create(self, **kwargs):
        return await self._call("create", kwargs)

    async def parse(self, **kwargs):
        return await self._call("parse", kwargs)


BASE = {"city": "Алматы", "category": "Ведущий", "event_format": "свадьба"}
CASES = [
    ("ru", "ru", "Нужен ведуший на свадьбу в Алматы, дата 2026-10-07. Бюжет до 1 000 000 ₸", "2026-10-07", 1_000_000),
    ("kk", "kk", "Алматыда 2026-10-07 күні үйлену тойына жүргізуші іздеймін. Бюджет 1 000 000 теңгеден аспасын", "2026-10-07", 1_000_000),
    ("en", "en", "Find an MC for a weddding in Almaty on 2026-10-07. My maximum budget is 1,000,000 KZT", "2026-10-07", 1_000_000),
    ("followup_date", "kk", "А если 10 октября?", "2026-10-10", 1_000_000),
    ("followup_budget", "en", "Снизим бюджет до 300 тысяч", "2026-10-10", 300_000),
    ("ambiguous_date", "ru", "Нужен ведущий на свадьбу в Алматы 07/10, бюджет 1 000 000 тенге", None, None),
]


async def main() -> int:
    settings = get_settings()
    if not settings.api_key or settings.mode != "auto":
        print("Live check requires local OPENAI_API_KEY and EXPLANATION_MODE=auto.")
        return 2
    profiles = load_profiles()
    sessions = AgentSessionStore()
    followup_session = None
    async with AsyncOpenAI(api_key=settings.api_key, timeout=8.5, max_retries=0) as sdk:
        observed = ObservedResponses(sdk.responses)
        client = type("ObservedClient", (), {"responses": observed})()
        for label, locale, message, expected_date, expected_budget in CASES:
            current_session = followup_session if label.startswith("followup_") else None
            first_event = len(observed.events)
            started = time.monotonic()
            result = await agent_turn(
                AgentTurnRequest(message=message, session_id=current_session),
                profiles, sessions, settings=settings, client=client, locale=locale,
            )
            elapsed = round(time.monotonic() - started, 3)
            if label == "en":
                followup_session = result.session_id
            if expected_date is None:
                passed = result.status == "clarification" and result.match is None
                expected = None
            else:
                expected_query = MatchRequest.model_validate({**BASE, "date": expected_date, "budget_kzt": expected_budget})
                expected = match(profiles, expected_query)
                actual = result.match
                passed = bool(
                    result.status == "matched" and result.tool_name == "match_contractors"
                    and result.parameters.model_dump(exclude_none=True)
                    == expected_query.model_dump(mode="json", exclude_none=True)
                    and actual and actual.outcome == expected.outcome
                    and actual.total_matches == expected.total_matches
                    and [card.id for card in actual.cards] == [card.id for card in expected.cards]
                )
            print(json.dumps({
                "case": label, "locale": locale, "model": settings.model,
                "status": result.status, "source": result.source,
                "tool": result.tool_name, "seconds": elapsed,
                "parameters": result.parameters.model_dump(exclude_none=True),
                "outcome": result.match.outcome if result.match else None,
                "total_matches": result.match.total_matches if result.match else None,
                "card_ids": [card.id for card in result.match.cards] if result.match else [],
                "api_events": observed.events[first_event:], "passed": passed,
            }, ensure_ascii=True), flush=True)
            if not passed:
                return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly allow up to twelve paid API calls")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to explicitly run paid API requests")
    raise SystemExit(asyncio.run(main()))
