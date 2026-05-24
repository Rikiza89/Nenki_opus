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
)
from PySide6.QtCore import Qt

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.ui.dashboard import DashboardPage
from memorial_app.ui.people_table import PeopleTablePage
from memorial_app.ui.import_window import ImportPage
from memorial_app.ui.anniversary_window import AnniversaryPage
from memorial_app.ui.results_window import ResultsPage
from memorial_app.ui.settings_window import SettingsPage

# Sidebar nav items: (internal key, display label)
_NAV_ITEMS = [
    ("ダッシュボード",  "▸  ホーム"),
    ("データベース",    "▸  名簿管理"),
    ("データインポート","▸  データ取込"),
    ("年忌計算",        "▸  年忌計算"),
    ("結果一覧",        "▸  結果・出力"),
    ("設定",            "▸  設定"),
]


class MainWindow(QMainWindow):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self._results_unlocked = False
        self.setWindowTitle("年忌管理システム")
        self.setMinimumSize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = self._create_sidebar()
        layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.pages = {}
        self._add_page("ダッシュボード",   DashboardPage(self.db))
        self._add_page("データベース",     PeopleTablePage(self.db))
        self._add_page("データインポート", ImportPage(self.db))
        self._add_page("年忌計算",         AnniversaryPage(self.db))
        self._add_page("結果一覧",         ResultsPage(self.db))
        self._add_page("設定",             SettingsPage(self.db))

        self._select_page("ダッシュボード")

    # ------------------------------------------------------------------ #
    # Sidebar                                                              #
    # ------------------------------------------------------------------ #

    def _create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
            }
            QPushButton {
                color: white;
                background: transparent;
                border: none;
                text-align: left;
                padding: 14px 20px;
                font-size: 14px;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:checked {
                background-color: #3498db;
                font-weight: bold;
            }
            QPushButton:disabled {
                color: #7f8c8d;
                background: transparent;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("年忌管理")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "color: white; font-size: 20px; font-weight: bold; padding: 22px;"
        )
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(sep)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in _NAV_ITEMS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, k=key: self._select_page(k))
            layout.addWidget(btn)
            self.nav_buttons[key] = btn

        # 結果一覧 is locked until a calculation produces results
        self.nav_buttons["結果一覧"].setEnabled(False)
        self.nav_buttons["結果一覧"].setToolTip(
            "先に「年忌計算」を実行してください"
        )

        layout.addStretch()

        # Bottom hint when results are locked
        self._results_hint = QLabel("※ 計算後に出力可能")
        self._results_hint.setAlignment(Qt.AlignCenter)
        self._results_hint.setStyleSheet(
            "color: #7f8c8d; font-size: 11px; padding: 4px;"
        )
        layout.addWidget(self._results_hint)

        return sidebar

    # ------------------------------------------------------------------ #
    # Page management                                                      #
    # ------------------------------------------------------------------ #

    def _add_page(self, name: str, widget: QWidget):
        self.pages[name] = widget
        self.stack.addWidget(widget)

    def _select_page(self, name: str):
        if name not in self.pages:
            return
        if name == "結果一覧" and not self._results_unlocked:
            return
        self.stack.setCurrentWidget(self.pages[name])
        for btn_name, btn in self.nav_buttons.items():
            btn.setChecked(btn_name == name)
        page = self.pages[name]
        if hasattr(page, "refresh"):
            page.refresh()

    def unlock_results_page(self):
        """Called by AnniversaryPage after a successful calculation."""
        if self._results_unlocked:
            return
        self._results_unlocked = True
        btn = self.nav_buttons["結果一覧"]
        btn.setEnabled(True)
        btn.setToolTip("")
        self._results_hint.setVisible(False)
