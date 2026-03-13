"""Tests for the kanji number conversion and date formatting module."""

import datetime
import pytest

from memorial_app.core.date_converter import (
    digits_to_kanji, number_to_counter_kanji, year_to_kanji,
    format_date_kanji_era, format_year_kanji_era, format_nenki_title,
)


class TestDigitsToKanji:
    def test_single_digit(self):
        assert digits_to_kanji(5) == "五"

    def test_year(self):
        assert digits_to_kanji(2026) == "二〇二六"

    def test_zero(self):
        assert digits_to_kanji(0) == "〇"

    def test_string_input(self):
        assert digits_to_kanji("2026") == "二〇二六"


class TestNumberToCounterKanji:
    def test_one(self):
        assert number_to_counter_kanji(1) == "一"

    def test_ten(self):
        assert number_to_counter_kanji(10) == "十"

    def test_twelve(self):
        assert number_to_counter_kanji(12) == "十二"

    def test_twenty(self):
        assert number_to_counter_kanji(20) == "二十"

    def test_thirty_one(self):
        assert number_to_counter_kanji(31) == "三十一"

    def test_out_of_range_fallback(self):
        assert number_to_counter_kanji(100) == "一〇〇"


class TestFormatDateKanjiEra:
    def test_standard_date(self):
        result = format_date_kanji_era(datetime.date(2026, 3, 13))
        assert result == "令和八年三月十三日"

    def test_gannen(self):
        result = format_date_kanji_era(datetime.date(2019, 5, 1))
        assert result == "令和元年五月一日"

    def test_showa(self):
        result = format_date_kanji_era(datetime.date(1945, 8, 15))
        assert result == "昭和二十年八月十五日"

    def test_december_31(self):
        result = format_date_kanji_era(datetime.date(2026, 12, 31))
        assert result == "令和八年十二月三十一日"


class TestFormatYearKanjiEra:
    def test_with_int(self):
        result = format_year_kanji_era(2026)
        assert result == "令和八年"

    def test_with_date(self):
        result = format_year_kanji_era(datetime.date(2026, 6, 1))
        assert result == "令和八年"

    def test_gannen(self):
        # 2019-05-01 is Reiwa gannen; using Jan 1 2019 would be Heisei 31
        result = format_year_kanji_era(datetime.date(2019, 5, 1))
        assert result == "令和元年"


class TestFormatNenkiTitle:
    def test_title_format(self):
        result = format_nenki_title(2026)
        assert result == "年忌表 - 令和八年の年忌法要"
