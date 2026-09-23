"""Строгая загрузка исходного CSV без изменения файла."""

import csv
from datetime import date
from pathlib import Path

from app.schemas import Profile

ROOT = Path(__file__).resolve().parent.parent
SOURCE_NAME = "hackathon dataset anonymized.csv"
EXPECTED_FIELDS = (
    "id", "anon_name", "categories", "city", "city_imputed", "synthetic",
    "price_from_kzt", "price_imputed", "event_formats", "languages",
    "max_hours", "busy_dates", "description",
)


def source_path(root: Path = ROOT) -> Path:
    for candidate in (root / "data" / SOURCE_NAME, root / SOURCE_NAME):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Исходный CSV не найден. Положите {SOURCE_NAME} в {root / 'data'} или {root}"
    )


def _required(row: dict[str, str], field: str, position: int) -> str:
    value = (row[field] or "").strip()
    if not value:
        raise ValueError(f"Строка {position}: пустое обязательное поле {field}")
    return value


def _boolean(value: str, field: str, position: int) -> bool:
    if value not in ("True", "False"):
        raise ValueError(f"Строка {position}: {field} должно быть True или False")
    return value == "True"


def _positive_int(value: str, field: str, position: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Строка {position}: некорректное число в {field}") from exc
    if result <= 0:
        raise ValueError(f"Строка {position}: {field} должно быть положительным")
    return result


def _list(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split("|") if part.strip())


def load_csv(path: Path, provenance: str) -> list[Profile]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        opening = handle.read(2048).lstrip().lower()
        handle.seek(0)
        if opening.startswith(("<!doctype html", "<html", "<head", "<body")):
            raise ValueError(
                f"Файл {path.name} содержит HTML вместо CSV. "
                "Проверьте скачивание исходного датасета."
            )
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != EXPECTED_FIELDS:
            raise ValueError(f"Неверная схема CSV: {path.name}")
        profiles = []
        for position, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Строка {position}: неверное количество колонок")
            price_text = row["price_from_kzt"].strip()
            hours_text = row["max_hours"].strip()
            try:
                busy_dates = tuple(date.fromisoformat(item) for item in _list(row["busy_dates"]))
            except ValueError as exc:
                raise ValueError(f"Строка {position}: некорректная дата занятости") from exc
            profile = Profile(
                id=_required(row, "id", position),
                anon_name=_required(row, "anon_name", position),
                categories=_list(_required(row, "categories", position)),
                city=_required(row, "city", position),
                city_imputed=_boolean(row["city_imputed"], "city_imputed", position),
                synthetic=_boolean(row["synthetic"], "synthetic", position),
                price_from_kzt=_positive_int(price_text, "price_from_kzt", position) if price_text else None,
                price_imputed=_boolean(row["price_imputed"], "price_imputed", position),
                event_formats=_list(row["event_formats"]),
                languages=_list(row["languages"]),
                max_hours=_positive_int(hours_text, "max_hours", position) if hours_text else None,
                busy_dates=busy_dates,
                description=row["description"].strip(),
                provenance=provenance,
            )
            profiles.append(profile)
    return profiles


def load_profiles(root: Path = ROOT) -> tuple[Profile, ...]:
    profiles = load_csv(source_path(root), "original_csv")
    extra = root / "data" / "synthetic_extra.csv"
    if extra.is_file():
        profiles.extend(load_csv(extra, "synthetic_extra"))
    identifiers = [profile.id for profile in profiles]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("В каталоге повторяются id профилей")
    return tuple(profiles)
