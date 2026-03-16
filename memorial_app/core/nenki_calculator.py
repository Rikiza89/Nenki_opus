"""Nenki (年忌) memorial anniversary calculator.

Calculates traditional Japanese Buddhist memorial schedule from a death date.
"""

import datetime
from dataclasses import dataclass


@dataclass
class NenkiAnniversary:
    name: str  # e.g. "一周忌"
    date: datetime.date  # Anniversary date
    years_offset: int  # Offset from death year
    death_date: datetime.date


# Standard Nenki schedule: (name, years_offset_from_death_year)
# 百ヶ日 is special (99 days from death), handled separately.
STANDARD_NENKI = [
    ("一周忌", 1),
    ("三回忌", 2),
    ("七回忌", 6),
    ("十三回忌", 12),
    ("十七回忌", 16),
    ("二十三回忌", 22),
    ("二十五回忌", 24),
    ("二十七回忌", 26),
    ("三十三回忌", 32),
    ("三十七回忌", 36),
    ("四十三回忌", 42),
    ("四十七回忌", 46),
    ("五十回忌", 49),
]

# Default pre-checked nenki types for document generation
DEFAULT_SELECTED_NENKI = [
    "一周忌",
    "三回忌",
    "七回忌",
    "十三回忌",
    "十七回忌",
    "二十五回忌",
    "二十七回忌",
    "三十三回忌",
    "五十回忌",
]


def _year_offset_to_name(offset: int) -> str:
    """Generate nenki name for offsets beyond the standard list (every 50 years after 五十回忌)."""
    kanji_map = {
        100: "百回忌",
        150: "百五十回忌",
        200: "二百回忌",
    }
    actual_kaiki = offset + 1
    return kanji_map.get(actual_kaiki, f"{actual_kaiki}回忌")


def calculate_all_anniversaries(
    death_date: datetime.date, max_year: int | None = None
) -> list[NenkiAnniversary]:
    """Calculate all Nenki anniversaries for a given death date.

    Args:
        death_date: The date of death.
        max_year: Optional maximum Gregorian year to calculate up to.
                  If None, calculates through 五十回忌 + 50-year cycles up to 200 years.

    Returns:
        List of NenkiAnniversary sorted by date.
    """
    results = []

    # 百ヶ日 (99 days after death)
    hyakkanichi = death_date + datetime.timedelta(days=99)
    if max_year is None or hyakkanichi.year <= max_year:
        results.append(NenkiAnniversary("百ヶ日", hyakkanichi, 0, death_date))

    # Standard anniversaries
    for name, offset in STANDARD_NENKI:
        ann_date = _anniversary_date(death_date, offset)
        if max_year is None or ann_date.year <= max_year:
            results.append(NenkiAnniversary(name, ann_date, offset, death_date))

    # Beyond 五十回忌: every 50 years
    if max_year is not None:
        offset = 99  # 百回忌 = death_year + 99
        while True:
            ann_date = _anniversary_date(death_date, offset)
            if ann_date.year > max_year:
                break
            name = _year_offset_to_name(offset)
            results.append(NenkiAnniversary(name, ann_date, offset, death_date))
            offset += 50
    else:
        # Default: calculate up to 200 years
        for offset in [99, 149, 199]:
            ann_date = _anniversary_date(death_date, offset)
            results.append(
                NenkiAnniversary(
                    name=_year_offset_to_name(offset),
                    date=ann_date,
                    years_offset=offset,
                    death_date=death_date,
                )
            )

    return sorted(results, key=lambda a: a.date)


def _anniversary_date(death_date: datetime.date, years_offset: int) -> datetime.date:
    """Calculate anniversary date: same month/day, offset years from death year."""
    target_year = death_date.year + years_offset
    # Handle Feb 29 edge case
    try:
        return death_date.replace(year=target_year)
    except ValueError:
        # Feb 29 in non-leap year → use Feb 28
        return datetime.date(target_year, 2, 28)


def get_anniversaries_for_year(
    death_date: datetime.date, target_year: int
) -> list[NenkiAnniversary]:
    """Get all Nenki anniversaries that fall in the specified year."""
    all_anns = calculate_all_anniversaries(death_date, max_year=target_year + 1)
    return [a for a in all_anns if a.date.year == target_year]


def get_anniversaries_in_range(
    death_date: datetime.date,
    start_date: datetime.date,
    end_date: datetime.date,
) -> list[NenkiAnniversary]:
    """Get all Nenki anniversaries that fall within a date range."""
    all_anns = calculate_all_anniversaries(death_date, max_year=end_date.year)
    return [a for a in all_anns if start_date <= a.date <= end_date]


def get_upcoming_anniversaries(
    death_date: datetime.date,
    months_ahead: int = 12,
    from_date: datetime.date | None = None,
) -> list[NenkiAnniversary]:
    """Get Nenki anniversaries in the next N months from a given date."""
    if from_date is None:
        from_date = datetime.date.today()
    end_date = _add_months(from_date, months_ahead)
    return get_anniversaries_in_range(death_date, from_date, end_date)


def _add_months(date: datetime.date, months: int) -> datetime.date:
    """Add months to a date."""
    month = date.month + months
    year = date.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    # Handle day overflow
    import calendar

    max_day = calendar.monthrange(year, month)[1]
    day = min(date.day, max_day)
    return datetime.date(year, month, day)
