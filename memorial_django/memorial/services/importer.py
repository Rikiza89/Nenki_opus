import io
import pandas as pd
from .japanese_date_parser import parse_date, parse_split_columns

# Known column patterns
_NAME_COLS = {'氏名', '名前', '俗名', '施主名', 'name', '名'}
_DEATH_COLS = {'没年月日', '命日', '死亡日', '祥月命日', 'death_date', '命日年月日'}
_ERA_COLS = {'元号', '年号', 'era'}
_YEAR_COLS = {'年', '没年', '死亡年', 'year'}
_MONTH_COLS = {'月', '没月', '死亡月', 'month'}
_DAY_COLS = {'日', '没日', '死亡日付', 'day'}
_BUDDHIST_COLS = {'法名', '戒名', 'buddhist_name'}


def _normalize(s: str) -> str:
    return str(s).strip().replace('\u3000', '').replace(' ', '').lower()


def read_file(file_obj, filename: str) -> dict:
    """Returns {sheet_name: DataFrame}"""
    name = filename.lower()
    if name.endswith('.csv'):
        df = pd.read_csv(file_obj, dtype=str, keep_default_na=False)
        return {'Sheet1': df}
    elif name.endswith('.xlsx'):
        xf = pd.ExcelFile(file_obj, engine='openpyxl')
    elif name.endswith('.xls'):
        xf = pd.ExcelFile(file_obj, engine='xlrd')
    else:
        raise ValueError(f"Unsupported file type: {filename}")

    sheets = {}
    for sheet in xf.sheet_names:
        df = xf.parse(sheet, dtype=str, keep_default_na=False)
        sheets[sheet] = df
    return sheets


def detect_mapping(columns: list) -> dict:
    mapping = {
        'name_col': None,
        'death_date_col': None,
        'era_col': None,
        'year_col': None,
        'month_col': None,
        'day_col': None,
        'extra_cols': [],
    }
    used = set()

    for col in columns:
        n = _normalize(col)
        if not mapping['name_col'] and n in {_normalize(c) for c in _NAME_COLS}:
            mapping['name_col'] = col
            used.add(col)
        elif not mapping['death_date_col'] and n in {_normalize(c) for c in _DEATH_COLS}:
            mapping['death_date_col'] = col
            used.add(col)
        elif not mapping['era_col'] and n in {_normalize(c) for c in _ERA_COLS}:
            mapping['era_col'] = col
            used.add(col)
        elif not mapping['year_col'] and n in {_normalize(c) for c in _YEAR_COLS}:
            mapping['year_col'] = col
            used.add(col)
        elif not mapping['month_col'] and n in {_normalize(c) for c in _MONTH_COLS}:
            mapping['month_col'] = col
            used.add(col)
        elif not mapping['day_col'] and n in {_normalize(c) for c in _DAY_COLS}:
            mapping['day_col'] = col
            used.add(col)

    mapping['extra_cols'] = [c for c in columns if c not in used]
    return mapping


def import_dataframe(df: pd.DataFrame, mapping: dict) -> list:
    """Returns list of dicts with 'name', 'death_date', 'attributes', 'errors'."""
    results = []
    for _, row in df.iterrows():
        entry = {'name': '', 'death_date': '', 'attributes': {}, 'errors': []}

        # Name
        if mapping.get('name_col'):
            entry['name'] = str(row.get(mapping['name_col'], '')).strip()

        # Death date
        parsed = None
        if mapping.get('death_date_col'):
            raw = str(row.get(mapping['death_date_col'], '')).strip()
            parsed = parse_date(raw)
        elif mapping.get('year_col') or mapping.get('month_col'):
            parsed = parse_split_columns(
                row.get(mapping.get('year_col', ''), ''),
                row.get(mapping.get('month_col', ''), ''),
                row.get(mapping.get('day_col', ''), ''),
                row.get(mapping.get('era_col', ''), '') if mapping.get('era_col') else None,
            )

        if parsed:
            entry['death_date'] = parsed.date.isoformat()
        else:
            entry['errors'].append('命日が解析できませんでした')

        # Extra attributes
        for col in mapping.get('extra_cols', []):
            val = str(row.get(col, '')).strip()
            if val:
                entry['attributes'][col] = val

        if entry['name'] or entry['death_date']:
            results.append(entry)

    return results
