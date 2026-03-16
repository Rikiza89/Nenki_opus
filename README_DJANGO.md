# 年忌法要 管理システム — Django Web App

A browser-based version of the Nenki (年忌) Buddhist memorial anniversary manager.
Single-page interface for importing parishioner data, calculating anniversaries, and generating formatted documents.

---

## Requirements

- Python 3.11+
- pip

---

## Setup

### 1. Clone / enter the Django app folder

```bash
cd Nenki_opus/memorial_django
```

### 2. Install dependencies

```bash
pip install django python-docx reportlab pandas openpyxl
```

| Package | Version | Purpose |
|---|---|---|
| Django | 5.2+ | Web framework |
| python-docx | 1.2+ | Word (.docx) generation |
| reportlab | 4.4+ | PDF generation (fallback) |
| pandas | 2.0+ | Excel/CSV parsing |
| openpyxl | 3.1+ | .xlsx engine for pandas |

> **Virtual environment (recommended)**
> ```bash
> python -m venv venv
> source venv/bin/activate   # Windows: venv\Scripts\activate
> pip install django python-docx reportlab pandas openpyxl
> ```

### 3. Initialize the database

```bash
python manage.py migrate
```

This creates `memorial_web.db` (SQLite) inside `memorial_django/`.

### 4. Run the development server

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

---

## Project Structure

```
Nenki_opus/
├── memorial_app/                ← Desktop app (PySide6, standalone)
│   └── ...
└── memorial_django/             ← Django web app (this app)
    ├── manage.py
    ├── memorial_web.db          ← SQLite database (auto-created)
    ├── nenki_web/               ← Django project config
    │   ├── settings.py
    │   └── urls.py
    └── memorial/                ← Main Django app
        ├── models.py            ← Person + Attribute (EAV)
        ├── views.py             ← All API endpoints + page view
        ├── urls.py
        ├── services/
        │   ├── era_converter.py         ← 元号 ↔ Gregorian conversion
        │   ├── date_converter.py        ← Kanji number/era formatting
        │   ├── japanese_date_parser.py  ← Multi-format date parser
        │   ├── nenki_calculator.py      ← Anniversary calculation engine
        │   ├── importer.py              ← Excel/CSV import + column detection
        │   └── document_generator.py   ← Word + PDF output
        └── templates/memorial/
            └── index.html               ← Single-page app template
```

> The two apps are fully independent — `memorial_app` (desktop) and `memorial_django` (web) do not share a database or code at runtime.

---

## Using the App

The interface is a single page with four sequential tabs.

### Tab ① — インポート (Import)

Import parishioner data from Excel or CSV files.

1. Click **ファイル選択** and choose a `.xlsx`, `.xls`, or `.csv` file
2. Click **プレビュー** — the app reads the file and auto-detects column mapping
3. Review the mapping table. Adjust if needed:
   - **氏名** → the name column
   - **命日** → single date column, or split into era/year/month/day columns
4. Click **インポート実行** — duplicates (same name + death date) are skipped automatically
5. Check the result summary (created / skipped counts)

**Supported date formats in imported files:**
- `令和3年5月1日` — Japanese era text
- `令和三年五月一日` — Kanji numerals
- `R3.5.1` / `H30-1-7` — Era abbreviations
- `2020-03-15` / `2020/03/15` — Gregorian
- Excel serial numbers (e.g. `44197`)
- Split columns: separate era, year, month, day columns

---

### Tab ② — 人物一覧 (People)

Browse and manage the person database.

- **Search** by name using the search box
- **Add** a person manually with ＋追加
- **Edit** or **Delete** individual records
- **Select** people (checkboxes) for targeted anniversary calculation
- Click **→ 年忌計算** with people selected to jump to calculation for just those people

---

### Tab ③ — 年忌計算 (Calculate)

Calculate which anniversaries fall in a given year.

1. Set the **対象年** (target year)
2. Choose scope:
   - **全員** — calculate for everyone in the database
   - **選択中** — only the people checked in the People tab
3. Click **計算実行**
4. Results show grouped by anniversary type (一周忌, 三回忌, etc.)
5. Click **📄 文書エディタで開く** to send results to the editor

**Standard anniversary schedule (年忌):**

| 名称 | 没後 |
|---|---|
| 百ヶ日 | 99日後 |
| 一周忌 | 1年 |
| 三回忌 | 2年 |
| 七回忌 | 6年 |
| 十三回忌 | 12年 |
| 十七回忌 | 16年 |
| 二十三回忌 | 22年 |
| 二十七回忌 | 26年 |
| 三十三回忌 | 32年 |
| 三十七回忌 | 36年 |
| 五十回忌 | 49年 |
| 百回忌〜 | 50年ごと延長 |

---

### Tab ④ — 文書エディタ (Document Editor)

Visual layout editor for generating printed documents.

#### Page Settings (left sidebar)
| Setting | Options |
|---|---|
| 文書タイトル | Free text title |
| 向き | 横 A4 (landscape) / 縦 A4 (portrait) |
| 段組み | 1段 / 2段 |
| 文字方向 | 縦書き (tategaki) / 横書き (yokogumi) |
| フォント | MS 明朝 / MS ゴシック / 游明朝 / 游ゴシック |
| 区切り | Field separator character (default: 全角スペース) |

#### Widget Palette
Drag widgets from the left sidebar onto the paper canvas:

| Widget | Description |
|---|---|
| 📌 文書タイトル | Document title (once, at top) |
| 📋 年忌グループ見出し | Group header printed before each 回忌 section |
| 👤 データ行 | One line per person entry |
| ⬜ スペーサー | Blank lines between sections |
| 📄 改ページ | Force page break |

- Drag widgets **onto the paper** to add them
- **Click** a widget to select and edit its properties in the right panel
- **Drag widgets on the canvas** to reorder them
- Click **✕** on a widget to remove it

#### Widget Properties (right panel)
- **Font size** (pt)
- **Bold** on/off
- **Alignment** — left / center / right
- **Group header template** — use `{nenki_name}` and `{anniversary_date}` as variables
- **Entry padding** — aligns columns using display-width-aware full-width spacing (matches desktop app behavior)
- **Spacer lines** — number of blank lines

#### Field Selection (bottom of left sidebar)
Check the fields you want to appear in each data row. Available fields include:
- `name` — person's name
- `death_date_kanji` — death date in kanji era format (e.g. 令和元年五月十日)
- `anniversary_date_kanji` — anniversary date in kanji era format
- Any extra attribute columns imported from Excel (法名, 寺院名, etc.)

The field order in the output follows the order they appear in the selection list.

#### Generating Output

| Button | Output |
|---|---|
| 🖨 印刷 | Opens browser print dialog with print-optimized layout |
| 📄 Word (.docx) | Downloads a `.docx` file with tategaki/yokogumi formatting |
| 📑 PDF | Downloads a PDF (uses reportlab) |

> **Note on Word output:** Vertical text (縦書き) and MS 明朝 font render correctly when opened in Microsoft Word or LibreOffice on a system with Japanese fonts installed.

---

## API Endpoints

All endpoints are under the root URL. The frontend calls these via `fetch`.

| Method | URL | Description |
|---|---|---|
| `GET` | `/` | Single-page app |
| `GET` | `/api/people/` | List people (`?q=`, `?page=`, `?per_page=`) |
| `POST` | `/api/people/` | Create person |
| `GET/PUT/DELETE` | `/api/people/<id>/` | Read / update / delete person |
| `POST` | `/api/import/preview/` | Upload file, get column mapping suggestion |
| `POST` | `/api/import/confirm/` | Confirm import with mapping |
| `POST` | `/api/calculate/` | Run anniversary calculation |
| `POST` | `/api/generate/word/` | Generate and download Word file |
| `POST` | `/api/generate/pdf/` | Generate and download PDF |

---

## Data Model

```
Person
  id            integer (PK)
  name          text
  death_date    text  (ISO: YYYY-MM-DD)
  source_file   text  (original import filename)
  created_at    datetime
  updated_at    datetime

Attribute  (EAV — one row per custom field)
  id            integer (PK)
  person_id     FK → Person
  column_name   text  (e.g. "法名", "寺院名")
  value         text
```

Any column in the imported Excel file beyond name and death date becomes an `Attribute` row, so the schema handles arbitrary custom fields without migrations.

---

## Default Document Layout

The default widget arrangement mirrors the original desktop app (`word_generator.py`):

```
[Title widget]         — font 36pt, bold, centered
[Group header widget]  — font 28pt, bold, centered; template: {nenki_name}　{anniversary_date}
[Entry widget]         — font 18pt, left-aligned, display-width padding enabled
[Spacer widget]        — 1 blank line between groups
```

Page: A4 landscape, 縦書き (tategaki), MS 明朝, 0.5" margins.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'openpyxl'`**
```bash
pip install openpyxl
```

**Imported dates show as parse errors**
- Check the date column format; try mapping to split era/year/month/day columns instead of a single date column.

**Word file has no vertical text**
- Vertical text (`縦書き`) requires Microsoft Word or a compatible viewer. LibreOffice may not render `tbRl` text direction correctly.

**`OperationalError: no such table`**
```bash
cd Nenki_opus/memorial_django
python manage.py migrate
```

**Port already in use**
```bash
python manage.py runserver 8080
# then open http://127.0.0.1:8080
```

**`manage.py: No such file or directory`**
- Make sure you are inside the `memorial_django/` folder, not the repo root:
```bash
cd Nenki_opus/memorial_django
python manage.py runserver
```
