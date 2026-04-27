@echo off
setlocal
chcp 65001 >nul 2>&1

echo ============================================================
echo   年忌管理アプリ - 初回セットアップ
echo   Memorial App - First-Time Package Setup
echo ============================================================
echo.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PYTHON=%ROOT%\python\python.exe"
set "SITE_PKG=%ROOT%\python\Lib\site-packages"
set "PTH_FILE=%ROOT%\python\python311._pth"

:: ── Step 1: Verify embedded Python ──────────────────────────────────────────
echo [1/5] Embedded Python を確認中...
if not exist "%PYTHON%" (
    echo.
    echo  ERROR: python\python.exe が見つかりません。
    echo.
    echo  以下の手順で Embedded Python 3.11.9 を配置してください:
    echo.
    echo    1. ブラウザで以下のURLを開く:
    echo       https://www.python.org/downloads/release/python-3119/
    echo.
    echo    2. ページ下部の「Files」から
    echo       "Windows embeddable package (64-bit)"
    echo       (ファイル名: python-3.11.9-embed-amd64.zip) をダウンロード
    echo.
    echo    3. ダウンロードした zip を「python」フォルダに展開する
    echo       (python\python.exe が存在する状態にする)
    echo.
    echo    4. このスクリプトを再実行する
    echo.
    pause
    exit /b 1
)
echo     OK: %PYTHON%
echo.

:: ── Step 2: Patch python311._pth to enable site-packages ────────────────────
echo [2/5] python311._pth を設定中...
if not exist "%PTH_FILE%" (
    echo  WARNING: python311._pth が見つかりません。スキップします。
) else (
    :: Write the patched _pth content (overwrites existing)
    (
        echo python311.zip
        echo .
        echo Lib\site-packages
        echo import site
    ) > "%PTH_FILE%"
    echo     OK: site-packages パスを有効化しました。
)
echo.

:: ── Step 3: Create site-packages directory ───────────────────────────────────
echo [3/5] site-packages フォルダを作成中...
if not exist "%SITE_PKG%" mkdir "%SITE_PKG%"
echo     OK: %SITE_PKG%
echo.

:: ── Step 4: Bootstrap pip ────────────────────────────────────────────────────
echo [4/5] pip をセットアップ中...
"%PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo     pip が見つかりません。get-pip.py からインストールします...
    echo     (インターネット接続が必要です)
    curl -sS -o "%TEMP%\get-pip.py" "https://bootstrap.pypa.io/get-pip.py"
    if errorlevel 1 (
        echo.
        echo  ERROR: get-pip.py のダウンロードに失敗しました。
        echo  インターネット接続を確認してください。
        pause
        exit /b 1
    )
    "%PYTHON%" "%TEMP%\get-pip.py" --no-warn-script-location
    del "%TEMP%\get-pip.py" >nul 2>&1
    echo     OK: pip のインストール完了。
) else (
    echo     OK: pip は既にインストール済みです。
)
echo.

:: ── Step 5: Install all required packages ────────────────────────────────────
echo [5/5] パッケージをインストール中...
echo     (PySide6 は大きいため数分かかる場合があります)
echo.

"%PYTHON%" -m pip install ^
    "PySide6>=6.6.0" ^
    "SQLAlchemy>=2.0" ^
    "pandas>=2.0" ^
    "openpyxl>=3.1" ^
    "xlrd>=2.0" ^
    "python-docx>=1.0" ^
    "reportlab>=4.0" ^
    --target "%SITE_PKG%" ^
    --no-warn-script-location ^
    --disable-pip-version-check

if errorlevel 1 (
    echo.
    echo  ERROR: パッケージのインストールに失敗しました。
    echo  ネットワーク接続を確認して再度実行してください。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   セットアップ完了！
echo   Setup Complete!
echo ============================================================
echo.
echo   run.bat をダブルクリックするとアプリが起動します。
echo   Double-click run.bat to launch the application.
echo.
pause
