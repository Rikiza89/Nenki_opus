"""Tests for the Japanese date parser module."""

import datetime
import pytest

from memorial_app.core.japanese_date_parser import parse_date, parse_date_from_columns, DateValidationError


class TestEraTextParsing:
    def test_reiwa_numeric(self):
        result = parse_date("令和3年5月1日")
        assert result.date == datetime.date(2021, 5, 1)

    def test_heisei_gannen(self):
        result = parse_date("平成元年1月8日")
        assert result.date == datetime.date(1989, 1, 8)

    def test_showa(self):
        result = parse_date("昭和20年8月15日")
        assert result.date == datetime.date(1945, 8, 15)

    def test_year_month_only(self):
        result = parse_date("令和3年5月")
        assert result.date == datetime.date(2021, 5, 1)

    def test_year_only(self):
        result = parse_date("令和3年")
        assert result.date == datetime.date(2021, 1, 1)


class TestEraAbbreviation:
    def test_dot_separator(self):
        result = parse_date("R3.5.1")
        assert result.date == datetime.date(2021, 5, 1)

    def test_slash_separator(self):
        result = parse_date("H30/12/1")
        assert result.date == datetime.date(2018, 12, 1)

    def test_year_only(self):
        result = parse_date("S64")
        assert result.date == datetime.date(1989, 1, 1)


class TestRomanizedEra:
    def test_reiwa(self):
        result = parse_date("Reiwa 3")
        assert result.date == datetime.date(2021, 1, 1)

    def test_heisei_with_date(self):
        result = parse_date("Heisei 1 1 8")
        assert result.date == datetime.date(1989, 1, 8)


class TestGregorianParsing:
    def test_iso_format(self):
        result = parse_date("2021-05-01")
        assert result.date == datetime.date(2021, 5, 1)

    def test_slash_format(self):
        result = parse_date("2021/5/1")
        assert result.date == datetime.date(2021, 5, 1)

    def test_compact_format(self):
        result = parse_date("20210501")
        assert result.date == datetime.date(2021, 5, 1)


class TestKanjiTextParsing:
    def test_full_kanji(self):
        result = parse_date("令和三年五月一日")
        assert result.date == datetime.date(2021, 5, 1)

    def test_kanji_gannen(self):
        # "元" in era text parser is handled by _parse_era_text since 元 matches the pattern
        result = parse_date("令和元年五月一日")
        assert result.date == datetime.date(2019, 5, 1)

    def test_counter_style_kanji(self):
        result = parse_date("昭和二十年八月十五日")
        assert result.date == datetime.date(1945, 8, 15)


class TestExcelSerial:
    def test_known_date(self):
        # 44317 = 2021-05-01 in Excel serial
        result = parse_date("44317")
        assert result.date == datetime.date(2021, 5, 1)

    def test_early_date(self):
        # 1 = 1900-01-01 in Excel serial
        result = parse_date("1")
        assert result.date == datetime.date(1900, 1, 1)


class TestSplitColumns:
    def test_era_with_year(self):
        result = parse_date_from_columns(3, 5, 1, "令和")
        assert result.date == datetime.date(2021, 5, 1)

    def test_gregorian_year(self):
        result = parse_date_from_columns(2021, 5, 1)
        assert result.date == datetime.date(2021, 5, 1)

    def test_era_abbreviation(self):
        result = parse_date_from_columns(3, 5, 1, "R")
        assert result.date == datetime.date(2021, 5, 1)


class TestEdgeCases:
    def test_empty_raises(self):
        with pytest.raises(DateValidationError, match="日付が空です"):
            parse_date("")

    def test_none_raises(self):
        with pytest.raises(DateValidationError, match="日付が空です"):
            parse_date(None)

    def test_garbage_raises(self):
        with pytest.raises(DateValidationError, match="日付を解析できません"):
            parse_date("これは日付ではない")

    def test_parsed_date_has_era_display(self):
        result = parse_date("2026-03-13")
        assert "令和" in result.era_display
        assert result.original == "2026-03-13"
