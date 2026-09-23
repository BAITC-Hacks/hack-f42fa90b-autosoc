"""Настройки объяснений: окружение имеет приоритет над локальным .env."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from app.data import ROOT


@dataclass(frozen=True)
class ExplanationSettings:
    mode: str = "auto"
    api_key: str | None = field(default=None, repr=False)
    model: str = "gpt-4o-mini"


def get_settings(root: Path = ROOT) -> ExplanationSettings:
    local = dotenv_values(root / ".env") if (root / ".env").is_file() else {}

    def setting(name: str) -> str | None:
        if name in os.environ:
            return os.environ[name]
        return local.get(name)

    mode = (setting("EXPLANATION_MODE") or "auto").strip().lower()
    # Неизвестный режим не должен случайно запускать внешний запрос.
    if mode not in {"auto", "template"}:
        mode = "template"
    return ExplanationSettings(
        mode=mode,
        api_key=(setting("OPENAI_API_KEY") or "").strip() or None,
        model=(setting("OPENAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini",
    )
