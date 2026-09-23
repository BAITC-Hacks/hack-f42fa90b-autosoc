"""Small, explicit multilingual vocabulary for validating catalog names in agent evidence.

The model proposes a canonical value. This module only checks whether the cited
words support that value; it never chooses a contractor or changes the catalog.
"""

import re
import unicodedata


ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "city": {
        "Алматы": ("алматы", "almaty", "алма ата"),
        "Астана": ("астана", "astana", "nur sultan", "нур султан"),
        "Зарубежье": ("зарубежье", "abroad", "overseas", "шетел"),
    },
    "category": {
        "Банкетный зал": ("банкетный зал", "banquet hall", "банкет залы"),
        "Ведущий": ("ведущий", "ведущ", "тамада", "mc", "event host", "host", "жүргізуші"),
        "Ведущий церемонии": ("ведущий церемонии", "ceremony host", "ceremony mc", "рәсім жүргізушісі"),
        "Видеограф": ("видеограф", "videographer", "бейнеоператор"),
        "Декоратор": ("декоратор", "decorator", "безендіруші"),
        "Загородная площадка": ("загородная площадка", "outdoor venue", "қала сыртындағы алаң"),
        "Инструменталист": ("инструменталист", "instrumentalist", "аспапшы"),
        "Лайв-бэнд": ("лайв бэнд", "live band", "жанды топ"),
        "Национальный ансамбль": ("национальный ансамбль", "national ensemble", "ұлттық ансамбль"),
        "Отель": ("отель", "hotel", "қонақ үй"),
        "Подарки и сувениры": ("подарки и сувениры", "gifts and souvenirs", "сыйлықтар мен кәдесыйлар"),
        "Ресторан": ("ресторан", "restaurant", "мейрамхана"),
        "Танцевальный коллектив": ("танцевальный коллектив", "dance troupe", "би тобы"),
        "Флорист": ("флорист", "florist", "гүл өсіруші"),
        "Фото и видеобудки": ("фото и видеобудки", "photo and video booths", "фото және бейнебудкалар"),
        "Фотограф": ("фотограф", "photographer", "фотосуретші"),
        "Шоу-программа": ("шоу программа", "show programme", "show program", "шоу бағдарлама"),
    },
    "event_format": {
        "день рождения": ("день рождения", "birthday", "туған күн"),
        "конференция": ("конференция", "conference", "конференция"),
        "корпоратив": ("корпоратив", "corporate event", "корпоратив"),
        "свадьба": ("свадьба", "wedding", "үйлену тойы", "үйлену той", "неке тойы"),
        "той": ("той", "toi", "celebration", "мереке"),
        "юбилей": ("юбилей", "anniversary", "мерейтой"),
    },
    "language": {
        "английский": ("английский", "english", "ағылшын", "ағылшынша"),
        "казахский": ("казахский", "kazakh", "қазақ", "қазақша"),
        "русский": ("русский", "russian", "орыс", "орысша"),
    },
}

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_RU_ENDINGS = (
    "ого", "его", "ому", "ему", "ыми", "ими", "ий", "ый", "ой", "ая", "яя",
    "ое", "ее", "ые", "ие", "ия", "ью", "ей", "у", "а", "я", "ы", "и", "е", "ь",
)


def words(value: str) -> tuple[str, ...]:
    folded = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return tuple(_TOKEN.findall(folded))


def _stem(word: str) -> str:
    for ending in _RU_ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[:-len(ending)]
    return word


def _distance_one(left: str, right: str) -> bool:
    """One insertion, deletion, substitution or neighboring transposition."""
    if left == right:
        return True
    if min(len(left), len(right)) < 4 or abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        positions = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        return (len(positions) == 1 and len(left) >= 5) or (
            len(positions) == 2 and positions[1] == positions[0] + 1
            and left[positions[0]] == right[positions[1]]
            and left[positions[1]] == right[positions[0]]
        )
    if len(left) > len(right):
        left, right = right, left
    return any(left == right[:i] + right[i + 1:] for i in range(len(right)))


def _word_cost(alias: str, cited: str) -> int | None:
    if alias == cited:
        return 0
    # Only known catalog words may be inflected or corrected. A word must
    # still match the whole cited token; arbitrary substrings are not evidence.
    if len(alias) >= 4 and _stem(alias) == _stem(cited):
        return 0
    if alias == "той" and cited.startswith("той"):
        return 0
    if alias == "алматы" and cited.startswith("алматы"):
        return 0
    if _distance_one(alias, cited):
        return 1
    return None


def _score(alias: str, evidence_words: tuple[str, ...]) -> tuple[int, int] | None:
    tokens = words(alias)
    if not tokens or len(tokens) > len(evidence_words):
        return None
    best: tuple[int, int] | None = None
    for start in range(len(evidence_words) - len(tokens) + 1):
        costs = [_word_cost(a, b) for a, b in zip(tokens, evidence_words[start:])]
        if any(cost is None for cost in costs):
            continue
        candidate = (len(tokens), -sum(costs))
        if best is None or candidate > best:
            best = candidate
    return best


def supports(field: str, canonical: str, evidence: str, available: list[str] | None = None) -> bool:
    """Accept only a unique best catalog interpretation of the cited phrase."""
    variants = ALIASES.get(field, {})
    names = available if available is not None else list(variants)
    evidence_words = words(evidence)
    scored: dict[str, tuple[int, int]] = {}
    for name in names:
        aliases = variants.get(name, (name,))
        if name not in aliases:
            aliases = (*aliases, name)
        best = max((score for alias in aliases if (score := _score(alias, evidence_words)) is not None), default=None)
        if best is not None:
            scored[name] = best
    if canonical not in scored:
        return False
    highest = max(scored.values())
    return scored[canonical] == highest and list(scored.values()).count(highest) == 1
