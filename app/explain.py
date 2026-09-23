"""Проверка цитат и объяснения, собранные кодом из фактов профиля."""

import re
from typing import Literal

from app.schemas import MatchCard, MatchFacts, MatchRequest, Profile

MAX_EXCERPT_LENGTH = 400
MIN_EXCERPT_LENGTH = 18
_WORDS = re.compile(r"\w+", re.UNICODE)
_FRAGMENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+|[\r\n]+|(?=•)")
_FEATURE_TERMS = (
    ("импровиз", 36), ("сценар", 24), ("язык", 20),
    ("оформлен", 18), ("флорист", 18), ("фото", 16), ("видео", 16),
    ("вокал", 15), ("музык", 10), ("меню", 10), ("банкет", 10),
    ("вед", 6), ("свадеб", 6),
)


def description_fragments(profile: Profile) -> tuple[str, ...]:
    """Полные предложения или пункты описания, без обрезки смысла по длине.

    Только эти серверные фрагменты могут попасть в карточку. Не делим по
    запятым или точкам с запятой: там часто находятся условия и отрицания.
    Слишком длинные части пропускаем целиком, а не обрезаем.
    """
    fragments: list[str] = []
    for part in _FRAGMENT_BOUNDARY.split(profile.description):
        fragment = part.strip().removeprefix("•").strip().rstrip(".!?").strip()
        if not MIN_EXCERPT_LENGTH <= len(fragment) <= MAX_EXCERPT_LENGTH:
            continue
        words = _WORDS.findall(fragment)
        if len(words) < 3 or not any(len(word) >= 5 for word in words):
            continue
        folded = fragment.casefold()
        if folded == profile.anon_name.casefold() or "отличный выбор" in folded:
            continue
        if folded.startswith(("привет", "здравствуйте", "меня зовут", "добрый день")):
            continue
        if fragment in profile.description and fragment not in fragments:
            fragments.append(fragment)
    return tuple(fragments)


def valid_excerpt(excerpt: str | None, profile: Profile) -> bool:
    """Цитата должна совпадать с полным фрагментом собственного описания."""
    return isinstance(excerpt, str) and excerpt in description_fragments(profile)


def template_excerpt(profile: Profile) -> str | None:
    """Детерминированно выбирает проверяемую особенность из собственного описания."""
    choices: list[tuple[int, int, str]] = []
    for index, raw in enumerate(description_fragments(profile)):
        folded = raw.casefold()
        score = sum(weight for term, weight in _FEATURE_TERMS if term in folded)
        if "все форматы" in folded or "оборудован" in folded:
            score -= 18
        if any(term in folded for term in ("топ-", "лучши", "безупреч", "идеаль", "гарант", "247")):
            score -= 18
        score += min(len(_WORDS.findall(raw)), 12)
        choices.append((score, -index, raw))
    return max(choices)[2] if choices else None


def make_card(
    profile: Profile,
    request: MatchRequest,
    *,
    evidence_excerpt: str | None = None,
    explanation_source: Literal["ai_selected", "template"] = "template",
) -> MatchCard:
    assert profile.price_from_kzt is not None
    if evidence_excerpt is None:
        evidence_excerpt = template_excerpt(profile)
        explanation_source = "template"
    elif not valid_excerpt(evidence_excerpt, profile):
        raise ValueError("Цитата не подтверждена описанием профиля")

    headroom = request.budget_kzt - profile.price_from_kzt
    percent = round(100 * headroom / request.budget_kzt, 1)
    facts = MatchFacts(
        budget_kzt=request.budget_kzt,
        price_from_kzt=profile.price_from_kzt,
        budget_headroom_kzt=headroom,
        budget_headroom_percent=percent,
        event_format=request.event_format,
        language=request.language,
        requested_hours=request.hours,
        max_hours=profile.max_hours,
        date=request.date,
        not_marked_busy_on_date=request.date not in profile.busy_dates,
        description_excerpt=evidence_excerpt,
    )
    details = []
    if request.language:
        details.append(f"язык «{request.language}» указан в профиле")
    if request.hours is not None:
        if profile.max_hours is None:
            details.append("работа в каталоге не привязана к часам; длительность обслуживания уточняется")
        else:
            details.append(f"запрошено {request.hours} ч из указанного предела {profile.max_hours} ч")
    if evidence_excerpt:
        details.append(f"в описании указано: «{evidence_excerpt}»")
    elif profile.description.strip():
        details.append("краткий фрагмент описания не выбран; полный текст доступен в карточке")
    else:
        details.append("подробных сведений в описании нет")
    extra = "; ".join(details)
    ending = "" if evidence_excerpt and evidence_excerpt.endswith((".", "!", "?")) else "."
    explanation = (
        f"«{profile.anon_name}»: {request.category}, {request.city}, формат «{request.event_format}»; "
        f"цена от {profile.price_from_kzt} ₸ при бюджете {request.budget_kzt} ₸ "
        f"(запас {headroom} ₸, {percent}%), окончательная смета не подтверждена. "
        f"На {request.date.isoformat()} профиль не отмечен занятым в предоставленном календаре; {extra}{ending}"
    )
    return MatchCard(
        id=profile.id,
        anon_name=profile.anon_name,
        categories=profile.categories,
        city=profile.city,
        price_from_kzt=profile.price_from_kzt,
        rank_score=headroom / request.budget_kzt,
        rank_factors={"budget_headroom_kzt": headroom, "budget_headroom_percent": percent},
        facts=facts,
        explanation=explanation,
        explanation_source=explanation_source,
        evidence_excerpt=evidence_excerpt,
        description=profile.description,
        synthetic=profile.synthetic,
        city_imputed=profile.city_imputed,
        price_imputed=profile.price_imputed,
        provenance=profile.provenance,
    )
