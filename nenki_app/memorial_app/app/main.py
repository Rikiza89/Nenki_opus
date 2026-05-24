"""Memorial anniversary management application entry point."""

import os
import sys
from pathlib import Path


def _setup_webengine_paths() -> None:
    """Ensure QtWebEngineProcess.exe and Qt DLLs are findable on Windows.

    In a proper venv the venv's Scripts/ directory is on PATH so PySide6 DLLs
    are already reachable by any subprocess.  In embedded Python (python311._pth)
    nothing adds PySide6 to PATH, so QtWebEngineProcess.exe crashes with a
    missing-DLL error as soon as Qt tries to render a page.

    This function runs before any PySide6 import so the env vars are in place
    before Qt reads them.
    """
    if os.name != "nt":
        return
    try:
        import importlib.util

        spec = importlib.util.find_spec("PySide6")
        if spec is None or not spec.origin:
            return
        p6_dir = Path(spec.origin).parent

        # --- subprocess executable ---
        process_exe = p6_dir / "QtWebEngineProcess.exe"
        if process_exe.exists():
            os.environ.setdefault("QTWEBENGINEPROCESS_PATH", str(process_exe))

        # --- DLL search path inherited by the spawned subprocess ---
        p6_str = str(p6_dir)
        cur_path = os.environ.get("PATH", "")
        if p6_str.lower() not in cur_path.lower():
            os.environ["PATH"] = p6_str + os.pathsep + cur_path

        # --- WebEngine resource/locale directories ---
        # PySide6 6.x ships them under PySide6/Qt/resources and
        # PySide6/Qt/translations/qtwebengine_locales.
        for res_candidate in (
            p6_dir / "Qt" / "resources",
            p6_dir / "Qt6" / "resources",
            p6_dir / "resources",
        ):
            if res_candidate.is_dir():
                os.environ.setdefault("QTWEBENGINE_RESOURCES_PATH", str(res_candidate))
                break

        for loc_candidate in (
            p6_dir / "Qt" / "translations" / "qtwebengine_locales",
            p6_dir / "Qt6" / "translations" / "qtwebengine_locales",
            p6_dir / "translations" / "qtwebengine_locales",
        ):
            if loc_candidate.is_dir():
                os.environ.setdefault("QTWEBENGINE_LOCALES_PATH", str(loc_candidate))
                break

    except Exception:
        pass


# Must run before any PySide6 import so Qt reads the env vars on first init.
_setup_webengine_paths()

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
