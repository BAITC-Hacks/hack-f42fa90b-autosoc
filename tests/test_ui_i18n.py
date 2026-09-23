"""Проверка полноты встроенных словарей интерфейса без запуска браузера."""

import re
from pathlib import Path

from app.i18n import _CATALOG_LABELS


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
PAGE = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
KEY = re.compile(r"(?<![\w])([A-Za-z][A-Za-z0-9]*):\s*\"")


def _locale_keys(locale: str) -> set[str]:
    source = SCRIPT.split("const ui = {", 1)[1].split("\n};\n\nconst precisionUi", 1)[0]
    start = source.split(f"  {locale}: {{", 1)[1]
    if locale == "ru":
        start = start.split("  kk: {", 1)[0]
    elif locale == "kk":
        start = start.split("  en: {", 1)[0]
    return set(KEY.findall(start))


def test_russian_kazakh_english_dictionaries_have_the_same_keys() -> None:
    russian = _locale_keys("ru")
    assert len(russian) > 100
    assert _locale_keys("kk") == russian
    assert _locale_keys("en") == russian

    precision = SCRIPT.split("const precisionUi = {", 1)[1].split("\n};\n\nfunction precise", 1)[0]
    ru = set(KEY.findall(precision.split("  ru: {", 1)[1].split("  kk: {", 1)[0]))
    kk = set(KEY.findall(precision.split("  kk: {", 1)[1].split("  en: {", 1)[0]))
    en = set(KEY.findall(precision.split("  en: {", 1)[1]))
    assert ru and ru == kk == en

    comparison = SCRIPT.split("const dateCompareUi = {", 1)[1].split("\n};\n\nfunction dc", 1)[0]
    ru = set(KEY.findall(comparison.split("  ru: {", 1)[1].split("  kk: {", 1)[0]))
    kk = set(KEY.findall(comparison.split("  kk: {", 1)[1].split("  en: {", 1)[0]))
    en = set(KEY.findall(comparison.split("  en: {", 1)[1]))
    assert ru and ru == kk == en


def test_html_and_client_text_keys_exist_in_each_locale() -> None:
    required = set(re.findall(r'data-i18n(?:-placeholder|-aria-label)?="([A-Za-z][A-Za-z0-9]*)"', PAGE))
    required.update(re.findall(r'\bt\("([A-Za-z][A-Za-z0-9]*)"', SCRIPT))
    assert required
    assert required <= _locale_keys("ru")


def test_locale_switch_and_requests_use_locale_without_changing_catalog_values() -> None:
    assert 'localStorage.setItem("contractor-locale", locale)' in SCRIPT
    assert 'document.documentElement.lang = locale' in SCRIPT
    assert '"Accept-Language": requestLocale' in SCRIPT
    assert 'new Option(catalogLabel(value), value)' in SCRIPT
    assert PAGE.count('data-scenario="') == 4


def test_catalog_option_labels_match_server_labels_for_reverse_translation() -> None:
    source = SCRIPT.split("const catalogLabels = {", 1)[1].split("\n};", 1)[0]
    client = {
        canonical: (kk, en)
        for canonical, kk, en in re.findall(
            r'"([^"]+)": \{ kk: "([^"]+)", en: "([^"]+)" \}', source
        )
    }
    server = {
        canonical: labels
        for kind in _CATALOG_LABELS.values()
        for canonical, labels in kind.items()
    }
    assert client == server
    assert "Object.values(translations).includes(trimmed)" in SCRIPT
