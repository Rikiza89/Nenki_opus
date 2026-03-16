"""Memorial anniversary management application entry point."""

import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PySide6.QtWidgets import QApplication

from memorial_app.core.app_paths import ensure_dirs, EXAMPLE_FILE
from memorial_app.database.db_manager import DatabaseManager
from memorial_app.ui.main_window import MainWindow


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

    # Create all data directories
    ensure_dirs()

    # Initialize database
    db_manager = DatabaseManager()
    db_manager.initialize()

    # Generate example data on first run
    _generate_example_excel()

    # Create and show main window
    window = MainWindow(db_manager)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
