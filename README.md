# 年忌管理 (Nenki Kanri) - Buddhist Memorial Anniversary Manager

寺院職員向けの年忌法要管理デスクトップアプリケーション。
檀家の没年月日から年忌法要（百ヶ日、一周忌、三回忌...五十回忌）を自動計算し、Word/PDF文書として出力します。

A PySide6 desktop application for Japanese Buddhist temple staff to manage memorial anniversary (年忌) records. It automatically calculates nenki anniversaries from death dates and generates vertical-text (縦書き) Word/PDF documents.

---

## 機能一覧 (Features)

- **年忌自動計算**: 没年月日から百ヶ日〜五十回忌までを自動算出
- **和暦対応**: 明治・大正・昭和・平成・令和の元号変換、漢数字表記
- **Excelインポート**: 7段階ウィザードによるデータ取込（シート選択→列マッピング→列統合→プレビュー→検証→確認→完了）
- **列統合機能**: 既存DBの列名と異なる列名のデータを統合してインポート可能（例: 「戒名」→「法名」）
- **縦書き文書出力**: Word(.docx)で縦書きA4横向き文書を生成。MS明朝フォント使用
- **PDF変換**: docx2pdf経由またはreportlabフォールバックでPDF出力
- **出力フィールド選択**: ユーザーが出力する項目と順序をドラッグ&ドロップで自由に設定
- **1段・2段レイアウト**: 文書の段組みを選択可能
- **データ管理**: 檀家情報の追加・編集・削除・検索
- **サンプルデータ**: 初回起動時に100件のサンプルExcelを自動生成

---

## 動作環境 (Requirements)

- Python 3.11 以上
- OS: Windows / macOS / Linux

---

## インストール (Installation)

### 1. リポジトリのクローン

```bash
git clone https://github.com/Rikiza89/Nenki_opus.git
cd Nenki_opus
```

### 2. 仮想環境の作成と有効化

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -e .
```

PDF変換機能（docx2pdf）も使う場合:

```bash
pip install -e ".[pdf]"
```

> **注意**: `docx2pdf` はWindowsではMicrosoft Wordが、macOSではLibreOfficeが必要です。
> インストールしなくても、reportlabによるフォールバックPDF出力は利用可能です。

### 代替: requirements.txt を使う場合

```bash
pip install -r requirements.txt
pip install -e .
```

---

## 起動方法 (Usage)

### コマンドから起動

```bash
nenki
```

### Pythonモジュールとして起動

```bash
python -m memorial_app.app.main
```

初回起動時にサンプルデータ (`memorial_app/data/example_dataset.xlsx`) が自動生成されます。

---

## 使い方 (How to Use)

### 1. データインポート

サイドバーの「データインポート」から、Excel (.xlsx/.xls) または CSV ファイルを取り込みます。

| ステップ | 内容 |
|---------|------|
| 1/7 | ファイル選択・シート選択（複数シートの場合はここで選択） |
| 2/7 | 基本列マッピング（氏名・没年月日・法名の列を指定） |
| 3/7 | 追加列の統合設定（既存DB列への統合 or 新規列として追加） |
| 4/7 | データプレビュー（取込データの確認） |
| 5/7 | データ検証（日付解析・必須項目・重複チェック） |
| 6/7 | インポート確認（最終確認） |
| 7/7 | 完了 |

> ステップ3は、DBに既存データがある場合のみ表示されます。
> 例えば、ファイルの「戒名」列をDBの「法名」列に統合する、といった操作が可能です。

### 2. 年忌計算

サイドバーの「年忌計算」から、対象年を指定して計算を実行します。
該当する年忌法要の一覧が表示されます。

### 3. 文書出力

年忌計算結果の画面から「Word出力」または「PDF出力」を選択します。

**出力設定ダイアログ**:
- 出力するフィールドをチェックボックスで選択
- ドラッグ&ドロップで表示順序を変更
- 1段組み / 2段組みのレイアウトを選択

出力される文書は **縦書き（tategaki）A4横向き** で、MS明朝フォントを使用します。

### 4. データ管理

サイドバーの「檀家一覧」から、個別の編集・削除が可能です。

---

## データの保存場所

すべてのデータはアプリケーションディレクトリ内に保存されます:

```
memorial_app/
└── data/
    ├── memorial.db              # SQLiteデータベース
    ├── example_dataset.xlsx     # サンプルデータ
    ├── backups/                 # 自動バックアップ
    └── config/
        └── custom_eras.json     # カスタム元号設定
```

---

## 対応する日付形式

インポート時に以下の日付形式を自動認識します:

| 形式 | 例 |
|------|------|
| 和暦漢字 | 令和五年三月十六日 |
| 和暦数字 | 令和5年3月16日 |
| 西暦 | 2023-03-16, 2023/03/16 |
| 元年表記 | 令和元年五月一日 |
| 分割列 | 元号・年・月・日を別々の列で指定 |

---

## プロジェクト構成

```
Nenki_opus/
├── pyproject.toml                  # パッケージ設定
├── requirements.txt                # 依存パッケージ
├── README.md
└── memorial_app/
    ├── app/
    │   └── main.py                 # エントリーポイント
    ├── core/
    │   ├── app_paths.py            # パス設定
    │   ├── date_converter.py       # 漢数字変換
    │   ├── era_converter.py        # 和暦変換
    │   ├── japanese_date_parser.py # 日付解析
    │   └── nenki_calculator.py     # 年忌計算
    ├── database/
    │   ├── models.py               # SQLAlchemyモデル
    │   └── db_manager.py           # DB操作
    ├── documents/
    │   ├── word_generator.py       # Word文書生成（縦書き）
    │   └── pdf_generator.py        # PDF生成
    ├── importer/
    │   ├── excel_importer.py       # Excel読込・列検出
    │   └── validation_pipeline.py  # データ検証パイプライン
    ├── scripts/
    │   └── generate_example_data.py
    └── ui/
        ├── main_window.py          # メインウィンドウ
        ├── dashboard.py            # ダッシュボード
        ├── people_table.py         # 檀家一覧
        ├── edit_dialog.py          # 編集ダイアログ
        ├── import_window.py        # インポートウィザード
        ├── anniversary_window.py   # 年忌計算
        ├── results_window.py       # 結果表示・文書出力
        ├── settings_window.py      # 設定
        └── template_editor.py      # テンプレート編集
```

---

## ライセンス (License)

This project is provided as-is for temple administrative use.
