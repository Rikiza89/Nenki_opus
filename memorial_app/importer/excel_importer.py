"""Excel file reader - handles .xlsx, .xls, .csv with sheet selection and column mapping."""

import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field


# Known column name patterns for auto-detection
_NAME_COLUMNS = {"氏名", "名前", "俗名", "name", "Name", "氏　名"}
_DEATH_DATE_COLUMNS = {"没年月日", "命日", "死亡日", "death_date", "Death_Date", "逝去日", "往生日"}
_BUDDHIST_NAME_COLUMNS = {"法名", "戒名", "buddhist_name", "Buddhist_Name", "法　名"}

# Split date column patterns
_ERA_COLUMNS = {"号", "元号", "era", "号年"}
_YEAR_COLUMNS = {"年", "year", "年号"}
_MONTH_COLUMNS = {"月", "month"}
_DAY_COLUMNS = {"日", "day"}


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

    @property
    def uses_split_date(self) -> bool:
        return self.year_col is not None


@dataclass
class SheetInfo:
    name: str
    row_count: int
    columns: list[str]


def read_file(file_path: Path) -> dict[str, pd.DataFrame]:
    """Read Excel/CSV file and return dict of {sheet_name: DataFrame}.

    For CSV files, the sheet name is 'Sheet1'.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        return {"Sheet1": df}
    elif suffix == ".xls":
        xls = pd.ExcelFile(file_path, engine="xlrd")
        return {name: pd.read_excel(xls, sheet_name=name, dtype=str, keep_default_na=False)
                for name in xls.sheet_names}
    else:  # .xlsx
        xls = pd.ExcelFile(file_path, engine="openpyxl")
        return {name: pd.read_excel(xls, sheet_name=name, dtype=str, keep_default_na=False)
                for name in xls.sheet_names}


def get_sheet_info(sheets: dict[str, pd.DataFrame]) -> list[SheetInfo]:
    """Get info about sheets that have data."""
    result = []
    for name, df in sheets.items():
        if len(df) > 0:
            result.append(SheetInfo(name=name, row_count=len(df), columns=list(df.columns)))
    return result


def auto_detect_mapping(columns: list[str]) -> ColumnMapping:
    """Auto-detect column mapping from column names."""
    mapping = ColumnMapping()
    col_set = set(columns)

    # Detect name column
    for col in columns:
        stripped = col.strip().replace("　", "")
        if stripped in _NAME_COLUMNS or col in _NAME_COLUMNS:
            mapping.name_col = col
            break

    # Detect death date column (single)
    for col in columns:
        stripped = col.strip().replace("　", "")
        if stripped in _DEATH_DATE_COLUMNS or col in _DEATH_DATE_COLUMNS:
            mapping.death_date_col = col
            break

    # Detect split date columns
    if mapping.death_date_col is None:
        for col in columns:
            stripped = col.strip()
            if stripped in _ERA_COLUMNS:
                mapping.era_col = col
            elif stripped in _YEAR_COLUMNS:
                mapping.year_col = col
            elif stripped in _MONTH_COLUMNS:
                mapping.month_col = col
            elif stripped in _DAY_COLUMNS:
                mapping.day_col = col

    # Detect buddhist name
    for col in columns:
        stripped = col.strip().replace("　", "")
        if stripped in _BUDDHIST_NAME_COLUMNS or col in _BUDDHIST_NAME_COLUMNS:
            mapping.buddhist_name_col = col
            break

    # Everything else is extra
    used = {mapping.name_col, mapping.death_date_col, mapping.buddhist_name_col,
            mapping.era_col, mapping.year_col, mapping.month_col, mapping.day_col}
    mapping.extra_cols = [c for c in columns if c not in used]

    return mapping
