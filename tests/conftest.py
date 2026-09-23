"""Обычный pytest всегда выполняется без реальных платных API-вызовов."""

import pytest


@pytest.fixture(autouse=True)
def disable_external_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    # Окружение имеет приоритет над локальным .env даже при наличии ключа.
    monkeypatch.setenv("EXPLANATION_MODE", "template")
