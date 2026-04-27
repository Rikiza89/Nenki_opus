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
├── python\                        ← Embedded Python 3.11.9（手動で配置）
│   ├── python.exe
│   ├── python311.zip
│   ├── python311._pth             ← setup_packages.bat が自動で書き換える
│   └── Lib\
│       └── site-packages\         ← setup_packages.bat が自動で作成・インストール
│           ├── PySide6\
│           ├── sqlalchemy\
│           └── ...（その他のパッケージ）
├── memorial_app\                  ← アプリ本体（このリポジトリの内容）
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

## ステップ 1 — USB にアプリファイルをコピーする

1. このリポジトリ（`Nenki_opus`）の **内容すべて** を USB のルートにコピーします。

   ```
   コピー対象:
     memorial_app\
     run.py
     run.bat
     setup_packages.bat
     python311._pth
     requirements.txt
     pyproject.toml
   ```

   > `memorial_django\` など、`memorial_app` 以外のフォルダはコピー不要です。

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

## ステップ 3 — Python を USB に展開する

1. USB ルートに `python` という名前のフォルダを作成します。

2. ダウンロードした `python-3.11.9-embed-amd64.zip` を展開し、
   中身をすべて `USB_ROOT\python\` に入れます。

3. 展開後、以下のファイルが存在することを確認します:
   ```
   USB_ROOT\python\python.exe        ← これが存在すれば OK
   USB_ROOT\python\python311.zip
   USB_ROOT\python\python311._pth    ← setup_packages.bat が書き換えます
   ```

   > ⚠️ `python\python\python.exe` のように二重になっていないか確認してください。
   > 展開先は `python\` の **直下** です。

---

## ステップ 4 — setup_packages.bat を実行する（初回のみ）

1. インターネットに接続した状態で行います。

2. USB ルートにある **`setup_packages.bat`** をダブルクリックします。

3. 以下の処理が自動で行われます:
   | ステップ | 内容 |
   |----------|------|
   | 1/5 | Embedded Python の存在確認 |
   | 2/5 | `python311._pth` を書き換えて `site-packages` を有効化 |
   | 3/5 | `python\Lib\site-packages\` フォルダを作成 |
   | 4/5 | pip をインストール（なければ `get-pip.py` を取得） |
   | 5/5 | 必要なパッケージをすべてインストール |

4. 「**セットアップ完了！**」と表示されたら成功です。

   > インストール時間の目安:
   > - 高速回線: 約 3〜5 分
   > - 低速回線: 約 10〜20 分
   > PySide6（約 900 MB）が最も時間がかかります。

   > ⚠️ エラーが出た場合は「ステップ 5 — トラブルシューティング」を参照してください。

---

## ステップ 5 — アプリを起動する

1. USB ルートにある **`run.bat`** をダブルクリックします。

2. 年忌管理アプリが起動します。

   > 初回起動時にデータフォルダ（`memorial_app\data\`）が自動作成されます。

---

## 別の PC で使う場合 / Using on a Different PC

USB をそのまま別の Windows PC に差し込んで `run.bat` をダブルクリックするだけです。
追加のインストールは一切不要です。

**データ（memorial.db）は USB 内の `memorial_app\data\` に保存されているため、
USB を持ち歩けばどの PC でもデータを引き継げます。**

---

## PC にコピーしてインストールする場合 / Installing on a PC

USB からすべてのファイルを PC の任意のフォルダ（例: `C:\nenki\`）にコピーして、
同様に `run.bat` をダブルクリックするだけです。

ショートカットをデスクトップに作る場合:
1. `run.bat` を右クリック →「ショートカットの作成」
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

## python311._pth の内容について（技術メモ）

`setup_packages.bat` は `python\python311._pth` を以下の内容に書き換えます:

```
python311.zip
.
Lib\site-packages
import site
```

| 行 | 意味 |
|----|------|
| `python311.zip` | Python 標準ライブラリ（zip 形式） |
| `.` | Python 実行ファイルのあるフォルダ（`python\`）自身 |
| `Lib\site-packages` | pip でインストールしたパッケージの場所 |
| `import site` | site.py を有効化（pip が正常動作するために必要） |

> デフォルトの Embedded Python では `import site` がコメントアウトされており、
> pip が動作しません。この書き換えによって pip と site-packages が有効になります。

---

## トラブルシューティング / Troubleshooting

### ❌ `python\python.exe が見つかりません` と表示される
→ ステップ 2〜3 を再確認。`python\` フォルダの直下に `python.exe` があるか確認。

### ❌ `get-pip.py のダウンロードに失敗しました` と表示される
→ インターネット接続を確認。プロキシ環境の場合、ネットワーク管理者に相談。

### ❌ `パッケージのインストールに失敗しました` と表示される
→ ウイルス対策ソフトが pip の書き込みをブロックしている可能性があります。
  一時的にオフにして再試行してください。

### ❌ アプリ起動時に黒いコマンドプロンプトが一瞬出て消える
→ `run.bat` の最後の `pause` が無い場合にエラーが発生していますが、
  以下の手順でエラー内容を確認できます:
  1. コマンドプロンプト（cmd.exe）を開く
  2. `cd /d <USB ドライブレター>:\`（例: `cd /d E:\`）
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
