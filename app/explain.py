"""Только проверенные факты и шаблонный текст; внешние модели не вызываются."""

from app.schemas import MatchCard, MatchFacts, MatchRequest, Profile


def _excerpt(description: str) -> str | None:
    text = description.strip()
    if not text:
        return None
    endings = [text.find(mark) for mark in ".!?" if 0 <= text.find(mark) <= 120]
    if endings:
        return text[:min(endings)] or None
    if len(text) <= 100:
        return text
    fragment = text[:100]
    return fragment.rsplit(" ", 1)[0] or fragment


def make_card(profile: Profile, request: MatchRequest) -> MatchCard:
    assert profile.price_from_kzt is not None
    headroom = request.budget_kzt - profile.price_from_kzt
    percent = round(100 * headroom / request.budget_kzt, 1)
    excerpt = _excerpt(profile.description)
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
        description_excerpt=excerpt,
    )
    additional = []
    if request.language:
        additional.append(f"язык «{request.language}» указан в профиле")
    if request.hours is not None:
        if profile.max_hours is None:
            additional.append("работа в каталоге не привязана к часам; длительность обслуживания уточняется")
        else:
            additional.append(f"запрошено {request.hours} ч из указанного предела {profile.max_hours} ч")
    details = "; ".join(additional)
    if details:
        details = "; " + details
    explanation = (
        f"«{profile.anon_name}»: {request.category}, {request.city}, формат «{request.event_format}»; "
        f"цена от {profile.price_from_kzt} ₸ при бюджете {request.budget_kzt} ₸ "
        f"(запас {headroom} ₸, {percent}%), окончательная смета не подтверждена. "
        f"На {request.date.isoformat()} профиль не отмечен занятым в предоставленном календаре{details}."
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
        description=profile.description,
        synthetic=profile.synthetic,
        city_imputed=profile.city_imputed,
        price_imputed=profile.price_imputed,
        provenance=profile.provenance,
    )
