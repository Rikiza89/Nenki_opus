"""Robust Japanese date parser - handles all era formats, Gregorian, Excel serial, kanji text.

Priority-based detection:
1. Japanese era text (令和3年5月1日, 平成元年...)
2. Era abbreviations (R3.5.1, H30, S64)
3. Romanized era (Reiwa 3, Heisei 1)
4. Gregorian formats (YYYY-MM-DD, YYYY/MM/DD, YYYYMMDD)
5. Excel serial date numbers
6. Japanese kanji text dates (令和三年五月一日)
"""

import re
import datetime
from dataclasses import dataclass

from memorial_app.core.era_converter import (
    get_eras,
    find_era,
    era_to_gregorian,
    format_date_era,
)


class DateValidationError(Exception):
    """Raised when a date string cannot be parsed. Message is in Japanese."""

    pass


@dataclass
class ParsedDate:
    date: datetime.date
    era_display: str  # e.g. "令和7年5月1日"
    original: str  # the original input string


# Kanji digit mapping for parsing
_KANJI_DIGITS = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "百": 100,
}


def _kanji_to_int(text: str) -> int | None:
    """Convert kanji number string to int. Handles counter-style (十二=12) and positional (一二=12)."""
    if not text:
        return None
    # Check for 元 (gannen = year 1)
    if text.strip() == "元":
        return 1

    # Try counter-style first (e.g., 十二, 二十三, 三十)
    total = 0
    current = 0
    has_counter = "十" in text or "百" in text

    if has_counter:
        for ch in text:
            if ch == "十":
                total += (current if current else 1) * 10
                current = 0
            elif ch == "百":
                total += (current if current else 1) * 100
                current = 0
            elif ch in _KANJI_DIGITS:
                current = _KANJI_DIGITS[ch]
            else:
                return None
        total += current
        return total if total > 0 else None

    # Positional style (一二三 = 123)
    digits = []
    for ch in text:
        if ch in _KANJI_DIGITS:
            digits.append(_KANJI_DIGITS[ch])
        else:
            return None
    if not digits:
        return None
    result = 0
    for d in digits:
        result = result * 10 + d
    return result


def _parse_era_text(text: str) -> ParsedDate | None:
    """Parse Japanese era text: 令和3年5月1日, 平成元年5月1日, etc."""
    for era in get_eras():
        # Pattern: 元号 + (数字|元)年 + optional 月日
        pattern = (
            rf"{re.escape(era.name)}\s*(\d+|元)\s*年"
            rf"(?:\s*(\d+)\s*月(?:\s*(\d+)\s*日)?)?"
        )
        m = re.search(pattern, text)
        if m:
            year_str = m.group(1)
            year = 1 if year_str == "元" else int(year_str)
            month = int(m.group(2)) if m.group(2) else None
            day = int(m.group(3)) if m.group(3) else None
            # If month wasn't captured but there's kanji text after 年, skip to kanji parser
            if month is None:
                after_match = text[m.end() :]
                if re.search(r"[〇零一二三四五六七八九十百]+\s*月", after_match):
                    continue
            if month is None:
                month = 1
            if day is None:
                day = 1
            try:
                d = era_to_gregorian(era.name, year, month, day)
                return ParsedDate(d, format_date_era(d), text)
            except ValueError:
                continue
    return None


def _parse_era_abbreviation(text: str) -> ParsedDate | None:
    """Parse era abbreviations: R3.5.1, H30, S64.1.7, R1/5/1, etc."""
    for era in get_eras():
        abbr = era.abbreviation
        # Pattern: R3.5.1 or R3/5/1 or R3-5-1 or just R3
        pattern = (
            rf"(?:^|(?<=\s)){re.escape(abbr)}\s*(\d+)"
            rf"(?:[./\-]\s*(\d+)(?:[./\-]\s*(\d+))?)?"
        )
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            month = int(m.group(2)) if m.group(2) else 1
            day = int(m.group(3)) if m.group(3) else 1
            try:
                d = era_to_gregorian(era.name, year, month, day)
                return ParsedDate(d, format_date_era(d), text)
            except ValueError:
                continue
    return None


def _parse_romanized_era(text: str) -> ParsedDate | None:
    """Parse romanized era: Reiwa 3, Heisei 1, Showa 64, etc."""
    for era in get_eras():
        reading = era.reading
        if not reading:
            continue
        pattern = rf"{re.escape(reading)}\s+(\d+)(?:\s+(\d+)\s+(\d+))?"
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            month = int(m.group(2)) if m.group(2) else 1
            day = int(m.group(3)) if m.group(3) else 1
            try:
                d = era_to_gregorian(era.name, year, month, day)
                return ParsedDate(d, format_date_era(d), text)
            except ValueError:
                continue
    return None


def _parse_gregorian(text: str) -> ParsedDate | None:
    """Parse Gregorian: YYYY-MM-DD, YYYY/MM/DD, YYYYMMDD, YYYY.MM.DD."""
    # YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
    m = re.search(r"(\d{4})[/\-.\s](\d{1,2})[/\-.\s](\d{1,2})", text)
    if m:
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return ParsedDate(d, format_date_era(d), text)
        except ValueError:
            pass

    # YYYYMMDD (8 digits)
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", text.strip())
    if m:
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return ParsedDate(d, format_date_era(d), text)
        except ValueError:
            pass

    return None


def _parse_excel_serial(text: str) -> ParsedDate | None:
    """Parse Excel serial date number."""
    text = text.strip()
    try:
        serial = float(text)
    except ValueError:
        return None

    if serial < 1 or serial > 200000:
        return None

    # Excel serial: 1 = 1900-01-01, but Excel has the 1900 leap year bug
    try:
        if serial > 59:
            serial -= 1  # Adjust for Excel's erroneous Feb 29, 1900
        base = datetime.date(1899, 12, 31)
        d = base + datetime.timedelta(days=int(serial))
        # Sanity check: must be a reasonable date
        if d.year < 1868 or d.year > 2200:
            return None
        return ParsedDate(d, format_date_era(d), text)
    except (OverflowError, ValueError):
        return None


def _parse_kanji_text(text: str) -> ParsedDate | None:
    """Parse full kanji text dates: 令和三年五月一日, 令和元年五月一日."""
    for era in get_eras():
        # Match era name + kanji year + optional kanji month/day
        pattern = (
            rf"{re.escape(era.name)}\s*([〇零一二三四五六七八九十百元]+)\s*年"
            rf"(?:\s*([〇零一二三四五六七八九十百]+)\s*月"
            rf"(?:\s*([〇零一二三四五六七八九十百]+)\s*日)?)?"
        )
        m = re.search(pattern, text)
        if m:
            year = _kanji_to_int(m.group(1))
            if year is None:
                continue
            month = _kanji_to_int(m.group(2)) if m.group(2) else 1
            day = _kanji_to_int(m.group(3)) if m.group(3) else 1
            if month is None:
                month = 1
            if day is None:
                day = 1
            try:
                d = era_to_gregorian(era.name, year, month, day)
                return ParsedDate(d, format_date_era(d), text)
            except ValueError:
                continue
    return None


def _parse_split_columns(
    year_val, month_val, day_val, era_val=None
) -> ParsedDate | None:
    """Parse date from separate columns (号年、月、日 pattern).

    Args:
        year_val: Year value (could be era year or gregorian)
        month_val: Month value
        day_val: Day value
        era_val: Optional era name/abbreviation
    """
    try:
        year = int(str(year_val).strip()) if year_val else None
        month = int(str(month_val).strip()) if month_val else 1
        day = int(str(day_val).strip()) if day_val else 1
    except (ValueError, TypeError):
        return None

    if year is None:
        return None

    if era_val:
        era_str = str(era_val).strip()
        era = find_era(era_str)
        if era:
            try:
                d = era_to_gregorian(era.name, year, month, day)
                return ParsedDate(
                    d, format_date_era(d), f"{era_str}{year}年{month}月{day}日"
                )
            except ValueError:
                return None

    # If year looks like Gregorian (>= 1868)
    if year >= 1868:
        try:
            d = datetime.date(year, month, day)
            return ParsedDate(d, format_date_era(d), f"{year}年{month}月{day}日")
        except ValueError:
            return None

    return None


def parse_date(text: str) -> ParsedDate:
    """Parse a date string using priority-based detection.

    Tries: era text → abbreviation → romanized → gregorian → excel serial → kanji text.

    Args:
        text: The date string to parse.

    Returns:
        ParsedDate with date, era_display, and original string.

    Raises:
        DateValidationError: If the date cannot be parsed (Japanese error message).
    """
    if text is None:
        raise DateValidationError("日付が空です")

    text = str(text).strip()
    if not text:
        raise DateValidationError("日付が空です")

    # Try each parser in priority order
    parsers = [
        _parse_era_text,
        _parse_era_abbreviation,
        _parse_romanized_era,
        _parse_gregorian,
        _parse_kanji_text,
        _parse_excel_serial,
    ]

    for parser in parsers:
        result = parser(text)
        if result is not None:
            return result

    raise DateValidationError(f"日付を解析できません: 「{text}」")


def parse_date_from_columns(year_val, month_val, day_val, era_val=None) -> ParsedDate:
    """Parse date from separate column values.

    Raises:
        DateValidationError: If values cannot form a valid date.
    """
    result = _parse_split_columns(year_val, month_val, day_val, era_val)
    if result is not None:
        return result
    raise DateValidationError(
        f"分割された日付を解析できません: 年={year_val}, 月={month_val}, 日={day_val}"
    )
