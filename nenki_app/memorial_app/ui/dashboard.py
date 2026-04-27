"""Dashboard page - summary statistics and recent activity."""

import datetime
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QGridLayout,
)
from PySide6.QtCore import Qt

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.core.nenki_calculator import get_upcoming_anniversaries


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0"):
        super().__init__()
        self.setStyleSheet("""
            QFrame {
                background: white; border: 1px solid #ddd; border-radius: 8px;
                padding: 16px;
            }
        """)
        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            "color: #2c3e50; font-size: 28px; font-weight: bold;"
        )
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)


class DashboardPage(QWidget):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel("ダッシュボード")
        header.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 16px;"
        )
        layout.addWidget(header)

        # Stat cards
        cards_layout = QHBoxLayout()
        self.total_card = StatCard("登録件数")
        self.upcoming_card = StatCard("今後12ヶ月の年忌")
        self.this_year_card = StatCard("今年の年忌")
        cards_layout.addWidget(self.total_card)
        cards_layout.addWidget(self.upcoming_card)
        cards_layout.addWidget(self.this_year_card)
        layout.addLayout(cards_layout)

        # Upcoming list
        upcoming_header = QLabel("直近の年忌予定")
        upcoming_header.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #2c3e50; margin-top: 24px;"
        )
        layout.addWidget(upcoming_header)

        self.upcoming_list = QLabel("データを読み込み中...")
        self.upcoming_list.setStyleSheet("color: #555; font-size: 13px; padding: 8px;")
        self.upcoming_list.setWordWrap(True)
        layout.addWidget(self.upcoming_list)

        # Sample data hint
        self.sample_hint = QLabel("")
        self.sample_hint.setWordWrap(True)
        self.sample_hint.setStyleSheet(
            "color: #3498db; font-size: 12px; padding: 12px; "
            "background: #eaf2f8; border-radius: 4px; margin-top: 8px;"
        )
        self.sample_hint.setVisible(False)
        layout.addWidget(self.sample_hint)

        layout.addStretch()

    def refresh(self):
        total = self.db.get_person_count()
        self.total_card.set_value(str(total))

        # Calculate upcoming anniversaries
        today = datetime.date.today()
        this_year = today.year
        upcoming_count = 0
        this_year_count = 0
        upcoming_items = []

        _DASHBOARD_LIMIT = 500
        persons = self.db.get_all_persons(offset=0, limit=_DASHBOARD_LIMIT)
        for person in persons:
            try:
                death_date = person.death_date_obj
            except (ValueError, TypeError):
                continue

            from memorial_app.core.nenki_calculator import (
                get_anniversaries_for_year,
                get_upcoming_anniversaries,
            )

            year_anns = get_anniversaries_for_year(death_date, this_year)
            this_year_count += len(year_anns)

            upcoming = get_upcoming_anniversaries(
                death_date, months_ahead=12, from_date=today
            )
            upcoming_count += len(upcoming)

            for ann in upcoming[:3]:  # Show first few per person
                upcoming_items.append((ann.date, ann.name, person.name))

        self.upcoming_card.set_value(str(upcoming_count))
        self.this_year_card.set_value(str(this_year_count))

        # Sort and display upcoming
        upcoming_items.sort(key=lambda x: x[0])
        if upcoming_items:
            lines = []
            for date, nenki, name in upcoming_items[:20]:
                from memorial_app.core.era_converter import format_date_era

                lines.append(f"{format_date_era(date)}  {nenki}  {name}")
            self.upcoming_list.setText("\n".join(lines))
        else:
            self.upcoming_list.setText("直近の年忌予定はありません")

        # Show sample data hint when database is empty
        if total == 0:
            from memorial_app.core.app_paths import EXAMPLE_FILE

            sample_path = EXAMPLE_FILE
            if sample_path.exists():
                self.sample_hint.setText(
                    f"サンプルデータが利用可能です。\n"
                    f"「データインポート」ページで以下のファイルを読み込んでください:\n"
                    f"{sample_path}"
                )
                self.sample_hint.setVisible(True)
            else:
                self.sample_hint.setVisible(False)
        else:
            self.sample_hint.setVisible(False)
