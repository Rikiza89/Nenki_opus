import datetime
from .era_converter import gregorian_to_era

_DIGIT_KANJI = {'0': '〇', '1': '一', '2': '二', '3': '三', '4': '四',
                '5': '五', '6': '六', '7': '七', '8': '八', '9': '九'}

_TENS = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九']
_ONES = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九']


def number_to_counter_kanji(n: int) -> str:
    if n <= 0:
        return '〇'
    if n >= 100:
        return ''.join(_DIGIT_KANJI[c] for c in str(n))
    tens = n // 10
    ones = n % 10
    result = ''
    if tens == 1:
        result += '十'
    elif tens > 1:
        result += _TENS[tens] + '十'
    result += _ONES[ones]
    return result


def format_date_kanji_era(date: datetime.date) -> str:
    era, year = gregorian_to_era(date)
    if not era:
        return str(date)
    year_str = '元' if year == 1 else number_to_counter_kanji(year)
    month_str = number_to_counter_kanji(date.month)
    day_str = number_to_counter_kanji(date.day)
    return f"{era.name}{year_str}年{month_str}月{day_str}日"
