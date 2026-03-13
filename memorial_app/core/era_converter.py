"""Japanese era (元号) converter - handles conversion between Gregorian and Japanese era dates."""

import json
import datetime
from pathlib import Path
from dataclasses import dataclass

# Default config path for custom eras
_CONFIG_DIR = Path.home() / ".nenki_app"
_ERA_CONFIG_PATH = _CONFIG_DIR / "custom_eras.json"


@dataclass
class Era:
    name: str          # 令和
    abbreviation: str  # R
    start_date: datetime.date

    @property
    def reading(self) -> str:
        """Romanized reading for regex matching."""
        return _ERA_READINGS.get(self.name, "")


# Built-in eras (newest first for priority matching)
_ERA_READINGS = {
    "令和": "Reiwa",
    "平成": "Heisei",
    "昭和": "Showa",
    "大正": "Taisho",
    "明治": "Meiji",
}

BUILTIN_ERAS = [
    Era("令和", "R", datetime.date(2019, 5, 1)),
    Era("平成", "H", datetime.date(1989, 1, 8)),
    Era("昭和", "S", datetime.date(1926, 12, 25)),
    Era("大正", "T", datetime.date(1912, 7, 30)),
    Era("明治", "M", datetime.date(1868, 9, 8)),
]

# Module-level era list (built-in + custom, sorted newest first)
_eras: list[Era] = []


def _load_custom_eras() -> list[Era]:
    """Load user-defined custom eras from JSON config."""
    if not _ERA_CONFIG_PATH.exists():
        return []
    try:
        data = json.loads(_ERA_CONFIG_PATH.read_text(encoding="utf-8"))
        custom = []
        for e in data:
            custom.append(Era(
                name=e["name"],
                abbreviation=e["abbreviation"],
                start_date=datetime.date.fromisoformat(e["start_date"]),
            ))
        return custom
    except (json.JSONDecodeError, KeyError, ValueError):
        return []


def save_custom_eras(eras: list[Era]) -> None:
    """Save custom eras to JSON config."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = [
        {"name": e.name, "abbreviation": e.abbreviation, "start_date": e.start_date.isoformat()}
        for e in eras
    ]
    _ERA_CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    reload_eras()


def reload_eras() -> None:
    """Reload era list from built-in + custom config."""
    global _eras
    custom = _load_custom_eras()
    _eras = sorted(custom + BUILTIN_ERAS, key=lambda e: e.start_date, reverse=True)


def get_eras() -> list[Era]:
    """Get all eras sorted by start_date descending (newest first)."""
    if not _eras:
        reload_eras()
    return _eras


def get_custom_eras() -> list[Era]:
    """Get only user-defined custom eras."""
    return _load_custom_eras()


def gregorian_to_era(date: datetime.date) -> tuple[Era, int]:
    """Convert Gregorian date to (Era, year_in_era).

    Returns the matching era and the year number within that era.
    Year 1 of an era is 元年.

    Raises:
        ValueError: if date is before 明治 start and no custom era covers it.
    """
    for era in get_eras():
        if date >= era.start_date:
            # Era year = gregorian_year - start_year + 1
            # In the start year, only dates >= start_date belong to this era (元年)
            # From the next year onward, all dates belong to this era
            year = date.year - era.start_date.year + 1
            return era, year
    raise ValueError(f"日付 {date.isoformat()} に該当する元号がありません")


def era_to_gregorian(era_name: str, era_year: int, month: int, day: int) -> datetime.date:
    """Convert era name + year + month + day to Gregorian date.

    Args:
        era_name: Era name (e.g. "令和") or abbreviation (e.g. "R")
        era_year: Year within the era (1 = 元年)
        month: Month (1-12)
        day: Day (1-31)

    Raises:
        ValueError: if era not found or date invalid.
    """
    era = find_era(era_name)
    if era is None:
        raise ValueError(f"不明な元号: {era_name}")
    gregorian_year = era.start_date.year + era_year - 1
    try:
        return datetime.date(gregorian_year, month, day)
    except ValueError:
        raise ValueError(f"無効な日付: {era_name}{era_year}年{month}月{day}日")


def find_era(name_or_abbr: str) -> Era | None:
    """Find era by name, abbreviation, or romanized reading (case-insensitive)."""
    key = name_or_abbr.strip()
    key_lower = key.lower()
    for era in get_eras():
        if key == era.name or key.upper() == era.abbreviation:
            return era
        if era.reading and key_lower == era.reading.lower():
            return era
    return None


def format_era_year(era: Era, year: int) -> str:
    """Format era year with 元年 handling. e.g. (令和, 1) -> '令和元年'"""
    if year == 1:
        return f"{era.name}元年"
    return f"{era.name}{year}年"


def format_date_era(date: datetime.date) -> str:
    """Format date as full era string. e.g. 2025-05-01 -> '令和7年5月1日'"""
    era, year = gregorian_to_era(date)
    year_str = "元" if year == 1 else str(year)
    return f"{era.name}{year_str}年{date.month}月{date.day}日"
