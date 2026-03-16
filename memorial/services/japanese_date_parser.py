import datetime
import re
from dataclasses import dataclass
from .era_converter import find_era, get_eras, era_to_gregorian
from .date_converter import format_date_kanji_era

_KANJI_DIGITS = {
    '〇': 0, '零': 0, '○': 0, '0': 0,
    '一': 1, '壱': 1, '壹': 1, '1': 1,
    '二': 2, '弐': 2, '貳': 2, '2': 2,
    '三': 3, '参': 3, '參': 3, '3': 3,
    '四': 4, '4': 4, '五': 5, '5': 5,
    '六': 6, '6': 6, '七': 7, '7': 7,
    '八': 8, '8': 8, '九': 9, '9': 9,
}


@dataclass
class ParsedDate:
    date: datetime.date
    era_display: str
    original: str


def _kanji_to_int(text: str):
    text = text.strip()
    if not text:
        return None
    if text == '元':
        return 1
    has_counter = '十' in text or '百' in text
    if has_counter:
        total = 0
        current = 0
        for ch in text:
            if ch == '百':
                total += (current if current else 1) * 100
                current = 0
            elif ch == '十':
                total += (current if current else 1) * 10
                current = 0
            elif ch in _KANJI_DIGITS:
                current = _KANJI_DIGITS[ch]
            elif ch.isdigit():
                current = int(ch)
        total += current
        return total if total > 0 else None
    # Positional: convert each char
    digits = []
    for ch in text:
        if ch in _KANJI_DIGITS:
            digits.append(str(_KANJI_DIGITS[ch]))
        elif ch.isdigit():
            digits.append(ch)
        else:
            return None
    return int(''.join(digits)) if digits else None


def _make(date: datetime.date, original: str) -> ParsedDate:
    return ParsedDate(date=date, era_display=format_date_kanji_era(date), original=original)


def _parse_era_text(s: str):
    # 令和3年5月1日 or 令和三年五月一日
    for era in get_eras():
        pattern = re.compile(
            rf'{re.escape(era.name)}([元〇一二三四五六七八九十百壱弐参0-9]+)年'
            r'([元〇一二三四五六七八九十百0-9]+)月'
            r'([元〇一二三四五六七八九十百0-9]+)日'
        )
        m = pattern.search(s)
        if m:
            y = _kanji_to_int(m.group(1))
            mo = _kanji_to_int(m.group(2))
            d = _kanji_to_int(m.group(3))
            if y and mo and d:
                date = era_to_gregorian(era.name, y, mo, d)
                if date:
                    return _make(date, s)
    return None


def _parse_era_abbreviation(s: str):
    # R3.5.1 or H30-1-7
    m = re.match(r'^([RHSTMrhstm])(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{1,2})$', s.strip())
    if m:
        era = find_era(m.group(1).upper())
        if era:
            date = era_to_gregorian(era.name, int(m.group(2)), int(m.group(3)), int(m.group(4)))
            if date:
                return _make(date, s)
    return None


def _parse_gregorian(s: str):
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'):
        try:
            date = datetime.datetime.strptime(s.strip(), fmt).date()
            return _make(date, s)
        except ValueError:
            pass
    # YYYYMMDD
    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', s.strip())
    if m:
        try:
            date = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return _make(date, s)
        except ValueError:
            pass
    return None


def _parse_excel_serial(s: str):
    try:
        n = float(s.strip())
        if 1 <= n <= 2958465:
            # Excel epoch: 1899-12-30, but there's the 1900 leap year bug
            base = datetime.date(1899, 12, 30)
            date = base + datetime.timedelta(days=int(n))
            return _make(date, s)
    except (ValueError, TypeError):
        pass
    return None


def parse_date(s: str) -> ParsedDate | None:
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    for parser in [_parse_era_text, _parse_era_abbreviation, _parse_gregorian, _parse_excel_serial]:
        result = parser(s)
        if result:
            return result
    return None


def parse_split_columns(year_val, month_val, day_val, era_val=None) -> ParsedDate | None:
    try:
        month = int(float(str(month_val))) if month_val else None
        day = int(float(str(day_val))) if day_val else None
        if not month or not day:
            return None
        if era_val:
            era = find_era(str(era_val))
            if era:
                year = _kanji_to_int(str(year_val)) if year_val else None
                if year:
                    date = era_to_gregorian(era.name, year, month, day)
                    if date:
                        return _make(date, f"{era_val}{year_val}年{month_val}月{day_val}日")
        # Try as Gregorian year
        y = _kanji_to_int(str(year_val)) if year_val else None
        if y and y >= 1868:
            try:
                date = datetime.date(y, month, day)
                return _make(date, str(date))
            except ValueError:
                pass
    except (ValueError, TypeError):
        pass
    return None
