import datetime
from dataclasses import dataclass


@dataclass
class Era:
    name: str
    abbreviation: str
    start_date: datetime.date
    readings: list  # romanized readings


_BUILTIN_ERAS = [
    Era("令和", "R", datetime.date(2019, 5, 1), ["reiwa"]),
    Era("平成", "H", datetime.date(1989, 1, 8), ["heisei"]),
    Era("昭和", "S", datetime.date(1926, 12, 25), ["showa"]),
    Era("大正", "T", datetime.date(1912, 7, 30), ["taisho"]),
    Era("明治", "M", datetime.date(1868, 9, 8), ["meiji"]),
]


def get_eras():
    return sorted(_BUILTIN_ERAS, key=lambda e: e.start_date, reverse=True)


def find_era(name_or_abbr: str):
    s = name_or_abbr.strip()
    for era in get_eras():
        if s in (era.name, era.abbreviation, era.abbreviation.lower()):
            return era
        if s.lower() in era.readings:
            return era
    return None


def gregorian_to_era(date: datetime.date):
    for era in get_eras():
        if date >= era.start_date:
            year = date.year - era.start_date.year + 1
            return era, year
    return None, None


def era_to_gregorian(era_name: str, era_year: int, month: int, day: int):
    era = find_era(era_name)
    if not era:
        return None
    g_year = era.start_date.year + era_year - 1
    try:
        return datetime.date(g_year, month, day)
    except ValueError:
        return None
