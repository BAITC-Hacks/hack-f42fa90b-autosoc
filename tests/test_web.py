from fastapi.testclient import TestClient

from app.main import app


def test_home_and_static_files_are_served():
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "text/html" in page.headers["content-type"]
        assert "Подобрать подрядчиков" in page.text
        css = client.get("/static/styles.css")
        js = client.get("/static/app.js")
        assert css.status_code == 200 and "text/css" in css.headers["content-type"]
        assert js.status_code == 200 and "javascript" in js.headers["content-type"]
        assert client.get("/api/options").status_code == 200
