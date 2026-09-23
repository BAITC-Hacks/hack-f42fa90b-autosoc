"""Чистые правила отбора и устойчивой сортировки."""

from collections import Counter
from collections.abc import Iterable

from app.explain import make_card
from app.schemas import MatchRequest, MatchResponse, Profile, Rejection, RejectionReason

REASONS = ("date", "format", "budget", "language", "hours", "insufficient_data")
REASON_LABELS = {
    "date": "занятость на дату", "format": "формат", "budget": "бюджет",
    "language": "язык", "hours": "длительность", "insufficient_data": "недостаток данных",
}


def _profile_word(number: int) -> str:
    if number % 10 == 1 and number % 100 != 11:
        return "профиль"
    if number % 10 in (2, 3, 4) and number % 100 not in (12, 13, 14):
        return "профиля"
    return "профилей"


def _rejection(profile: Profile, request: MatchRequest) -> Rejection | None:
    # Все причины сохраняются; первая по фиксированному порядку — основная.
    reasons: list[RejectionReason] = []
    if request.date in profile.busy_dates:
        reasons.append(RejectionReason(code="date", detail=f"Занят на {request.date.isoformat()}"))
    if profile.event_formats and request.event_format not in profile.event_formats:
        reasons.append(RejectionReason(code="format", detail=f"Формат «{request.event_format}» отсутствует; указаны: {', '.join(profile.event_formats)}"))
    if profile.price_from_kzt is not None and profile.price_from_kzt > request.budget_kzt:
        reasons.append(RejectionReason(code="budget", detail=f"Цена от {profile.price_from_kzt} ₸ превышает бюджет {request.budget_kzt} ₸"))
    if request.language and profile.languages and request.language not in profile.languages:
        reasons.append(RejectionReason(code="language", detail=f"Язык «{request.language}» отсутствует; указаны: {', '.join(profile.languages)}"))
    if request.hours is not None and profile.max_hours is not None and profile.max_hours < request.hours:
        reasons.append(RejectionReason(code="hours", detail=f"Запрошено {request.hours} ч, предел профиля {profile.max_hours} ч"))
    missing = []
    if not profile.event_formats:
        missing.append(f"форматы не указаны, нельзя проверить «{request.event_format}»")
    if profile.price_from_kzt is None:
        missing.append(f"цена от не указана, нельзя подтвердить бюджет {request.budget_kzt} ₸")
    if request.language and not profile.languages:
        missing.append(f"языки не указаны, нельзя проверить «{request.language}»")
    if missing:
        reasons.append(RejectionReason(code="insufficient_data", detail="Недостаток данных: " + "; ".join(missing)))
    if not reasons:
        return None
    primary = reasons[0]
    return Rejection(id=profile.id, primary_reason=primary.code, detail=primary.detail, all_reasons=reasons)


def match(profiles: Iterable[Profile], request: MatchRequest) -> MatchResponse:
    candidates = sorted(
        (profile for profile in profiles if profile.city == request.city and request.category in profile.categories),
        key=lambda profile: profile.id,
    )
    if not candidates:
        return MatchResponse(
            outcome="no_category_in_city", total_matches=0, cards=[],
            primary_reason_counts={reason: 0 for reason in REASONS}, rejected=[],
            excluded_by_date=0,
            message=f"Категория «{request.category}» не представлена в городе {request.city}; календарь никого не исключил.",
        )

    matched = []
    rejected = []
    for profile in candidates:
        reason = _rejection(profile, request)
        if reason is None:
            matched.append(profile)
        else:
            rejected.append(reason)
    counts = Counter(item.primary_reason for item in rejected)
    reason_counts = {reason: counts[reason] for reason in REASONS}
    matched.sort(key=lambda profile: (profile.price_from_kzt, profile.id))
    cards = [make_card(profile, request) for profile in matched[:3]]
    date_count = reason_counts["date"]
    calendar_note = f"По выбранной дате исключено {date_count} {_profile_word(date_count)}."
    if not matched:
        summary = ", ".join(f"{REASON_LABELS[reason]}: {count}" for reason, count in reason_counts.items() if count)
        message = f"Категория есть в городе: {len(candidates)} {_profile_word(len(candidates))}. Все отсеяны ({summary}). {calendar_note}"
        outcome = "all_filtered"
    else:
        verb = "Найден" if len(matched) == 1 else "Найдено"
        message = f"{verb} {len(matched)} {_profile_word(len(matched))}. {calendar_note}"
        if len(matched) < 3:
            message += f" Карточек меньше трёх: всего кандидатов {len(candidates)}, не прошли условия {len(rejected)}."
        outcome = "matched"
    return MatchResponse(
        outcome=outcome, total_matches=len(matched), cards=cards,
        primary_reason_counts=reason_counts, rejected=rejected,
        excluded_by_date=reason_counts["date"], message=message,
    )
