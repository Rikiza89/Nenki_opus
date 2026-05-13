"""Database manager - CRUD operations, backup, restore, and search.

All mutating operations are wrapped with explicit error handling and rollback.
The engine is configured for cross-thread use because background QThread workers
share the same DatabaseManager instance with the UI thread.
"""

import datetime
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session

from memorial_app.database.models import Base, Person, Attribute
from memorial_app.core.app_paths import DB_PATH, BACKUP_DIR


class DatabaseError(Exception):
    """Raised for any database-level failure surfaced to the UI."""

    pass


@dataclass
class BatchResult:
    """Result of a batch insert / update operation.

    inserted/updated/skipped track row counts; failures contains per-row reasons
    so the UI can show the user exactly which records were rejected and why.
    """

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failures: list[tuple[int, str]] = field(default_factory=list)  # (index, reason)


class DatabaseManager:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self.engine = None
        self._Session = None

    def initialize(self) -> None:
        """Create database and tables if they don't exist.

        Raises:
            DatabaseError: if the DB file/directory cannot be created.
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            # check_same_thread=False is required because QThread workers
            # (ImportWorker, CalculationWorker) call DB methods from non-UI threads
            # and SQLAlchemy may reuse pooled connections across threads.
            self.engine = create_engine(
                f"sqlite:///{self.db_path}",
                echo=False,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
            Base.metadata.create_all(self.engine)
            self._Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        except (OSError, SQLAlchemyError) as e:
            raise DatabaseError(f"データベースの初期化に失敗しました: {e}") from e

    def session(self) -> Session:
        if self._Session is None:
            raise DatabaseError("データベースが初期化されていません")
        return self._Session()

    # --- CRUD: Person ---

    def add_person(
        self,
        name: str,
        death_date: str,
        source_file_path: str | None = None,
        attributes: dict[str, str] | None = None,
    ) -> Person:
        """Add a new person with optional dynamic attributes.

        Raises:
            DatabaseError: on validation or storage failure.
        """
        if not name or not name.strip():
            raise DatabaseError("氏名は必須です")
        if not death_date:
            raise DatabaseError("没年月日は必須です")
        try:
            with self.session() as s:
                person = Person(
                    name=name.strip(),
                    death_date=death_date,
                    source_file_path=source_file_path,
                )
                if attributes:
                    for col_name, value in attributes.items():
                        if not col_name:
                            continue
                        person.attributes.append(
                            Attribute(column_name=col_name, value=value)
                        )
                s.add(person)
                s.commit()
                s.refresh(person)
                _ = person.attributes
                return person
        except SQLAlchemyError as e:
            raise DatabaseError(f"レコードの追加に失敗しました: {e}") from e

    def update_person(
        self,
        person_id: int,
        name: str | None = None,
        death_date: str | None = None,
        source_file_path: str | None = ...,
        attributes: dict[str, str] | None = None,
        merge_attributes: bool = False,
    ) -> Person | None:
        """Update an existing person.

        Args:
            attributes: When provided, the supplied attribute keys are written.
            merge_attributes: When True, existing attributes not in the new dict
                are preserved (only the supplied keys are overwritten). When False
                (default), the legacy replace-all behaviour is used.

        Raises:
            DatabaseError: on storage failure.
        """
        try:
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
                    if merge_attributes:
                        existing = {a.column_name: a for a in person.attributes}
                        for col_name, value in attributes.items():
                            if not col_name:
                                continue
                            if col_name in existing:
                                existing[col_name].value = value
                            else:
                                person.attributes.append(
                                    Attribute(column_name=col_name, value=value)
                                )
                    else:
                        person.attributes.clear()
                        for col_name, value in attributes.items():
                            if not col_name:
                                continue
                            person.attributes.append(
                                Attribute(column_name=col_name, value=value)
                            )
                s.commit()
                s.refresh(person)
                _ = person.attributes
                return person
        except SQLAlchemyError as e:
            raise DatabaseError(f"レコードの更新に失敗しました: {e}") from e

    def delete_person(self, person_id: int) -> bool:
        """Delete a person and all their attributes."""
        try:
            with self.session() as s:
                person = s.get(Person, person_id)
                if person is None:
                    return False
                s.delete(person)
                s.commit()
                return True
        except SQLAlchemyError as e:
            raise DatabaseError(f"レコードの削除に失敗しました: {e}") from e

    def get_person(self, person_id: int) -> Person | None:
        try:
            with self.session() as s:
                person = s.get(Person, person_id)
                if person:
                    _ = person.attributes
                return person
        except SQLAlchemyError as e:
            raise DatabaseError(f"レコードの取得に失敗しました: {e}") from e

    def get_all_persons(self, offset: int = 0, limit: int = 100) -> list[Person]:
        """Get persons with pagination."""
        try:
            with self.session() as s:
                persons = (
                    s.query(Person)
                    .order_by(Person.id)
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                for p in persons:
                    _ = p.attributes
                return persons
        except SQLAlchemyError as e:
            raise DatabaseError(f"レコード一覧の取得に失敗しました: {e}") from e

    def get_person_count(self) -> int:
        try:
            with self.session() as s:
                return s.query(func.count(Person.id)).scalar() or 0
        except SQLAlchemyError as e:
            raise DatabaseError(f"件数の取得に失敗しました: {e}") from e

    def search_persons(
        self, query: str, offset: int = 0, limit: int = 100
    ) -> list[Person]:
        """Search by name (partial match)."""
        try:
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
        except SQLAlchemyError as e:
            raise DatabaseError(f"検索に失敗しました: {e}") from e

    # --- Duplicate Detection ---

    def find_duplicates(self, name: str, death_date: str) -> list[Person]:
        """Find existing persons with matching name and death_date."""
        try:
            with self.session() as s:
                return (
                    s.query(Person)
                    .filter(
                        Person.name == name.strip(),
                        Person.death_date == death_date,
                    )
                    .all()
                )
        except SQLAlchemyError as e:
            raise DatabaseError(f"重複検索に失敗しました: {e}") from e

    # --- Dynamic Attribute Columns ---

    def get_all_column_names(self) -> list[str]:
        """Get all unique dynamic attribute column names in the database."""
        try:
            with self.session() as s:
                rows = s.query(Attribute.column_name).distinct().all()
                return sorted([r[0] for r in rows if r[0]])
        except SQLAlchemyError as e:
            raise DatabaseError(f"列名の取得に失敗しました: {e}") from e

    # --- Backup & Restore ---

    def backup(self) -> tuple[Path, Path]:
        """Create backup: SQLite copy + JSON export.

        On JSON-export failure the partial SQLite copy is removed so we never
        leave a half-completed backup pair on disk.

        Returns: (db_backup_path, json_backup_path)
        """
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        db_backup = BACKUP_DIR / f"memorial_{ts}.db"
        json_backup = BACKUP_DIR / f"memorial_{ts}.json"

        try:
            shutil.copy2(self.db_path, db_backup)
        except OSError as e:
            raise DatabaseError(f"DBファイルのコピーに失敗しました: {e}") from e

        try:
            data = self._export_all_json()
            json_backup.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except (OSError, SQLAlchemyError, TypeError) as e:
            # Clean up partial backup so the user doesn't end up with a half pair
            db_backup.unlink(missing_ok=True)
            raise DatabaseError(f"JSONエクスポートに失敗しました: {e}") from e

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

    def restore_from_json(self, json_path: Path, replace: bool = False) -> BatchResult:
        """Restore database from JSON backup.

        Args:
            json_path: Path to a backup JSON file.
            replace: If True, wipe the existing DB first (a fresh backup is taken
                before wiping). If False, merge (append) the records.

        Returns:
            BatchResult with per-record success/failure information.
        """
        try:
            raw = json_path.read_text(encoding="utf-8")
        except OSError as e:
            raise DatabaseError(f"JSONファイルを読み込めません: {e}") from e
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise DatabaseError(f"JSONの解析に失敗しました: {e}") from e
        if not isinstance(data, list):
            raise DatabaseError("JSONの形式が不正です（リスト形式である必要があります）")

        if replace:
            self.backup()
            try:
                Base.metadata.drop_all(self.engine)
                Base.metadata.create_all(self.engine)
            except SQLAlchemyError as e:
                raise DatabaseError(f"既存データのクリアに失敗しました: {e}") from e

        result = BatchResult()
        try:
            with self.session() as s:
                for idx, rec in enumerate(data):
                    if not isinstance(rec, dict):
                        result.failures.append((idx, "レコードが辞書形式ではありません"))
                        continue
                    name = rec.get("name")
                    death_date = rec.get("death_date")
                    if not name or not death_date:
                        result.failures.append(
                            (idx, "name または death_date が欠落しています")
                        )
                        continue
                    try:
                        person = Person(
                            name=str(name).strip(),
                            death_date=str(death_date),
                            source_file_path=rec.get("source_file_path"),
                        )
                        attrs = rec.get("attributes") or {}
                        if isinstance(attrs, dict):
                            for col_name, value in attrs.items():
                                if not col_name:
                                    continue
                                person.attributes.append(
                                    Attribute(column_name=col_name, value=value)
                                )
                        s.add(person)
                        result.inserted += 1
                    except (TypeError, ValueError) as e:
                        result.failures.append((idx, str(e)))
                s.commit()
        except SQLAlchemyError as e:
            raise DatabaseError(f"復元に失敗しました: {e}") from e
        return result

    # --- Database Reset ---

    def reset_database(self) -> Path:
        """Drop all tables and recreate. Creates backup first.

        Returns:
            Path to the backup .db file so the UI can show the user where the
            safety copy was placed.
        """
        db_backup, _ = self.backup()
        try:
            Base.metadata.drop_all(self.engine)
            Base.metadata.create_all(self.engine)
        except SQLAlchemyError as e:
            raise DatabaseError(f"データベースのリセットに失敗しました: {e}") from e
        return db_backup

    # --- Batch Import Support ---

    def add_persons_batch(self, records: list[dict]) -> BatchResult:
        """Bulk insert persons.

        Each record: {name, death_date, source_file_path?, attributes?}.

        Returns a BatchResult; per-record failures do not abort the rest of the
        batch. The entire batch shares a single transaction that is committed
        only if at least one record was inserted; if every record failed the
        transaction is rolled back cleanly.
        """
        result = BatchResult()
        try:
            with self.session() as s:
                for idx, rec in enumerate(records):
                    try:
                        name = rec.get("name")
                        death_date = rec.get("death_date")
                        if not name or not death_date:
                            result.failures.append(
                                (idx, "氏名または没年月日が欠落しています")
                            )
                            continue
                        person = Person(
                            name=str(name).strip(),
                            death_date=str(death_date),
                            source_file_path=rec.get("source_file_path"),
                        )
                        attrs = rec.get("attributes") or {}
                        for col_name, value in attrs.items():
                            if not col_name:
                                continue
                            person.attributes.append(
                                Attribute(column_name=col_name, value=value)
                            )
                        s.add(person)
                        result.inserted += 1
                    except (TypeError, ValueError, KeyError) as e:
                        result.failures.append((idx, str(e)))
                if result.inserted > 0:
                    s.commit()
                else:
                    s.rollback()
        except SQLAlchemyError as e:
            raise DatabaseError(f"バッチインポートに失敗しました: {e}") from e
        return result
