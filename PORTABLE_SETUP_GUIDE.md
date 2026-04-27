# 年忌管理アプリ — ポータブル USB セットアップガイド
# Memorial App — Portable USB Setup Guide

このガイドでは、年忌管理アプリを USB メモリに入れて、Python がインストールされていない
Windows PC でもそのまま起動できるようにする手順を説明します。

---

## 必要なもの / Requirements

| 項目 | 詳細 |
|------|------|
| USB メモリ容量 | **最低 1.5 GB**（PySide6 が約 900 MB）|
| OS | Windows 10 / 11 (64 ビット) |
| 初回セットアップ時のみ | インターネット接続 |
| PDF 縦書き出力 | Microsoft Word がインストールされた PC |

---

## USB の最終フォルダ構成 / Final Folder Layout

セットアップ完了後の USB の構成です（参考）:

```
USB_ROOT\
└── nenki_app\                         ← このフォルダをまるごと USB に置く
    ├── python\                        ← Embedded Python 3.11.9（手動で配置）
    │   ├── python.exe
    │   ├── python311.zip
    │   ├── python311._pth             ← setup_packages.bat が自動で書き換える
    │   └── Lib\
    │       └── site-packages\         ← setup_packages.bat が自動で作成・インストール
    │           ├── PySide6\
    │           ├── sqlalchemy\
    │           └── ...（その他のパッケージ）
    ├── memorial_app\                  ← アプリ本体
    │   ├── app\
    │   ├── core\
    │   ├── database\
    │   ├── documents\
    │   ├── importer\
    │   ├── ui\
    │   └── data\                      ← DB・バックアップ（初回起動時に自動作成）
    │       ├── memorial.db
    │       ├── backups\
    │       └── config\
    ├── run.py                         ← 起動スクリプト（自動）
    ├── run.bat                        ← ダブルクリックで起動
    ├── setup_packages.bat             ← 初回セットアップ用
    └── python311._pth                 ← _pth テンプレート（参考用）
```

---

## ステップ 1 — USB に nenki_app フォルダをコピーする

1. このリポジトリ（`Nenki_opus`）の中にある **`nenki_app`** フォルダを丸ごと
   USB のルートにコピーします。

   ```
   コピー対象（フォルダ 1 つだけ）:
     nenki_app\
   ```

   コピー後の USB の状態:
   ```
   USB_ROOT\
   └── nenki_app\
       ├── memorial_app\
       ├── run.py
       ├── run.bat
       ├── setup_packages.bat
       └── python311._pth
   ```

   > `memorial_django\` や `requirements.txt` などはコピー不要です（開発用ファイル）。

---

## ステップ 2 — Embedded Python 3.11.9 をダウンロードする

1. 以下の URL をブラウザで開きます:
   ```
   https://www.python.org/downloads/release/python-3119/
   ```

2. ページを下にスクロールして「**Files**」セクションを探します。

3. 以下のファイルをダウンロードします:
   ```
   Windows embeddable package (64-bit)
   ファイル名: python-3.11.9-embed-amd64.zip
   サイズ: 約 10 MB
   ```

   > ⚠️ 「Windows installer (64-bit)」ではありません。**embeddable package** を選んでください。

---

## ステップ 3 — Python を nenki_app フォルダに展開する

1. USB 上の `nenki_app\` の中に `python` という名前のフォルダを作成します。

   ```
   USB_ROOT\nenki_app\python\    ← このフォルダを作る
   ```

2. ダウンロードした `python-3.11.9-embed-amd64.zip` を展開し、
   中身をすべて `nenki_app\python\` に入れます。

3. 展開後、以下のファイルが存在することを確認します:
   ```
   USB_ROOT\nenki_app\python\python.exe        ← これが存在すれば OK
   USB_ROOT\nenki_app\python\python311.zip
   USB_ROOT\nenki_app\python\python311._pth    ← setup_packages.bat が書き換えます
   ```

   > ⚠️ `python\python\python.exe` のように二重になっていないか確認してください。
   > 展開先は `nenki_app\python\` の **直下** です。

---

## ステップ 4 — setup_packages.bat を実行する（初回のみ）

1. インターネットに接続した状態で行います。

2. `nenki_app\` の中にある **`setup_packages.bat`** をダブルクリックします。

3. 以下の処理が自動で行われます:
   | ステップ | 内容 |
   |----------|------|
   | 1/5 | Embedded Python の存在確認 |
   | 2/5 | `python311._pth` をリネームして隔離モードを無効化 |
   | 3/5 | `python\Lib\site-packages\` フォルダを作成 |
   | 4/5 | pip をインストール（なければ `get-pip.py` を取得） |
   | 5/5 | 必要なパッケージをすべてインストール |

4. 「**セットアップ完了！**」と表示されたら成功です。

   > インストール時間の目安:
   > - 高速回線: 約 3〜5 分
   > - 低速回線: 約 10〜20 分
   > PySide6（約 900 MB）が最も時間がかかります。

   > ⚠️ エラーが出た場合は「トラブルシューティング」セクションを参照してください。

---

## ステップ 5 — アプリを起動する

1. `nenki_app\` の中にある **`run.bat`** をダブルクリックします。

2. 年忌管理アプリが起動します。

   > 初回起動時にデータフォルダ（`nenki_app\memorial_app\data\`）が自動作成されます。

---

## 別の PC で使う場合 / Using on a Different PC

USB をそのまま別の Windows PC に差し込んで `nenki_app\run.bat` をダブルクリックするだけです。
追加のインストールは一切不要です。

**データ（memorial.db）は `nenki_app\memorial_app\data\` に保存されているため、
USB を持ち歩けばどの PC でもデータを引き継げます。**

---

## PC にコピーしてインストールする場合 / Installing on a PC

`nenki_app\` フォルダを丸ごと PC の任意の場所（例: `C:\nenki_app\`）にコピーして、
`run.bat` をダブルクリックするだけです。

ショートカットをデスクトップに作る場合:
1. `nenki_app\run.bat` を右クリック →「ショートカットの作成」
2. 作成されたショートカットをデスクトップに移動

---

## PDF 縦書き出力について / Vertical-Text PDF Output

| 状況 | PDF の出力方法 |
|------|--------------|
| Microsoft Word がインストールされた PC | Word 経由で変換（縦書きレイアウト保持） |
| Word がない PC | reportlab で代替生成（横書きレイアウト） |

縦書き PDF が必要な場合は、Word がインストールされた PC で操作するか、
「Word 出力（.docx）」で保存して手動で PDF に変換してください。

---

## python311._pth の扱いについて（技術メモ）

Embedded Python は通常「隔離モード（isolated mode）」で動作し、
`python311._pth` ファイルによってパスが厳しく制御されています。

`setup_packages.bat` はこのファイルを **リネーム**（`python311._pth.bak`）することで
隔離モードを無効化します。

`run.bat` は代わりに `PYTHONHOME` 環境変数を使って Python に場所を教えます:

```batch
set PYTHONHOME=%CD%\python    ← 標準ライブラリと site-packages の場所
set PYTHONPATH=%CD%           ← memorial_app パッケージのある場所（nenki_app\）
```

| 変数 | 意味 |
|------|------|
| `PYTHONHOME` | Python 実行時の「ホーム」（stdlib・site-packages を探す場所） |
| `PYTHONPATH` | アプリのソースコード（`memorial_app` パッケージ）の場所 |

> `_pth` ファイルを書き換えるより、環境変数で制御する方が副作用なく安全です。

---

## トラブルシューティング / Troubleshooting

### ❌ `python\python.exe が見つかりません` と表示される
→ ステップ 3 を再確認。`nenki_app\python\` の直下に `python.exe` があるか確認。

### ❌ `get-pip.py のダウンロードに失敗しました` と表示される
→ インターネット接続を確認。プロキシ環境の場合、ネットワーク管理者に相談。

### ❌ `パッケージのインストールに失敗しました` と表示される
→ ウイルス対策ソフトが pip の書き込みをブロックしている可能性があります。
  一時的にオフにして再試行してください。

### ❌ アプリ起動時に黒いコマンドプロンプトが一瞬出て消える
→ エラーが発生しています。以下の手順でエラー内容を確認できます:
  1. コマンドプロンプト（cmd.exe）を開く
  2. `cd /d <USB ドライブレター>:\nenki_app`（例: `cd /d E:\nenki_app`）
  3. `run.bat` と入力して Enter

### ❌ PDF が横書きになる（縦書きではない）
→ Microsoft Word がインストールされていない PC では横書き（reportlab）で出力されます。
  Word がインストールされた PC で操作するか、`.docx` 出力をご利用ください。

### ❌ `PySide6` に関するエラーが出る
→ Windows の Visual C++ ランタイムが不足している可能性があります。
  以下から最新版をインストールしてください:
  `https://aka.ms/vs/17/release/vc_redist.x64.exe`

---

## パッケージ一覧 / Package List

| パッケージ | バージョン | 用途 |
|-----------|-----------|------|
| PySide6 | ≥6.6.0 | GUI フレームワーク |
| SQLAlchemy | ≥2.0 | データベース (SQLite) |
| pandas | ≥2.0 | Excel/CSV 読み込み |
| openpyxl | ≥3.1 | .xlsx ファイル処理 |
| xlrd | ≥2.0 | .xls ファイル処理（旧形式） |
| python-docx | ≥1.0 | Word 文書生成（縦書き） |
| reportlab | ≥4.0 | PDF 代替生成 |
| docx2pdf | オプション | Word→PDF 変換（Word 必須） |
