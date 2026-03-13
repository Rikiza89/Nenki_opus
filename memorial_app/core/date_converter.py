"""Kanji number conversion and Japanese date formatting utilities."""

import datetime
from memorial_app.core.era_converter import gregorian_to_era

# Digit to kanji mapping
_DIGIT_KANJI = {
    "0": "〇", "1": "一", "2": "二", "3": "三", "4": "四",
    "5": "五", "6": "六", "7": "七", "8": "八", "9": "九",
}

# Counter-style kanji for numbers 1-99 (used in dates: months, days, years within era)
_TENS = ["", "十", "二十", "三十", "四十", "五十", "六十", "七十", "八十", "九十"]
_ONES = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]


def digits_to_kanji(n: int | str) -> str:
    """Convert number to positional kanji (digit by digit).

    Example: 2026 -> '二〇二六', 12 -> '一二'
    """
    return "".join(_DIGIT_KANJI.get(ch, ch) for ch in str(n))


def number_to_counter_kanji(n: int) -> str:
    """Convert number (1-99) to counter-style kanji.

    Example: 1 -> '一', 12 -> '十二', 20 -> '二十', 31 -> '三十一'
    Special: 10 -> '十' (not '一十')
    """
    if n <= 0 or n > 99:
        return digits_to_kanji(n)
    tens = n // 10
    ones = n % 10
    result = _TENS[tens] + _ONES[ones]
    return result


def year_to_kanji(year: int) -> str:
    """Convert a 4-digit Gregorian year to positional kanji.

    Example: 2026 -> '二〇二六'
    """
    return digits_to_kanji(year)


def format_date_kanji_era(date: datetime.date) -> str:
    """Format date as full era string with kanji numbers.

    Example: 2026-12-31 -> '令和八年十二月三十一日'
    """
    era, year = gregorian_to_era(date)
    if year == 1:
        year_str = "元"
    else:
        year_str = number_to_counter_kanji(year)
    month_str = number_to_counter_kanji(date.month)
    day_str = number_to_counter_kanji(date.day)
    return f"{era.name}{year_str}年{month_str}月{day_str}日"


def format_year_kanji_era(date_or_year) -> str:
    """Format a year as era with kanji. Accepts date or int year.

    Example: 2026 -> '令和八年', datetime.date(2026,1,1) -> '令和八年'
    """
    if isinstance(date_or_year, int):
        date = datetime.date(date_or_year, 1, 1)
    else:
        date = date_or_year
    era, year = gregorian_to_era(date)
    if year == 1:
        return f"{era.name}元年"
    return f"{era.name}{number_to_counter_kanji(year)}年"


def format_nenki_title(target_year: int) -> str:
    """Format the nenki table title with kanji era year.

    Example: 2026 -> '年忌表 - 令和八年の年忌法要'
    """
    era_year = format_year_kanji_era(target_year)
    return f"年忌表 - {era_year}の年忌法要"
