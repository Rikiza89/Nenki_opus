"""Memorial anniversary management application entry point."""

import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PySide6.QtWidgets import QApplication, QMessageBox

from memorial_app.core.app_paths import ensure_dirs, EXAMPLE_FILE
from memorial_app.database.db_manager import DatabaseManager, DatabaseError
from memorial_app.ui.main_window import MainWindow


def _generate_example_excel():
    """Generate example Excel dataset on first run."""
    if EXAMPLE_FILE.exists():
        return
    try:
        from memorial_app.scripts.generate_example_data import generate_example

        generate_example(EXAMPLE_FILE)
    except Exception:
        # Example data is a convenience, not required for the app to work.
        pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("年忌管理")
    app.setOrganizationName("寺院管理システム")

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
