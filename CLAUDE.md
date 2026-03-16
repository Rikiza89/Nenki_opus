# Nenki_opus — Buddhist Memorial Anniversary App

## What This Is
Desktop app (PySide6) for Japanese temple staff to manage nenki (年忌) memorial anniversaries.
Calculates anniversaries from death dates, imports Excel/CSV data, generates vertical-text (縦書き) Word/PDF documents.

## Tech Stack
- **Python 3.11+**, PySide6, SQLAlchemy 2.0+ (SQLite), python-docx, reportlab, pandas, openpyxl
- Run: `python -m memorial_app.app.main` or `nenki`

## Project Structure
```
memorial_app/
├── app/main.py              # Entry point, DB init
├── core/                    # Business logic
│   ├── nenki_calculator.py  # Anniversary calculation (year offsets)
│   ├── era_converter.py     # Gregorian ↔ Japanese era (元号)
│   ├── date_converter.py    # Kanji number/era formatting
│   └── japanese_date_parser.py  # Robust date parsing (era, kanji, serial)
├── database/
│   ├── models.py            # Person + Attribute (EAV pattern)
│   └── db_manager.py        # CRUD, search, backup
├── importer/
│   ├── excel_importer.py    # Sheet/column detection & mapping
│   └── validation_pipeline.py  # Multi-stage validation & dedup
├── documents/
│   ├── word_generator.py    # Vertical text .docx (tategaki, MS Mincho)
│   └── pdf_generator.py     # Word→PDF (docx2pdf) or reportlab fallback
└── ui/                      # PySide6 GUI
    ├── main_window.py       # Sidebar nav + stacked widget
    ├── import_window.py     # 7-step import wizard
    ├── anniversary_window.py # Nenki calculation UI
    ├── results_window.py    # Results display, field selection, doc export
    ├── people_table.py      # Person database listing
    └── edit_dialog.py       # Add/edit person & attributes
```

## Key Data Flow
1. **Import**: Excel/CSV → column mapping → validation → SQLite (Person + EAV Attributes)
2. **Calculate**: death_date + year offsets → nenki anniversaries → filter by target year
3. **Export**: results → group by 回忌 type → field selection → Word/PDF generation

## Document Generation (word_generator.py)
- Landscape A4 with tategaki (vertical text, right-to-left)
- Single-column: large font (Pt 28 headers, Pt 18 entries)
- Two-column: Word native `w:cols`, smaller font (Pt 16 headers, Pt 11 entries)
- Display-width padding (`_display_width`) aligns fullwidth/CJK characters
- Data grouped by 回忌 name: header appears once, entries listed below

## Data Model
- **Person**: id, name, death_date (ISO), source_file_path, timestamps
- **Attribute** (EAV): person_id, column_name, value — any custom field
- **sorted_data** format: `[(key, entries)]` where key = `"年忌名|years_offset"`, entries = list of field-value lists

## Important Patterns
- Japanese dates: multiple input formats (era text, kanji, Gregorian, Excel serial)
- Output dates: kanji era format (令和八年十二月三十一日)
- 年忌名 field excluded from per-row data (shown only as group header)
- Field widths computed globally across all entries for consistent alignment
- DB at `memorial_app/data/memorial.db`
