"""Multi-stage Excel import validation pipeline."""

import datetime
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from memorial_app.core.japanese_date_parser import parse_date, parse_date_from_columns, DateValidationError
from memorial_app.database.db_manager import DatabaseManager
from memorial_app.importer.excel_importer import ColumnMapping


@dataclass
class ValidatedRow:
    row_index: int
    name: str
    death_date: str         # ISO format
    era_display: str        # Japanese era display
    attributes: dict[str, str]
    source_file_path: str


@dataclass
class ErrorRow:
    row_index: int
    raw_data: dict[str, str]
    error_message: str       # Japanese error message


@dataclass
class ValidationResult:
    valid_rows: list[ValidatedRow] = field(default_factory=list)
    error_rows: list[ErrorRow] = field(default_factory=list)
    duplicate_rows: list[tuple[ValidatedRow, int]] = field(default_factory=list)  # (row, existing_person_id)


class ValidationPipeline:
    def __init__(self, db_manager: DatabaseManager, mapping: ColumnMapping, source_path: str):
        self.db = db_manager
        self.mapping = mapping
        self.source_path = source_path

    def validate(self, df: pd.DataFrame, progress_callback=None) -> ValidationResult:
        """Run full validation pipeline on a DataFrame.

        Args:
            df: The data to validate.
            progress_callback: Optional callable(current, total) for progress updates.

        Returns:
            ValidationResult with valid, error, and duplicate rows.
        """
        result = ValidationResult()
        total = len(df)

        for idx, row in df.iterrows():
            if progress_callback:
                progress_callback(idx, total)

            raw = {col: str(row.get(col, "")) for col in df.columns}

            # Stage 1: Pre-validation - check required fields
            name = self._extract_name(row)
            if not name:
                result.error_rows.append(ErrorRow(idx, raw, "氏名が空です"))
                continue

            # Stage 2: Date parsing
            try:
                parsed = self._parse_death_date(row)
            except DateValidationError as e:
                result.error_rows.append(ErrorRow(idx, raw, str(e)))
                continue

            # Stage 3: Business rules
            death_date = parsed.date
            if death_date > datetime.date.today():
                result.error_rows.append(ErrorRow(idx, raw, f"没年月日が未来の日付です: {parsed.era_display}"))
                continue

            if death_date.year < 1868:
                result.error_rows.append(ErrorRow(idx, raw, f"没年月日が明治以前です: {parsed.era_display}"))
                continue

            # Stage 4: Build attributes
            attributes = self._build_attributes(row)

            validated = ValidatedRow(
                row_index=idx,
                name=name,
                death_date=death_date.isoformat(),
                era_display=parsed.era_display,
                attributes=attributes,
                source_file_path=self.source_path,
            )

            # Stage 5: Duplicate detection
            duplicates = self.db.find_duplicates(name, death_date.isoformat())
            if duplicates:
                result.duplicate_rows.append((validated, duplicates[0].id))
            else:
                result.valid_rows.append(validated)

        return result

    def _extract_name(self, row: pd.Series) -> str | None:
        col = self.mapping.name_col
        if col is None:
            return None
        val = str(row.get(col, "")).strip()
        return val if val else None

    def _parse_death_date(self, row: pd.Series):
        if self.mapping.uses_split_date:
            year_val = row.get(self.mapping.year_col, "")
            month_val = row.get(self.mapping.month_col, "")
            day_val = row.get(self.mapping.day_col, "")
            era_val = row.get(self.mapping.era_col, "") if self.mapping.era_col else None
            return parse_date_from_columns(year_val, month_val, day_val, era_val)
        else:
            col = self.mapping.death_date_col
            if col is None:
                raise DateValidationError("没年月日の列が設定されていません")
            val = str(row.get(col, "")).strip()
            if not val:
                raise DateValidationError("没年月日が空です")
            return parse_date(val)

    def _build_attributes(self, row: pd.Series) -> dict[str, str]:
        """Build dynamic attributes from extra columns + buddhist name."""
        attrs = {}
        if self.mapping.buddhist_name_col:
            val = str(row.get(self.mapping.buddhist_name_col, "")).strip()
            if val:
                attrs[self.mapping.buddhist_name_col] = val

        for col in self.mapping.extra_cols:
            val = str(row.get(col, "")).strip()
            if val:
                attrs[col] = val
        return attrs


def export_error_rows(error_rows: list[ErrorRow], output_path: Path) -> None:
    """Export error rows as an Excel file for correction."""
    if not error_rows:
        return
    data = []
    for er in error_rows:
        row_data = dict(er.raw_data)
        row_data["エラー内容"] = er.error_message
        row_data["元の行番号"] = er.row_index + 2  # +2 for header + 0-index
        data.append(row_data)
    df = pd.DataFrame(data)
    df.to_excel(output_path, index=False, engine="openpyxl")


def import_validated_rows(db: DatabaseManager, rows: list[ValidatedRow]) -> int:
    """Import validated rows into the database. Returns count."""
    records = []
    for row in rows:
        records.append({
            "name": row.name,
            "death_date": row.death_date,
            "source_file_path": row.source_file_path,
            "attributes": row.attributes,
        })
    return db.add_persons_batch(records)
