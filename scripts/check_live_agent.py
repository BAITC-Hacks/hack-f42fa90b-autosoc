"""Opt-in live smoke: three real agent turns, no secret or raw SDK error output."""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import replace
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
            result = await getattr(self.responses, method)(**kwargs)
            event["status"] = getattr(result, "status", None)
            event["tools"] = [
                item.name for item in getattr(result, "output", [])
                if getattr(item, "type", None) == "function_call"
            ]
            return result
        except Exception as exc:
            event["error_type"] = type(exc).__name__
            event["http_status"] = getattr(exc, "status_code", None)
            raise

    async def create(self, **kwargs):
        return await self._call("create", kwargs)

    async def parse(self, **kwargs):
        return await self._call("parse", kwargs)


async def main(model):
    settings = get_settings()
    if model:
        settings = replace(settings, model=model)
    if not settings.api_key or settings.mode != "auto":
        print("Live check requires local OPENAI_API_KEY and EXPLANATION_MODE=auto.")
        return 2
    profiles = load_profiles()
    sessions = AgentSessionStore()
    session_id = None
    base = {"city": "Алматы", "category": "Ведущий", "event_format": "свадьба"}
    cases = [
        ("Нужен ведущий в Алматы на свадьбу 7 октября 2026 года, бюджет до миллиона тенге", "2026-10-07", 1000000),
        ("А если 10 октября?", "2026-10-10", 1000000),
        ("Снизим бюджет до 300 тысяч", "2026-10-10", 300000),
    ]
    async with AsyncOpenAI(api_key=settings.api_key, timeout=6.5, max_retries=0) as sdk:
        observed = ObservedResponses(sdk.responses)
        wrapper = type("ObservedClient", (), {"responses": observed})()
        for index, (message, date, budget) in enumerate(cases, start=1):
            event_start = len(observed.events)
            started = time.monotonic()
            result = await agent_turn(
                AgentTurnRequest(message=message, session_id=session_id), profiles,
                sessions, settings=settings, client=wrapper,
            )
            seconds = round(time.monotonic() - started, 3)
            session_id = result.session_id
            expected_query = MatchRequest.model_validate({**base, "date": date, "budget_kzt": budget})
            expected = match(profiles, expected_query)
            actual = result.match
            same_query = result.parameters.model_dump(exclude_none=True) == expected_query.model_dump(mode="json", exclude_none=True)
            passed = bool(
                result.status == "matched" and result.tool_name == "match_contractors" and same_query
                and actual and actual.outcome == expected.outcome and actual.total_matches == expected.total_matches
                and [card.id for card in actual.cards] == [card.id for card in expected.cards]
            )
            print(json.dumps({
                "turn": index, "model": settings.model, "status": result.status,
                "source": result.source, "tool": result.tool_name, "seconds": seconds,
                "parameters": result.parameters.model_dump(exclude_none=True),
                "outcome": actual.outcome if actual else None,
                "total_matches": actual.total_matches if actual else None,
                "cards": [card.id for card in actual.cards] if actual else [],
                "api_events": observed.events[event_start:], "passed": passed,
            }, ensure_ascii=False), flush=True)
            if not passed:
                return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly allow up to six paid API calls")
    parser.add_argument("--model", help="Optional model override for this check only")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to explicitly run paid API requests")
    raise SystemExit(asyncio.run(main(args.model)))
