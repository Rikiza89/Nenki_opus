"""Memorial anniversary management application entry point."""

import os
import sys
from pathlib import Path

# ── Embedded-Python bootstrap ──────────────────────────────────────────────
# When deployed with a bundled Python (python/ folder alongside nenki_app/),
# Qt's helper processes and plugins must be located BEFORE the first PySide6
# import.  Setting these env-vars here covers both QtWebEngineProcess (so the
# visual-editor preview works) and the general Qt plugin path.
_app_dir = Path(__file__).resolve().parent.parent.parent  # …/nenki_app/
_python_dir = _app_dir.parent / "python"
if _python_dir.exists():
    _site = _python_dir / "Lib" / "site-packages"
    if _site.exists() and str(_site) not in sys.path:
        sys.path.insert(0, str(_site))
    _ps6 = _site / "PySide6"
    _qt_bin = _ps6 / "Qt" / "bin"
    _qt_plugins = _ps6 / "Qt" / "plugins"
    for _proc in (_qt_bin / "QtWebEngineProcess.exe", _qt_bin / "QtWebEngineProcess"):
        if _proc.exists():
            os.environ.setdefault("QTWEBENGINEPROCESS_PATH", str(_proc))
            break
    if _qt_plugins.exists():
        os.environ.setdefault("QT_PLUGIN_PATH", str(_qt_plugins))
    if _qt_bin.exists():
        os.environ["PATH"] = str(_qt_bin) + os.pathsep + os.environ.get("PATH", "")
# ──────────────────────────────────────────────────────────────────────────

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QFont

from memorial_app.core.app_paths import ensure_dirs, EXAMPLE_FILE
from memorial_app.database.db_manager import DatabaseManager, DatabaseError
from memorial_app.ui.main_window import MainWindow

# Global stylesheet — sets a comfortable base font size for elderly users.
_GLOBAL_STYLE = """
QWidget {
    font-size: 14px;
}
QLabel {
    font-size: 14px;
}
QPushButton {
    font-size: 14px;
    min-height: 36px;
    padding: 6px 14px;
}
QComboBox, QSpinBox, QLineEdit, QDateEdit {
    font-size: 14px;
    min-height: 30px;
    padding: 2px 6px;
}
QTableWidget {
    font-size: 13px;
}
QHeaderView::section {
    font-size: 13px;
    font-weight: bold;
    padding: 4px;
}
QGroupBox {
    font-size: 14px;
    font-weight: bold;
}
QCheckBox, QRadioButton {
    font-size: 14px;
}
QProgressBar {
    font-size: 13px;
    min-height: 22px;
}
"""


def _generate_example_excel():
    """Generate example Excel dataset on first run."""
    if EXAMPLE_FILE.exists():
        return
    try:
        from memorial_app.scripts.generate_example_data import generate_example
        generate_example(EXAMPLE_FILE)
    except Exception:
        pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("年忌管理")
    app.setOrganizationName("寺院管理システム")
    app.setStyleSheet(_GLOBAL_STYLE)

    # Set default font with a CJK-compatible face so all Japanese characters render cleanly.
    default_font = QFont("MS Gothic", 11)
    default_font.setStyleHint(QFont.TypeWriter)
    app.setFont(default_font)

    try:
        ensure_dirs()
    except OSError as e:
        QMessageBox.critical(
            None,
            "起動エラー",
            f"データディレクトリの作成に失敗しました:\n{e}",
        )
        sys.exit(1)

    db_manager = DatabaseManager()
    try:
        db_manager.initialize()
    except DatabaseError as e:
        QMessageBox.critical(None, "起動エラー", str(e))
        sys.exit(1)

    _generate_example_excel()

    window = MainWindow(db_manager)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
