"""Excel file reader - handles .xlsx, .xls, .csv with sheet selection and column mapping."""

import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field

# Known column name patterns for auto-detection
_NAME_COLUMNS = {"氏名", "名前", "俗名", "name", "Name", "氏　名", "お名前"}
_DEATH_DATE_COLUMNS = {
    "没年月日",
    "命日",
    "死亡日",
    "death_date",
    "Death_Date",
    "逝去日",
    "往生日",
    "ご命日",
}
_BUDDHIST_NAME_COLUMNS = {"法名", "戒名", "buddhist_name", "Buddhist_Name", "法　名"}

# Split date column patterns — kept narrow to avoid false positives
# (e.g. arbitrary columns literally named "号" must NOT be hijacked as era).
_ERA_COLUMNS = {"元号", "era", "号年"}
_YEAR_COLUMNS = {"年", "year", "年号"}
_MONTH_COLUMNS = {"月", "month"}
_DAY_COLUMNS = {"日", "day"}


class FileReadError(Exception):
    """Raised when an input data file cannot be read."""

    pass


@dataclass
class ColumnMapping:
    name_col: str | None = None
    death_date_col: str | None = None
    buddhist_name_col: str | None = None
    # Split date columns (alternative to single death_date_col)
    era_col: str | None = None
    year_col: str | None = None
    month_col: str | None = None
    day_col: str | None = None
    # All other columns become dynamic attributes
    extra_cols: list[str] = field(default_factory=list)
    # Remap extra column names: {excel_col_name: db_col_name}
    column_remap: dict[str, str] = field(default_factory=dict)

    @property
    def uses_split_date(self) -> bool:
        return self.year_col is not None


@dataclass
class SheetInfo:
    name: str
    row_count: int
    columns: list[str]


# CSV encoding fallback order. Japanese systems commonly produce CP932/Shift_JIS
# files; UTF-8 with BOM is also common when exporting from modern Excel.
_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "shift_jis", "euc-jp")


def _read_csv(file_path: Path) -> pd.DataFrame:
    """Read a CSV trying several common Japanese encodings before falling back
    to a permissive replace-on-error read."""
    last_err: Exception | None = None
    for enc in _CSV_ENCODINGS:
        try:
            return pd.read_csv(
                file_path, dtype=str, keep_default_na=False, encoding=enc
            )
        except UnicodeDecodeError as e:
            last_err = e
        except (pd.errors.ParserError, OSError) as e:
            raise FileReadError(f"CSVを読み込めません: {e}") from e
    # Last-resort: replace undecodable bytes so the user can at least see the file
    try:
        return pd.read_csv(
            file_path,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8",
            encoding_errors="replace",
        )
    except Exception as e:
        raise FileReadError(
            f"CSVの文字コードを判別できません（最後のエラー: {last_err}）: {e}"
        ) from e


def read_file(file_path: Path) -> dict[str, pd.DataFrame]:
    """Read Excel/CSV file and return dict of {sheet_name: DataFrame}.

    For CSV files, the sheet name is 'Sheet1'.

    Raises:
        FileReadError: if the file cannot be read.
    """
    if not file_path.exists():
        raise FileReadError(f"ファイルが見つかりません: {file_path}")
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".csv":
            return {"Sheet1": _read_csv(file_path)}
        elif suffix == ".xls":
            xls = pd.ExcelFile(file_path, engine="xlrd")
            return {
                name: pd.read_excel(
                    xls, sheet_name=name, dtype=str, keep_default_na=False
                )
                for name in xls.sheet_names
            }
        elif suffix in (".xlsx", ".xlsm"):
            xls = pd.ExcelFile(file_path, engine="openpyxl")
            return {
                name: pd.read_excel(
                    xls, sheet_name=name, dtype=str, keep_default_na=False
                )
                for name in xls.sheet_names
            }
        else:
            raise FileReadError(f"対応していないファイル形式です: {suffix}")
    except FileReadError:
        raise
    except Exception as e:
        raise FileReadError(f"ファイルの読み込みに失敗しました: {e}") from e


def get_sheet_info(sheets: dict[str, pd.DataFrame]) -> list[SheetInfo]:
    """Get info about sheets that have data."""
    result = []
    for name, df in sheets.items():
        if len(df) > 0:
            result.append(
                SheetInfo(name=name, row_count=len(df), columns=list(df.columns))
            )
    return result


def auto_detect_mapping(columns: list[str]) -> ColumnMapping:
    """Auto-detect column mapping from column names.

    Detection is exact-match on normalized column text (strip + collapse
    full-width spaces) so that arbitrary columns containing a kanji like 号
    are not mistakenly treated as era columns.
    """
    mapping = ColumnMapping()

    def _norm(c: str) -> str:
        return c.strip().replace("　", "")

    # Detect name column
    for col in columns:
        if _norm(col) in _NAME_COLUMNS or col in _NAME_COLUMNS:
            mapping.name_col = col
            break

    # Detect death date column (single)
    for col in columns:
        if _norm(col) in _DEATH_DATE_COLUMNS or col in _DEATH_DATE_COLUMNS:
            mapping.death_date_col = col
            break

    # Detect split date columns only when no single date column was found
    if mapping.death_date_col is None:
        for col in columns:
            n = _norm(col)
            if n in _ERA_COLUMNS:
                mapping.era_col = col
            elif n in _YEAR_COLUMNS:
                mapping.year_col = col
            elif n in _MONTH_COLUMNS:
                mapping.month_col = col
            elif n in _DAY_COLUMNS:
                mapping.day_col = col

    # Detect buddhist name
    for col in columns:
        if _norm(col) in _BUDDHIST_NAME_COLUMNS or col in _BUDDHIST_NAME_COLUMNS:
            mapping.buddhist_name_col = col
            break

    # Everything else is extra
    used = {
        mapping.name_col,
        mapping.death_date_col,
        mapping.buddhist_name_col,
        mapping.era_col,
        mapping.year_col,
        mapping.month_col,
        mapping.day_col,
    }
    used.discard(None)
    mapping.extra_cols = [c for c in columns if c not in used]

    return mapping
