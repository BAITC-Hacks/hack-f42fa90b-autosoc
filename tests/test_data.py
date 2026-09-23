import csv
from pathlib import Path

import pytest

from app.data import EXPECTED_FIELDS, SOURCE_NAME, load_csv, load_profiles


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(**changes: str) -> dict[str, str]:
    values = dict(
        id="x", anon_name="Тест", categories="Ведущий|Шоу-программа", city="Алматы",
        city_imputed="True", synthetic="False", price_from_kzt="100000", price_imputed="False",
        event_formats="свадьба|корпоратив", languages="русский|казахский",
        max_hours="", busy_dates="2026-10-07|2026-10-08", description="Описание",
    )
    values.update(changes)
    return values


def test_bom_lists_flags_and_null_hours(tmp_path):
    path = tmp_path / SOURCE_NAME
    write_csv(path, [row()])
    item = load_csv(path, "original_csv")[0]
    assert item.categories == ("Ведущий", "Шоу-программа")
    assert item.event_formats == ("свадьба", "корпоратив")
    assert len(item.busy_dates) == 2
    assert (item.city_imputed, item.synthetic, item.price_imputed) == (True, False, False)
    assert item.max_hours is None


def test_optional_extra_and_provenance(tmp_path):
    write_csv(tmp_path / "data" / SOURCE_NAME, [row()])
    write_csv(tmp_path / "data" / "synthetic_extra.csv", [row(id="extra", synthetic="True")])
    profiles = load_profiles(tmp_path)
    assert [item.provenance for item in profiles] == ["original_csv", "synthetic_extra"]
    assert [item.synthetic for item in profiles] == [False, True]


def test_missing_file_and_duplicate_ids(tmp_path):
    with pytest.raises(FileNotFoundError, match=SOURCE_NAME):
        load_profiles(tmp_path)
    write_csv(tmp_path / SOURCE_NAME, [row(), row()])
    with pytest.raises(ValueError, match="повторяются id"):
        load_profiles(tmp_path)


@pytest.mark.parametrize("html", [
    "<!DOCTYPE html><html><body>Ошибка скачивания</body></html>",
    "  <html><body>Sign in to Google Drive</body></html>",
])
def test_html_download_is_rejected_as_csv(tmp_path, html):
    path = tmp_path / SOURCE_NAME
    path.write_text(html, encoding="utf-8-sig")
    with pytest.raises(ValueError, match="HTML вместо CSV"):
        load_profiles(tmp_path)
    assert path.read_text(encoding="utf-8-sig") == html


@pytest.mark.parametrize("change", [
    {"synthetic": "yes"}, {"city": ""}, {"price_from_kzt": "-1"},
    {"busy_dates": "2026-10-99"},
])
def test_bad_csv_rejected(tmp_path, change):
    path = tmp_path / SOURCE_NAME
    write_csv(path, [row(**change)])
    with pytest.raises(ValueError):
        load_csv(path, "original_csv")
