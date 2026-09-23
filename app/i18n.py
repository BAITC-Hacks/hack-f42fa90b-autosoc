"""Серверные тексты результата; параметры каталога остаются каноническими."""

from collections.abc import Iterable

from app.schemas import MatchCard, MatchRequest, MatchResponse, Profile, RejectionReason

LOCALES = ("ru", "kk", "en")
_CATALOG_LABELS = {
    "city": {
        "Алматы": ("Алматы", "Almaty"), "Астана": ("Астана", "Astana"),
        "Зарубежье": ("Шетелде", "Abroad"),
    },
    "category": {
        "Банкетный зал": ("Банкет залы", "Banquet hall"),
        "Ведущий": ("Жүргізуші", "Event host"),
        "Ведущий церемонии": ("Рәсім жүргізушісі", "Ceremony host"),
        "Видеограф": ("Бейнеоператор", "Videographer"),
        "Декоратор": ("Безендіруші", "Decorator"),
        "Загородная площадка": ("Қала сыртындағы алаң", "Countryside venue"),
        "Инструменталист": ("Аспапшы", "Instrumentalist"),
        "Лайв-бэнд": ("Жанды музыка тобы", "Live band"),
        "Национальный ансамбль": ("Ұлттық ансамбль", "National ensemble"),
        "Отель": ("Қонақүй", "Hotel"),
        "Подарки и сувениры": ("Сыйлықтар мен кәдесыйлар", "Gifts and souvenirs"),
        "Ресторан": ("Мейрамхана", "Restaurant"),
        "Танцевальный коллектив": ("Би тобы", "Dance troupe"),
        "Флорист": ("Флорист", "Florist"),
        "Фото и видеобудки": ("Фото және бейнебудкалар", "Photo and video booths"),
        "Фотограф": ("Фотограф", "Photographer"),
        "Шоу-программа": ("Шоу бағдарламасы", "Show program"),
    },
    "event_format": {
        "день рождения": ("туған күн", "birthday"),
        "конференция": ("конференция", "conference"),
        "корпоратив": ("корпоративтік іс-шара", "company event"),
        "свадьба": ("үйлену тойы", "wedding"),
        "той": ("той", "toi celebration"),
        "юбилей": ("мерейтой", "anniversary celebration"),
    },
    "language": {
        "английский": ("ағылшын тілі", "English"),
        "казахский": ("қазақ тілі", "Kazakh"),
        "русский": ("орыс тілі", "Russian"),
    },
}
_REASON_LABELS = {
    "kk": {
        "date": "күнтізбедегі бос еместік", "format": "формат", "budget": "бюджет",
        "language": "қызмет тілі", "hours": "ұзақтығы", "insufficient_data": "дерек жеткіліксіз",
    },
    "en": {
        "date": "busy date", "format": "format", "budget": "budget",
        "language": "service language", "hours": "duration", "insufficient_data": "insufficient data",
    },
}


def normalize_locale(header: str | None) -> str:
    """Берёт первую поддерживаемую локаль из обычного Accept-Language."""
    if not header:
        return "ru"
    choices: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        pieces = [piece.strip() for piece in part.split(";")]
        tag = pieces[0].lower().split("-")[0]
        if tag not in LOCALES:
            continue
        quality = 1.0
        for parameter in pieces[1:]:
            if parameter.startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        if 0 < quality <= 1:
            choices.append((quality, -index, tag))
    return max(choices)[2] if choices else "ru"


def catalog_label(kind: str, canonical: str, locale: str) -> str:
    """Локализует только видимую подпись, оставляя значение API без изменения."""
    locale = normalize_locale(locale)
    if locale == "ru":
        return canonical
    pair = _CATALOG_LABELS.get(kind, {}).get(canonical)
    return pair[0 if locale == "kk" else 1] if pair else canonical


def _reason_detail(code: str, profile: Profile, request: MatchRequest, locale: str) -> str:
    if code == "date":
        return (f"{request.date.isoformat()} күні бос емес деп белгіленген" if locale == "kk"
                else f"Marked busy on {request.date.isoformat()}")
    if code == "format":
        requested = catalog_label("event_format", request.event_format, locale)
        supported = ", ".join(catalog_label("event_format", value, locale) for value in profile.event_formats)
        return (f"«{requested}» форматы жоқ; көрсетілгені: {supported}" if locale == "kk"
                else f"Format “{requested}” is not listed; listed: {supported}")
    if code == "budget":
        return (f"Бағасы {profile.price_from_kzt} ₸ бастап, {request.budget_kzt} ₸ бюджеттен жоғары"
                if locale == "kk" else
                f"Price from {profile.price_from_kzt} ₸ exceeds the {request.budget_kzt} ₸ budget")
    if code == "language":
        requested = catalog_label("language", request.language, locale)
        supported = ", ".join(catalog_label("language", value, locale) for value in profile.languages)
        return (f"«{requested}» қызмет тілі жоқ; көрсетілгені: {supported}" if locale == "kk"
                else f"Service language “{requested}” is not listed; listed: {supported}")
    if code == "hours":
        return (f"{request.hours} сағат сұралды, профильдегі шек {profile.max_hours} сағат" if locale == "kk"
                else f"Requested {request.hours} h; profile limit is {profile.max_hours} h")
    missing = []
    if not profile.event_formats:
        requested = catalog_label("event_format", request.event_format, locale)
        missing.append(
            f"«{requested}» форматын тексеру үшін форматтар көрсетілмеген" if locale == "kk"
            else f"formats are missing, so “{requested}” cannot be checked"
        )
    if profile.price_from_kzt is None:
        missing.append(
            f"{request.budget_kzt} ₸ бюджетке сәйкестікті растау үшін бастапқы баға жоқ" if locale == "kk"
            else f"starting price is missing, so the {request.budget_kzt} ₸ budget cannot be checked"
        )
    if request.language and not profile.languages:
        requested = catalog_label("language", request.language, locale)
        missing.append(
            f"«{requested}» тілін тексеру үшін тілдер көрсетілмеген" if locale == "kk"
            else f"languages are missing, so “{requested}” cannot be checked"
        )
    return ("Дерек жеткіліксіз: " if locale == "kk" else "Insufficient data: ") + "; ".join(missing)


def _summary(response: MatchResponse, request: MatchRequest, locale: str) -> str:
    count = response.total_matches
    date_count = response.excluded_by_date
    category = catalog_label("category", request.category, locale)
    city = catalog_label("city", request.city, locale)
    if locale == "kk":
        if response.outcome == "no_category_in_city":
            return f"«{category}» санаты {city} қаласында жоқ; күнтізбе бойынша ешкім шеттетілген жоқ."
        calendar = f"Таңдалған күні бос емес деп белгіленген {date_count} профиль алынып тасталды."
        if response.outcome == "all_filtered":
            reasons = ", ".join(f"{_REASON_LABELS[locale][key]}: {value}" for key, value in response.primary_reason_counts.items() if value)
            return f"Бұл қалада осы санат бойынша {len(response.rejected)} профиль бар. Барлығы шарттардан өтпеді ({reasons}). {calendar}"
        message = f"{count} профиль табылды. {calendar}"
        if count < 3:
            message += f" Үштен аз карточка: барлығы {count + len(response.rejected)} кандидат, {len(response.rejected)} шарттардан өтпеді."
        return message
    if response.outcome == "no_category_in_city":
        return f"Category “{category}” is not represented in {city}; no profile was excluded by the calendar."
    calendar = (
        "1 profile was excluded because it is marked busy on the selected date."
        if date_count == 1 else
        f"{date_count} profiles were excluded because they are marked busy on the selected date."
    )
    if response.outcome == "all_filtered":
        reasons = ", ".join(f"{_REASON_LABELS[locale][key]}: {value}" for key, value in response.primary_reason_counts.items() if value)
        return f"There are {len(response.rejected)} profiles in this city and category. All failed the conditions ({reasons}). {calendar}"
    match_noun = "profile" if count == 1 else "profiles"
    message = f"Found {count} matching {match_noun}. {calendar}"
    if count < 3:
        candidates = count + len(response.rejected)
        candidate_noun = "candidate" if candidates == 1 else "candidates"
        message += f" Fewer than three cards: {candidates} {candidate_noun} total; {len(response.rejected)} failed the conditions."
    return message


def _card_explanation(card: MatchCard, request: MatchRequest, locale: str) -> str:
    facts = card.facts
    category = catalog_label("category", request.category, locale)
    city = catalog_label("city", request.city, locale)
    event_format = catalog_label("event_format", facts.event_format, locale)
    if locale == "kk":
        details = []
        if facts.language:
            details.append(f"«{catalog_label('language', facts.language, locale)}» қызмет тілі профильде көрсетілген")
        if facts.requested_hours is not None:
            details.append(
                "каталогта жұмыс сағатпен шектелмеген, қызмет ұзақтығын нақтылау керек"
                if facts.max_hours is None else
                f"сұралған {facts.requested_hours} сағат профильдегі {facts.max_hours} сағат шегінде"
            )
        if card.evidence_excerpt:
            details.append(f"түпнұсқа тілдегі сипаттамадан үзінді: «{card.evidence_excerpt}»")
        else:
            details.append("сипаттамадан үзінді таңдалмады; толық мәтін карточкада бар" if card.description.strip()
                           else "сипаттамада қосымша мәлімет жоқ")
        return (
            f"«{card.anon_name}»: {category}, {city}, «{event_format}» форматы; "
            f"бағасы {facts.price_from_kzt} ₸ бастап, бюджет {facts.budget_kzt} ₸ "
            f"(бюджет қоры {facts.budget_headroom_kzt} ₸, {facts.budget_headroom_percent}%), "
            f"соңғы смета расталмаған. {facts.date.isoformat()} күні профиль берілген күнтізбеде бос емес "
            f"деп белгіленбеген; {'; '.join(details)}."
        )
    details = []
    if facts.language:
        details.append(f"service language “{catalog_label('language', facts.language, locale)}” is listed in the profile")
    if facts.requested_hours is not None:
        details.append(
            "the catalog does not tie this work to hours; confirm service duration"
            if facts.max_hours is None else
            f"requested {facts.requested_hours} h is within the listed {facts.max_hours} h limit"
        )
    if card.evidence_excerpt:
        details.append(f"original-language description excerpt: “{card.evidence_excerpt}”")
    else:
        details.append("no description excerpt was selected; the full text is available in the card" if card.description.strip()
                       else "no additional description details are available")
    return (
        f"“{card.anon_name}”: {category}, {city}, format “{event_format}”; "
        f"price from {facts.price_from_kzt} ₸ against a {facts.budget_kzt} ₸ budget "
        f"(budget headroom {facts.budget_headroom_kzt} ₸, {facts.budget_headroom_percent}%), "
        f"and the final quote is unconfirmed. On {facts.date.isoformat()}, this profile is not marked busy "
        f"in the supplied calendar; {'; '.join(details)}."
    )


def localize_match(
    response: MatchResponse, profiles: Iterable[Profile], request: MatchRequest, locale: str,
) -> MatchResponse:
    """Меняет только тексты; исходные факты, ID, порядок и ранжирование неизменны."""
    locale = normalize_locale(locale)
    if locale == "ru":
        return response
    by_id = {profile.id: profile for profile in profiles}
    rejected = []
    for rejection in response.rejected:
        profile = by_id.get(rejection.id)
        if profile is None:
            rejected.append(rejection)
            continue
        all_reasons = [
            RejectionReason(code=item.code, detail=_reason_detail(item.code, profile, request, locale))
            for item in rejection.all_reasons
        ]
        primary_detail = next((item.detail for item in all_reasons if item.code == rejection.primary_reason), rejection.detail)
        rejected.append(rejection.model_copy(update={"detail": primary_detail, "all_reasons": all_reasons}))
    cards = [card.model_copy(update={"explanation": _card_explanation(card, request, locale)}) for card in response.cards]
    return response.model_copy(update={
        "message": _summary(response, request, locale), "cards": cards, "rejected": rejected,
    })
