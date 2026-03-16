"""Database manager - CRUD operations, backup, restore, and search."""

import datetime
import json
import shutil
from pathlib import Path

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session

from memorial_app.database.models import Base, Person, Attribute
from memorial_app.core.app_paths import DB_PATH, BACKUP_DIR


class DatabaseManager:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self.engine = None
        self._Session = None

    def initialize(self) -> None:
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self._Session = sessionmaker(bind=self.engine)

    def session(self) -> Session:
        return self._Session()

    # --- CRUD: Person ---

    def add_person(
        self,
        name: str,
        death_date: str,
        source_file_path: str | None = None,
        attributes: dict[str, str] | None = None,
    ) -> Person:
        """Add a new person with optional dynamic attributes."""
        with self.session() as s:
            person = Person(
                name=name.strip(),
                death_date=death_date,
                source_file_path=source_file_path,
            )
            if attributes:
                for col_name, value in attributes.items():
                    person.attributes.append(
                        Attribute(column_name=col_name, value=value)
                    )
            s.add(person)
            s.commit()
            s.refresh(person)
            return person

    def update_person(
        self,
        person_id: int,
        name: str | None = None,
        death_date: str | None = None,
        source_file_path: str | None = ...,
        attributes: dict[str, str] | None = None,
    ) -> Person | None:
        """Update an existing person. Pass attributes dict to replace all dynamic attributes."""
        with self.session() as s:
            person = s.get(Person, person_id)
            if person is None:
                return None
            if name is not None:
                person.name = name.strip()
            if death_date is not None:
                person.death_date = death_date
            if source_file_path is not ...:
                person.source_file_path = source_file_path
            person.updated_at = datetime.datetime.now()
            if attributes is not None:
                # Replace all attributes
                person.attributes.clear()
                for col_name, value in attributes.items():
                    person.attributes.append(
                        Attribute(column_name=col_name, value=value)
                    )
            s.commit()
            s.refresh(person)
            return person

    def delete_person(self, person_id: int) -> bool:
        """Delete a person and all their attributes."""
        with self.session() as s:
            person = s.get(Person, person_id)
            if person is None:
                return False
            s.delete(person)
            s.commit()
            return True

    def get_person(self, person_id: int) -> Person | None:
        with self.session() as s:
            person = s.get(Person, person_id)
            if person:
                _ = person.attributes  # Eager load
            return person

    def get_all_persons(self, offset: int = 0, limit: int = 100) -> list[Person]:
        """Get persons with pagination."""
        with self.session() as s:
            persons = (
                s.query(Person).order_by(Person.id).offset(offset).limit(limit).all()
            )
            for p in persons:
                _ = p.attributes
            return persons

    def get_person_count(self) -> int:
        with self.session() as s:
            return s.query(func.count(Person.id)).scalar()

    def search_persons(
        self, query: str, offset: int = 0, limit: int = 100
    ) -> list[Person]:
        """Search by name (partial match)."""
        with self.session() as s:
            persons = (
                s.query(Person)
                .filter(Person.name.contains(query.strip()))
                .order_by(Person.id)
                .offset(offset)
                .limit(limit)
                .all()
            )
            for p in persons:
                _ = p.attributes
            return persons

    # --- Duplicate Detection ---

    def find_duplicates(self, name: str, death_date: str) -> list[Person]:
        """Find existing persons with matching name and death_date."""
        with self.session() as s:
            return (
                s.query(Person)
                .filter(
                    Person.name == name.strip(),
                    Person.death_date == death_date,
                )
                .all()
            )

    # --- Dynamic Attribute Columns ---

    def get_all_column_names(self) -> list[str]:
        """Get all unique dynamic attribute column names in the database."""
        with self.session() as s:
            rows = s.query(Attribute.column_name).distinct().all()
            return sorted([r[0] for r in rows])

    # --- Backup & Restore ---

    def backup(self) -> tuple[Path, Path]:
        """Create backup: SQLite copy + JSON export. Returns (db_backup_path, json_backup_path)."""
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # SQLite file copy
        db_backup = BACKUP_DIR / f"memorial_{ts}.db"
        shutil.copy2(self.db_path, db_backup)

        # JSON export
        json_backup = BACKUP_DIR / f"memorial_{ts}.json"
        data = self._export_all_json()
        json_backup.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return db_backup, json_backup

    def _export_all_json(self) -> list[dict]:
        """Export all records as JSON-serializable list."""
        with self.session() as s:
            persons = s.query(Person).all()
            result = []
            for p in persons:
                rec = {
                    "id": p.id,
                    "name": p.name,
                    "death_date": p.death_date,
                    "source_file_path": p.source_file_path,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    "attributes": {a.column_name: a.value for a in p.attributes},
                }
                result.append(rec)
            return result

    def restore_from_json(self, json_path: Path) -> int:
        """Restore database from JSON backup. Returns number of records restored."""
        data = json.loads(json_path.read_text(encoding="utf-8"))
        count = 0
        with self.session() as s:
            for rec in data:
                person = Person(
                    name=rec["name"],
                    death_date=rec["death_date"],
                    source_file_path=rec.get("source_file_path"),
                )
                attrs = rec.get("attributes", {})
                for col_name, value in attrs.items():
                    person.attributes.append(
                        Attribute(column_name=col_name, value=value)
                    )
                s.add(person)
                count += 1
            s.commit()
        return count

    # --- Database Reset ---

    def reset_database(self) -> None:
        """Drop all tables and recreate. Creates backup first."""
        self.backup()
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    # --- Batch Import Support ---

    def add_persons_batch(self, records: list[dict]) -> int:
        """Bulk insert persons. Each record: {name, death_date, source_file_path?, attributes?}.
        Returns count of inserted records.
        """
        with self.session() as s:
            count = 0
            for rec in records:
                person = Person(
                    name=rec["name"].strip(),
                    death_date=rec["death_date"],
                    source_file_path=rec.get("source_file_path"),
                )
                for col_name, value in rec.get("attributes", {}).items():
                    person.attributes.append(
                        Attribute(column_name=col_name, value=value)
                    )
                s.add(person)
                count += 1
            s.commit()
            return count
