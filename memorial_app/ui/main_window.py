"""Main application window with sidebar navigation."""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
    QPushButton,
    QLabel,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.ui.dashboard import DashboardPage
from memorial_app.ui.people_table import PeopleTablePage
from memorial_app.ui.import_window import ImportPage
from memorial_app.ui.anniversary_window import AnniversaryPage
from memorial_app.ui.results_window import ResultsPage
from memorial_app.ui.settings_window import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.setWindowTitle("年忌管理システム")
        self.setMinimumSize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        sidebar = self._create_sidebar()
        layout.addWidget(sidebar)

        # Content area
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # Create pages
        self.pages = {}
        self._add_page("ダッシュボード", DashboardPage(self.db))
        self._add_page("データベース", PeopleTablePage(self.db))
        self._add_page("データインポート", ImportPage(self.db))
        self._add_page("年忌計算", AnniversaryPage(self.db))
        self._add_page("結果一覧", ResultsPage(self.db))
        self._add_page("設定", SettingsPage(self.db))

        # Select first page
        self._select_page("ダッシュボード")

    def _create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QFrame { background-color: #2c3e50; }
            QPushButton {
                color: white; background: transparent; border: none;
                text-align: left; padding: 12px 16px; font-size: 14px;
            }
            QPushButton:hover { background-color: #34495e; }
            QPushButton:checked { background-color: #3498db; font-weight: bold; }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("年忌管理")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "color: white; font-size: 18px; font-weight: bold; padding: 20px;"
        )
        layout.addWidget(title)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(sep)

        # Navigation buttons
        self.nav_buttons = {}
        menu_items = [
            "ダッシュボード",
            "データベース",
            "データインポート",
            "年忌計算",
            "結果一覧",
            "設定",
        ]
        for name in menu_items:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, n=name: self._select_page(n))
            layout.addWidget(btn)
            self.nav_buttons[name] = btn

        layout.addStretch()
        return sidebar

    def _add_page(self, name: str, widget: QWidget):
        self.pages[name] = widget
        self.stack.addWidget(widget)

    def _select_page(self, name: str):
        if name in self.pages:
            self.stack.setCurrentWidget(self.pages[name])
            # Update button states
            for btn_name, btn in self.nav_buttons.items():
                btn.setChecked(btn_name == name)
            # Refresh page if it has a refresh method
            page = self.pages[name]
            if hasattr(page, "refresh"):
                page.refresh()
