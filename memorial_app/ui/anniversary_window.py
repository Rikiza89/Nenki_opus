"""Anniversary calculation page - calculate and display Nenki schedules."""

import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QComboBox,
    QGroupBox, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.core.nenki_calculator import (
    get_anniversaries_for_year, get_upcoming_anniversaries, get_anniversaries_in_range,
    NenkiAnniversary,
)
from memorial_app.core.era_converter import format_date_era
from memorial_app.core.date_converter import format_date_kanji_era, format_year_kanji_era


class CalculationWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, db, mode, target_year=None, start_date=None, end_date=None):
        super().__init__()
        self.db = db
        self.mode = mode
        self.target_year = target_year
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        try:
            persons = self.db.get_all_persons(offset=0, limit=100000)
            results = []
            total = len(persons)

            for i, person in enumerate(persons):
                self.progress.emit(i, total)
                try:
                    death_date = person.death_date_obj
                except (ValueError, TypeError):
                    continue

                if self.mode == "year":
                    anns = get_anniversaries_for_year(death_date, self.target_year)
                elif self.mode == "upcoming":
                    anns = get_upcoming_anniversaries(death_date, months_ahead=12)
                elif self.mode == "range":
                    anns = get_anniversaries_in_range(death_date, self.start_date, self.end_date)
                else:
                    continue

                # Collect ALL attributes as a dict
                attrs = {}
                for attr in person.attributes:
                    attrs[attr.column_name] = attr.value or ""

                for ann in anns:
                    # Each result carries full person data
                    results.append((ann, person.name, attrs, person.id))

            results.sort(key=lambda x: (x[0].name, x[0].date))
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class AnniversaryPage(QWidget):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self._worker = None
        self._results = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("年忌計算")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        # Mode selection
        mode_group = QGroupBox("計算モード")
        mode_layout = QHBoxLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("指定年の年忌一覧", "year")
        self.mode_combo.addItem("今後12ヶ月の年忌", "upcoming")
        mode_layout.addWidget(self.mode_combo)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2200)
        self.year_spin.setValue(datetime.date.today().year + 1)
        self.year_spin.setPrefix("対象年: ")
        mode_layout.addWidget(self.year_spin)

        calc_btn = QPushButton("計算実行")
        calc_btn.setStyleSheet("background: #3498db; color: white; padding: 8px 20px;")
        calc_btn.clicked.connect(self._calculate)
        mode_layout.addWidget(calc_btn)

        layout.addWidget(mode_group)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["年忌", "日付（元号）", "日付（西暦）", "氏名", "法名"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # Status & export
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #7f8c8d;")
        bottom_layout.addWidget(self.status_label, 1)

        self.export_btn = QPushButton("ドキュメント生成へ")
        self.export_btn.setStyleSheet("background: #8e44ad; color: white; padding: 8px 16px;")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._go_to_document_gen)
        bottom_layout.addWidget(self.export_btn)

        layout.addLayout(bottom_layout)

    def refresh(self):
        pass

    def _calculate(self):
        mode = self.mode_combo.currentData()

        self._worker = CalculationWorker(
            self.db,
            mode=mode,
            target_year=self.year_spin.value(),
        )
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(lambda e: QMessageBox.critical(self, "エラー", e))
        self._worker.start()

    def _on_results(self, results):
        self._results = results
        self.table.setRowCount(len(results))

        for i, (ann, name, attrs, pid) in enumerate(results):
            buddhist_name = attrs.get("法名", "") or attrs.get("戒名", "")
            self.table.setItem(i, 0, QTableWidgetItem(ann.name))
            self.table.setItem(i, 1, QTableWidgetItem(format_date_era(ann.date)))
            self.table.setItem(i, 2, QTableWidgetItem(ann.date.isoformat()))
            self.table.setItem(i, 3, QTableWidgetItem(name))
            self.table.setItem(i, 4, QTableWidgetItem(buddhist_name))

        self.status_label.setText(f"{len(results)}件の年忌が見つかりました")
        self.export_btn.setEnabled(len(results) > 0)

    def _go_to_document_gen(self):
        main_window = self.window()
        if hasattr(main_window, "pages") and "結果一覧" in main_window.pages:
            results_page = main_window.pages["結果一覧"]
            results_page.set_anniversary_data(self._results, self.year_spin.value())
            main_window._select_page("結果一覧")

    def get_results(self):
        return self._results
