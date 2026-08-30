"""Deterministic per-document pseudonym registry."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from pii.normalize import normalize_value


@dataclass
class PseudonymRegistry:
    """Per-document registry mapping (normalized_value, category) → pseudonym.

    Pseudonyms are generated deterministically from a hash of (doc_id, normalized_value, category),
    ensuring reproducibility and within-document consistency.
    """
    doc_id: str
    locale: str = "ru"
    _cache: dict[tuple[str, str], str] = field(default_factory=dict)
    _counter: dict[str, int] = field(default_factory=dict)

    def get_pseudonym(self, original_value: str, category: str) -> str:
        """Get or generate a deterministic pseudonym for (value, category) within this document."""
        norm = normalize_value(original_value)
        key = (norm, category)

        if key in self._cache:
            return self._cache[key]

        seed = _make_seed(self.doc_id, norm, category)
        pseudonym = _generate_pseudonym(seed, category, self._counter, self.locale)
        self._cache[key] = pseudonym
        return pseudonym

    def get_all(self) -> dict[tuple[str, str], str]:
        return dict(self._cache)


def _make_seed(doc_id: str, normalized_value: str, category: str) -> str:
    raw = f"{doc_id}:{normalized_value}:{category}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Russian dictionaries ──

RU_FIRST_NAMES = [
    "Александр", "Дмитрий", "Максим", "Сергей", "Андрей",
    "Алексей", "Артём", "Илья", "Кирилл", "Михаил",
    "Елена", "Анна", "Мария", "Ольга", "Наталья",
    "Татьяна", "Ирина", "Светлана", "Юлия", "Екатерина",
]
RU_LAST_NAMES = [
    "Соколов", "Волков", "Козлов", "Лебедев", "Новиков",
    "Морозов", "Петров", "Сидоров", "Фёдоров", "Смирнов",
    "Соколова", "Волкова", "Козлова", "Лебедева", "Новикова",
    "Морозова", "Петрова", "Сидорова", "Фёдорова", "Смирнова",
]
RU_PATRONYMICS = [
    "Александрович", "Дмитриевич", "Сергеевич", "Андреевич", "Михайлович",
    "Николаевич", "Владимирович", "Петрович", "Иванович", "Алексеевич",
    "Александровна", "Дмитриевна", "Сергеевна", "Андреевна", "Михайловна",
    "Николаевна", "Владимировна", "Петровна", "Ивановна", "Алексеевна",
]
RU_CITIES = [
    "г. Москва", "г. Санкт-Петербург", "г. Новосибирск", "г. Екатеринбург",
    "г. Казань", "г. Нижний Новгород", "г. Челябинск", "г. Самара",
    "г. Омск", "г. Ростов-на-Дону",
]
RU_STREETS = [
    "ул. Ленина", "ул. Пушкина", "ул. Мира", "ул. Советская",
    "ул. Гагарина", "пр. Октябрьский", "ул. Садовая", "ул. Центральная",
]
RU_ORGS = [
    "ООО «Техносервис»", "АО «Информсистемы»", "ПАО «Данные»",
    "ООО «Консалтинг»", "АО «Разработка»",
]

# ── English dictionaries ──

EN_FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William",
    "David", "Richard", "Joseph", "Thomas", "Charles",
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth",
    "Barbara", "Susan", "Jessica", "Sarah", "Karen",
]
EN_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones",
    "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Anderson", "Taylor", "Thomas", "Moore", "Jackson",
    "Martin", "Lee", "Thompson", "White", "Harris",
]
EN_CITIES = [
    "New York, NY", "Los Angeles, CA", "Chicago, IL",
    "Houston, TX", "Phoenix, AZ", "Philadelphia, PA",
    "San Antonio, TX", "San Diego, CA", "Dallas, TX",
    "Austin, TX",
]
EN_STREETS = [
    "Main St", "Oak Ave", "Maple Dr", "Cedar Ln",
    "Elm St", "Park Ave", "Washington Blvd", "Lincoln Rd",
]
EN_ORGS = [
    "Acme Corp", "GlobalTech Inc", "Summit Solutions LLC",
    "Pinnacle Group", "Vertex Systems", "Apex Industries",
]


def _is_english_locale(locale: str) -> bool:
    loc = locale.lower().replace("-", "_")
    return loc in ("en", "us", "en_us", "en_gb", "en_au", "en_ca") or loc.startswith("en")


def _generate_pseudonym(
    seed: str, category: str, counter: dict[str, int], locale: str = "ru",
) -> str:
    """Generate a category-appropriate pseudonym from a hex seed."""
    idx = int(seed[:8], 16)
    en = _is_english_locale(locale)

    if category in ("PERSON_NAME", "PERSON", "NAME",
                     "first_name", "last_name", "middle_name",
                     "full_name", "user_name"):
        if en:
            first = EN_FIRST_NAMES[idx % len(EN_FIRST_NAMES)]
            last = EN_LAST_NAMES[(idx >> 8) % len(EN_LAST_NAMES)]
            return f"{first} {last}"
        first = RU_FIRST_NAMES[idx % len(RU_FIRST_NAMES)]
        last = RU_LAST_NAMES[(idx >> 8) % len(RU_LAST_NAMES)]
        patr = RU_PATRONYMICS[(idx >> 16) % len(RU_PATRONYMICS)]
        return f"{last} {first} {patr}"

    if category in ("ADDRESS", "street_address", "city", "state",
                     "country", "county", "postcode"):
        if en:
            street = EN_STREETS[idx % len(EN_STREETS)]
            city = EN_CITIES[(idx >> 8) % len(EN_CITIES)]
            bld = (idx >> 16) % 200 + 1
            return f"{bld} {street}, {city}"
        city = RU_CITIES[idx % len(RU_CITIES)]
        street = RU_STREETS[(idx >> 8) % len(RU_STREETS)]
        bld = (idx >> 16) % 50 + 1
        return f"{city}, {street}, д.{bld}"

    if category in ("DATE_OF_BIRTH", "DATE", "date", "date_of_birth", "date_time"):
        day = (idx % 28) + 1
        month = ((idx >> 8) % 12) + 1
        if en:
            return f"{month:02d}/{day:02d}/1990"
        return f"{day:02d}.{month:02d}.1990"

    if category in ("EMAIL", "email"):
        local = seed[:8]
        domains = ["example.com", "mail.test", "sample.org"]
        domain = domains[(idx >> 8) % len(domains)]
        return f"{local}@{domain}"

    if category in ("HEALTHCARE_DATA", "MEDICAL_RECORD", "DIAGNOSIS",
                     "medical_record_number", "health_plan_beneficiary_number",
                     "blood_type"):
        return "[MEDICAL DATA]" if en else "[МЕДИЦИНСКИЕ ДАННЫЕ]"

    if category in ("ORGANIZATION", "COMPANY", "company_name"):
        if en:
            return EN_ORGS[idx % len(EN_ORGS)]
        return RU_ORGS[idx % len(RU_ORGS)]

    return "[REDACTED]"
