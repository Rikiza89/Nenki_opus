"""Tests for the Japanese era converter module."""

import datetime
import pytest

from memorial_app.core.era_converter import (
    gregorian_to_era, era_to_gregorian, find_era, format_date_era, format_era_year,
)


class TestGregorianToEra:
    def test_reiwa(self):
        era, year = gregorian_to_era(datetime.date(2026, 3, 13))
        assert era.name == "令和"
        assert year == 8

    def test_reiwa_gannen(self):
        era, year = gregorian_to_era(datetime.date(2019, 5, 1))
        assert era.name == "令和"
        assert year == 1

    def test_heisei(self):
        era, year = gregorian_to_era(datetime.date(2019, 4, 30))
        assert era.name == "平成"
        assert year == 31

    def test_heisei_gannen(self):
        era, year = gregorian_to_era(datetime.date(1989, 1, 8))
        assert era.name == "平成"
        assert year == 1

    def test_showa(self):
        era, year = gregorian_to_era(datetime.date(1989, 1, 7))
        assert era.name == "昭和"
        assert year == 64

    def test_showa_early(self):
        era, year = gregorian_to_era(datetime.date(1945, 8, 15))
        assert era.name == "昭和"
        assert year == 20

    def test_taisho(self):
        era, year = gregorian_to_era(datetime.date(1920, 6, 1))
        assert era.name == "大正"
        assert year == 9

    def test_meiji(self):
        era, year = gregorian_to_era(datetime.date(1900, 1, 1))
        assert era.name == "明治"
        assert year == 33

    def test_before_meiji_raises(self):
        with pytest.raises(ValueError):
            gregorian_to_era(datetime.date(1867, 1, 1))


class TestEraToGregorian:
    def test_reiwa_by_name(self):
        d = era_to_gregorian("令和", 8, 3, 13)
        assert d == datetime.date(2026, 3, 13)

    def test_reiwa_by_abbreviation(self):
        d = era_to_gregorian("R", 8, 3, 13)
        assert d == datetime.date(2026, 3, 13)

    def test_heisei_gannen(self):
        d = era_to_gregorian("平成", 1, 1, 8)
        assert d == datetime.date(1989, 1, 8)

    def test_showa(self):
        d = era_to_gregorian("昭和", 20, 8, 15)
        assert d == datetime.date(1945, 8, 15)

    def test_unknown_era_raises(self):
        with pytest.raises(ValueError, match="不明な元号"):
            era_to_gregorian("江戸", 1, 1, 1)

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError):
            era_to_gregorian("令和", 1, 13, 1)


class TestFindEra:
    def test_find_by_name(self):
        era = find_era("令和")
        assert era is not None
        assert era.abbreviation == "R"

    def test_find_by_abbreviation(self):
        era = find_era("H")
        assert era is not None
        assert era.name == "平成"

    def test_find_by_reading(self):
        era = find_era("Showa")
        assert era is not None
        assert era.name == "昭和"

    def test_not_found(self):
        assert find_era("江戸") is None


class TestFormatting:
    def test_format_date_era(self):
        result = format_date_era(datetime.date(2026, 3, 13))
        assert result == "令和8年3月13日"

    def test_format_date_era_gannen(self):
        result = format_date_era(datetime.date(2019, 5, 1))
        assert result == "令和元年5月1日"

    def test_format_era_year_gannen(self):
        from memorial_app.core.era_converter import BUILTIN_ERAS
        reiwa = BUILTIN_ERAS[0]
        assert format_era_year(reiwa, 1) == "令和元年"

    def test_format_era_year_normal(self):
        from memorial_app.core.era_converter import BUILTIN_ERAS
        reiwa = BUILTIN_ERAS[0]
        assert format_era_year(reiwa, 8) == "令和8年"
