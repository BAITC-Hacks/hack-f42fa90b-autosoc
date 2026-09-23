"""HTTP API каталога подрядчиков."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent import AgentSessionStore, agent_turn
from app.ai_explain import enrich_match
from app.data import load_profiles
from app.i18n import localize_match, normalize_locale
from app.matcher import match
from app.schemas import (
    CALENDAR_END, CALENDAR_START, AgentTurnRequest, AgentTurnResponse,
    MatchRequest, MatchResponse, OptionsResponse, Profile,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.profiles = load_profiles()
    application.state.agent_sessions = AgentSessionStore()
    yield


app = FastAPI(title="Умный подбор подрядчиков", lifespan=lifespan)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def _profiles(request: Request) -> tuple[Profile, ...]:
    return request.app.state.profiles


@app.get("/health")
def health(request: Request) -> dict[str, int | str]:
    return {"status": "ok", "profiles_loaded": len(_profiles(request))}


@app.get("/api/options", response_model=OptionsResponse)
def options(request: Request) -> OptionsResponse:
    profiles = _profiles(request)
    cities = sorted({profile.city for profile in profiles})
    return OptionsResponse(
        cities=cities,
        categories=sorted({category for profile in profiles for category in profile.categories}),
        categories_by_city={city: sorted({category for profile in profiles if profile.city == city for category in profile.categories}) for city in cities},
        event_formats=sorted({fmt for profile in profiles for fmt in profile.event_formats}),
        languages=sorted({language for profile in profiles for language in profile.languages}),
        calendar_start=CALENDAR_START,
        calendar_end=CALENDAR_END,
    )


@app.post("/api/match", response_model=MatchResponse)
async def api_match(payload: MatchRequest, request: Request) -> MatchResponse:
    profiles = _profiles(request)
    selected = match(profiles, payload)
    enriched = await enrich_match(selected, profiles, payload)
    return localize_match(enriched, profiles, payload, normalize_locale(request.headers.get("accept-language")))


@app.post("/api/agent", response_model=AgentTurnResponse)
async def api_agent(payload: AgentTurnRequest, request: Request) -> AgentTurnResponse:
    return await agent_turn(
        payload, _profiles(request), request.app.state.agent_sessions,
        locale=normalize_locale(request.headers.get("accept-language")),
    )
