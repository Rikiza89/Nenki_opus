import datetime
from dataclasses import dataclass
from .date_converter import format_date_kanji_era

STANDARD_NENKI = [
    ("一周忌", 1),
    ("三回忌", 2),
    ("七回忌", 6),
    ("十三回忌", 12),
    ("十七回忌", 16),
    ("二十三回忌", 22),
    ("二十七回忌", 26),
    ("三十三回忌", 32),
    ("三十七回忌", 36),
    ("五十回忌", 49),
]


@dataclass
class NenkiAnniversary:
    name: str
    date: datetime.date
    years_offset: int
    death_date: datetime.date


def _anniversary_date(death_date: datetime.date, years_offset: int) -> datetime.date:
    target_year = death_date.year + years_offset
    try:
        return death_date.replace(year=target_year)
    except ValueError:
        return datetime.date(target_year, 2, 28)


def calculate_all_anniversaries(death_date: datetime.date, max_year: int = None):
    results = []

    # 百ヶ日: 99 days after death
    hyakka = death_date + datetime.timedelta(days=99)
    results.append(NenkiAnniversary("百ヶ日", hyakka, 0, death_date))

    for name, offset in STANDARD_NENKI:
        date = _anniversary_date(death_date, offset)
        results.append(NenkiAnniversary(name, date, offset, death_date))

    # Extend beyond 五十回忌 in 50-year increments
    if max_year:
        base_offset = 49
        while True:
            base_offset += 50
            year = death_date.year + base_offset
            if year > max_year:
                break
            kanji_num = str(base_offset + 1)
            name = f"{kanji_num}回忌"
            date = _anniversary_date(death_date, base_offset)
            results.append(NenkiAnniversary(name, date, base_offset, death_date))

    return sorted(results, key=lambda a: a.date)


def get_anniversaries_for_year(death_date: datetime.date, target_year: int):
    all_ann = calculate_all_anniversaries(death_date, max_year=target_year + 100)
    return [a for a in all_ann if a.date.year == target_year]


def format_anniversary(ann: NenkiAnniversary) -> dict:
    return {
        "name": ann.name,
        "date": ann.date.isoformat(),
        "date_kanji": format_date_kanji_era(ann.date),
        "years_offset": ann.years_offset,
        "death_date": ann.death_date.isoformat(),
        "death_date_kanji": format_date_kanji_era(ann.death_date),
    }
