"""Multi-stage Excel import validation pipeline.

The pipeline:
  1. Pulls required fields (name, death date) from each row using the column mapping.
  2. Parses the death date (any of the supported Japanese / Gregorian forms).
  3. Applies business rules (no future dates, no pre-Meiji dates).
  4. Builds dynamic attributes, applying the user's column-remap selections.
  5. Detects duplicates against the DB *and* against rows seen earlier in the
     same file (so a doubled row inside one Excel sheet is reported, not
     silently inserted twice).

Errors are recorded with the raw row data so the UI can offer the user
inline correction.
"""

import datetime
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from memorial_app.core.japanese_date_parser import (
    parse_date,
    parse_date_from_columns,
    DateValidationError,
)
from memorial_app.database.db_manager import DatabaseManager
from memorial_app.importer.excel_importer import ColumnMapping


# Cells that begin with one of these characters could be interpreted as a
# formula by Excel and trigger unintended computation when the user opens the
# error-export file. We prefix them with an apostrophe to neutralize that.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_for_excel(value: str) -> str:
    if not value:
        return value
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


@dataclass
class ValidatedRow:
    row_index: int
    name: str
    death_date: str  # ISO format
    era_display: str  # Japanese era display
    attributes: dict[str, str]
    source_file_path: str
    # Set by the UI when the user resolves a duplicate at confirm time.
    # Values: None (default — insert as new), "overwrite" (update existing
    # row with id=duplicate_of), or "skip" (do nothing).
    duplicate_of: int | None = None
    duplicate_action: str | None = None


@dataclass
class ErrorRow:
    row_index: int
    raw_data: dict[str, str]
    error_message: str  # Japanese error message
    error_column: str | None = None  # Which column caused the error (for Excel highlighting)


@dataclass
class ValidationResult:
    valid_rows: list[ValidatedRow] = field(default_factory=list)
    error_rows: list[ErrorRow] = field(default_factory=list)
    duplicate_rows: list[ValidatedRow] = field(default_factory=list)


class ValidationPipeline:
    def __init__(
        self, db_manager: DatabaseManager, mapping: ColumnMapping, source_path: str
    ):
        self.db = db_manager
        self.mapping = mapping
        self.source_path = source_path

    def validate(self, df: pd.DataFrame, progress_callback=None) -> ValidationResult:
        """Run full validation pipeline on a DataFrame."""
        result = ValidationResult()
        total = len(df)

        # In-file dedup tracker — (name, death_date_iso) → first row index seen
        seen_in_file: dict[tuple[str, str], int] = {}

        for idx, row in df.iterrows():
            if progress_callback:
                try:
                    progress_callback(int(idx), total)
                except Exception:
                    # Never let a UI signal slot exception abort validation
                    pass

            row_index = int(idx) if isinstance(idx, (int, float)) else 0
            raw = {col: str(row.get(col, "")) for col in df.columns}

            # Stage 1: Pre-validation - check required fields
            name = self._extract_name(row)
            if not name:
                result.error_rows.append(
                    ErrorRow(row_index, raw, "氏名が空です", error_column=self.mapping.name_col)
                )
                continue

            # Stage 2: Date parsing
            _date_col = (
                self.mapping.death_date_col
                if not self.mapping.uses_split_date
                else self.mapping.year_col
            )
            try:
                parsed = self._parse_death_date(row)
            except DateValidationError as e:
                result.error_rows.append(
                    ErrorRow(row_index, raw, str(e), error_column=_date_col)
                )
                continue
            except Exception as e:
                result.error_rows.append(
                    ErrorRow(
                        row_index, raw,
                        f"日付の解析中に予期しないエラー: {e}",
                        error_column=_date_col,
                    )
                )
                continue

            # Stage 3: Business rules
            death_date = parsed.date
            if death_date > datetime.date.today():
                result.error_rows.append(
                    ErrorRow(
                        row_index,
                        raw,
                        f"没年月日が未来の日付です: {parsed.era_display}",
                        error_column=_date_col,
                    )
                )
                continue
            if death_date.year < 1868:
                result.error_rows.append(
                    ErrorRow(
                        row_index,
                        raw,
                        f"没年月日が明治以前です: {parsed.era_display}",
                        error_column=_date_col,
                    )
                )
                continue

            # Stage 4: Build attributes (uses column_remap selections)
            try:
                attributes = self._build_attributes(row)
            except Exception as e:
                result.error_rows.append(
                    ErrorRow(row_index, raw, f"属性の構築中にエラー: {e}")
                )
                continue

            iso = death_date.isoformat()

            # Stage 5a: In-file duplicate detection
            key = (name, iso)
            if key in seen_in_file:
                result.error_rows.append(
                    ErrorRow(
                        row_index,
                        raw,
                        f"ファイル内で重複しています（同一データの最初の出現: {seen_in_file[key] + 2}行目）",
                        error_column=self.mapping.name_col,
                    )
                )
                continue
            seen_in_file[key] = row_index

            validated = ValidatedRow(
                row_index=row_index,
                name=name,
                death_date=iso,
                era_display=parsed.era_display,
                attributes=attributes,
                source_file_path=self.source_path,
            )

            # Stage 5b: DB duplicate detection
            try:
                duplicates = self.db.find_duplicates(name, iso)
            except Exception as e:
                result.error_rows.append(
                    ErrorRow(row_index, raw, f"DB重複チェックエラー: {e}")
                )
                continue
            if duplicates:
                validated.duplicate_of = duplicates[0].id
                result.duplicate_rows.append(validated)
            else:
                result.valid_rows.append(validated)

        if progress_callback:
            try:
                progress_callback(total, total)
            except Exception:
                pass

        return result

    def validate_one(self, raw: dict[str, str], row_index: int) -> ValidatedRow | ErrorRow:
        """Re-validate a single row supplied as a plain dict (used after the
        user edits an erroneous row in the in-UI editor)."""
        row = pd.Series({k: (v if v is not None else "") for k, v in raw.items()})

        name = self._extract_name(row)
        if not name:
            return ErrorRow(row_index, raw, "氏名が空です")

        try:
            parsed = self._parse_death_date(row)
        except DateValidationError as e:
            return ErrorRow(row_index, raw, str(e))
        except Exception as e:
            return ErrorRow(row_index, raw, f"日付の解析中に予期しないエラー: {e}")

        if parsed.date > datetime.date.today():
            return ErrorRow(
                row_index, raw, f"没年月日が未来の日付です: {parsed.era_display}"
            )
        if parsed.date.year < 1868:
            return ErrorRow(
                row_index, raw, f"没年月日が明治以前です: {parsed.era_display}"
            )

        try:
            attributes = self._build_attributes(row)
        except Exception as e:
            return ErrorRow(row_index, raw, f"属性の構築中にエラー: {e}")

        iso = parsed.date.isoformat()
        validated = ValidatedRow(
            row_index=row_index,
            name=name,
            death_date=iso,
            era_display=parsed.era_display,
            attributes=attributes,
            source_file_path=self.source_path,
        )
        try:
            duplicates = self.db.find_duplicates(name, iso)
        except Exception as e:
            return ErrorRow(row_index, raw, f"DB重複チェックエラー: {e}")
        if duplicates:
            validated.duplicate_of = duplicates[0].id
        return validated

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
            era_val = (
                row.get(self.mapping.era_col, "") if self.mapping.era_col else None
            )
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
        """Build dynamic attributes from extra columns + buddhist name.

        Applies column_remap to rename Excel columns to existing DB column names.
        If multiple source columns end up writing to the same DB column we keep
        the first non-empty value rather than letting the later one silently
        clobber the earlier — the import-window step 3 conflict check should
        prevent this anyway.
        """
        remap = self.mapping.column_remap
        attrs: dict[str, str] = {}

        def _set(col: str, value: str):
            target = remap.get(col, col)
            if not target:
                return
            if target in attrs and attrs[target]:
                return  # keep first non-empty value
            attrs[target] = value

        if self.mapping.buddhist_name_col:
            val = str(row.get(self.mapping.buddhist_name_col, "")).strip()
            if val:
                _set(self.mapping.buddhist_name_col, val)

        for col in self.mapping.extra_cols:
            val = str(row.get(col, "")).strip()
            if val:
                _set(col, val)
        return attrs


def export_error_rows(error_rows: list[ErrorRow], output_path: Path) -> None:
    """Export error rows as an Excel file for offline correction.

    Cells that start with characters Excel interprets as a formula are prefixed
    with an apostrophe to prevent formula-injection problems when the user
    re-opens the file.
    """
    if not error_rows:
        return
    data = []
    for er in error_rows:
        row_data = {k: _sanitize_for_excel(str(v)) for k, v in er.raw_data.items()}
        row_data["エラー内容"] = _sanitize_for_excel(er.error_message)
        row_data["元の行番号"] = er.row_index + 2  # +2 for header + 0-index
        data.append(row_data)
    df = pd.DataFrame(data)
    df.to_excel(output_path, index=False, engine="openpyxl")


def export_annotated_copy(
    original_df: "pd.DataFrame",
    error_rows: "list[ErrorRow]",
    source_path: "Path",
) -> "Path":
    """Create *{stem}_エラー確認.xlsx* next to the original file.

    All original rows are preserved.  Error rows are highlighted:
    - The specific problem column gets an orange background.
    - The whole error row gets a light-yellow tint.
    - An appended 「エラー内容」column shows the Japanese error message in red.
    Returns the path of the created file.
    """
    import openpyxl
    from openpyxl.styles import PatternFill, Font

    output_path = source_path.parent / f"{source_path.stem}_エラー確認.xlsx"

    err_map: dict[int, tuple[str | None, str]] = {
        er.row_index: (er.error_column, er.error_message) for er in error_rows
    }

    df_copy = original_df.copy()
    df_copy["エラー内容"] = [
        err_map[i][1] if i in err_map else "" for i in range(len(df_copy))
    ]
    df_copy.to_excel(output_path, index=False, engine="openpyxl")

    wb = openpyxl.load_workbook(output_path)
    ws = wb.active

    orange_fill = PatternFill(start_color="FFB347", end_color="FFB347", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")
    red_font = Font(color="C0392B", bold=True)

    col_idx: dict[str, int] = {
        ws.cell(1, j).value: j
        for j in range(1, ws.max_column + 1)
        if ws.cell(1, j).value
    }
    err_col_idx = col_idx.get("エラー内容")

    for er in error_rows:
        xlsx_row = er.row_index + 2  # 1-based + header row
        if xlsx_row > ws.max_row:
            continue
        # Tint entire data row light-yellow
        for j in range(1, ws.max_column + 1):
            ws.cell(xlsx_row, j).fill = yellow_fill
        # Stronger orange on the specific problem column
        if er.error_column and er.error_column in col_idx:
            ws.cell(xlsx_row, col_idx[er.error_column]).fill = orange_fill
        # Red bold text in the error-message column
        if err_col_idx:
            ws.cell(xlsx_row, err_col_idx).font = red_font

    # Approximate column widths
    for col in ws.columns:
        letter = col[0].column_letter
        max_len = max(
            (len(str(cell.value)) for cell in col if cell.value is not None),
            default=8,
        )
        ws.column_dimensions[letter].width = min(max_len + 4, 45)

    wb.save(output_path)
    return output_path


def import_validated_rows(db: DatabaseManager, rows: list[ValidatedRow]):
    """Import validated rows into the database.

    Honours each row's duplicate_action:
      - None / "insert" → insert as a new record
      - "overwrite"     → update the existing row pointed to by duplicate_of
      - "skip"          → do nothing for this row

    Returns a BatchResult-like dict with inserted/updated/skipped counts and
    per-row failures.
    """
    inserted_records = []
    updated = 0
    skipped = 0
    failures: list[tuple[int, str]] = []

    for row in rows:
        action = row.duplicate_action
        if action == "skip":
            skipped += 1
            continue
        if action == "overwrite" and row.duplicate_of is not None:
            try:
                db.update_person(
                    row.duplicate_of,
                    name=row.name,
                    death_date=row.death_date,
                    attributes=row.attributes,
                    merge_attributes=True,
                )
                updated += 1
            except Exception as e:
                failures.append((row.row_index, str(e)))
            continue
        inserted_records.append(
            {
                "name": row.name,
                "death_date": row.death_date,
                "source_file_path": row.source_file_path,
                "attributes": row.attributes,
            }
        )

    insert_result = db.add_persons_batch(inserted_records) if inserted_records else None
    inserted = insert_result.inserted if insert_result else 0
    if insert_result:
        failures.extend(insert_result.failures)
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "failures": failures,
    }
