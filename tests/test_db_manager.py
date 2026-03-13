"""Tests for the database manager."""

import datetime
import tempfile
from pathlib import Path

import pytest

from memorial_app.database.db_manager import DatabaseManager


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        manager = DatabaseManager(db_path=db_path)
        manager.initialize()
        yield manager


class TestPersonCRUD:
    def test_add_person(self, db):
        person = db.add_person("佐藤太郎", "2020-01-15")
        assert person.id is not None
        assert person.name == "佐藤太郎"
        assert person.death_date == "2020-01-15"

    def test_add_person_with_attributes(self, db):
        person = db.add_person(
            "田中花子", "2019-06-01",
            attributes={"法名": "釈浄光", "住所": "東京都港区"}
        )
        assert person.id is not None
        # Re-fetch to access attributes (session was closed)
        retrieved = db.get_person(person.id)
        assert len(retrieved.attributes) == 2

    def test_get_person(self, db):
        added = db.add_person("鈴木一郎", "2018-03-20")
        retrieved = db.get_person(added.id)
        assert retrieved is not None
        assert retrieved.name == "鈴木一郎"

    def test_update_person(self, db):
        person = db.add_person("山本清", "2020-01-01")
        updated = db.update_person(person.id, name="山本清一")
        assert updated.name == "山本清一"

    def test_delete_person(self, db):
        person = db.add_person("高橋進", "2021-05-05")
        assert db.delete_person(person.id) is True
        assert db.get_person(person.id) is None

    def test_delete_nonexistent(self, db):
        assert db.delete_person(9999) is False


class TestSearch:
    def test_search_by_name(self, db):
        db.add_person("佐藤太郎", "2020-01-01")
        db.add_person("佐藤花子", "2019-06-01")
        db.add_person("田中一郎", "2018-03-01")

        results = db.search_persons("佐藤")
        assert len(results) == 2

    def test_search_no_match(self, db):
        db.add_person("佐藤太郎", "2020-01-01")
        results = db.search_persons("田中")
        assert len(results) == 0


class TestDuplicateDetection:
    def test_find_duplicates(self, db):
        db.add_person("佐藤太郎", "2020-01-15")
        dupes = db.find_duplicates("佐藤太郎", "2020-01-15")
        assert len(dupes) == 1

    def test_no_duplicates(self, db):
        db.add_person("佐藤太郎", "2020-01-15")
        dupes = db.find_duplicates("佐藤太郎", "2020-01-16")
        assert len(dupes) == 0


class TestBatchImport:
    def test_batch_add(self, db):
        records = [
            {"name": "佐藤太郎", "death_date": "2020-01-01"},
            {"name": "田中花子", "death_date": "2019-06-01", "attributes": {"法名": "釈浄光"}},
        ]
        count = db.add_persons_batch(records)
        assert count == 2
        assert db.get_person_count() == 2


class TestColumnNames:
    def test_get_all_column_names(self, db):
        db.add_person("佐藤太郎", "2020-01-01", attributes={"法名": "a", "住所": "b"})
        db.add_person("田中花子", "2019-01-01", attributes={"法名": "c", "電話": "d"})
        cols = db.get_all_column_names()
        assert "法名" in cols
        assert "住所" in cols
        assert "電話" in cols
