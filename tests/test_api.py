from fastapi.testclient import TestClient

from app.main import app


def payload(**changes):
    values = dict(city="Алматы", date="2026-10-07", event_format="свадьба", category="Ведущий", budget_kzt=1000000)
    values.update(changes)
    return values


def test_health_options_and_real_matches():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok", "profiles_loaded": 66}
        options = client.get("/api/options").json()
        assert options["calendar_start"] == "2026-09-23"
        assert options["calendar_end"] == "2026-12-31"
        assert "Ведущий" in options["categories_by_city"]["Алматы"]
        positive = client.post("/api/match", json=payload())
        assert positive.status_code == 200
        assert positive.json()["total_matches"] >= 3
        assert len(positive.json()["cards"]) == 3
        next_date = client.post("/api/match", json=payload(date="2026-10-10")).json()
        assert next_date["total_matches"] == 2
        assert positive.json()["excluded_by_date"] == 1
        assert next_date["excluded_by_date"] == 4
        assert [card["id"] for card in positive.json()["cards"]] != [card["id"] for card in next_date["cards"]]
        empty = client.post("/api/match", json=payload(date="2026-10-10", budget_kzt=300000)).json()
        assert empty["outcome"] == "all_filtered"
        assert empty["total_matches"] == 0
        assert all(item["all_reasons"] for item in empty["rejected"])
        absent = client.post("/api/match", json=payload(city="Астана", category="Декоратор")).json()
        assert absent["outcome"] == "no_category_in_city"


def test_api_validation_errors():
    with TestClient(app) as client:
        for bad in (payload(date="2027-01-01"), payload(date="wrong"), payload(budget_kzt=0), payload(hours=-1)):
            result = client.post("/api/match", json=bad)
            assert result.status_code == 422
        assert "неизвестна" in str(client.post("/api/match", json=payload(date="2027-01-01")).json())
