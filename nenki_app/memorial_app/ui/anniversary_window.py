"""Anniversary calculation page - calculate and display Nenki schedules."""

import datetime
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QGroupBox,
    QHeaderView,
    QMessageBox,
    QProgressBar,
    QDateEdit,
)
from PySide6.QtCore import Qt, QThread, Signal, QDate

from memorial_app.database.db_manager import DatabaseManager, DatabaseError
from memorial_app.core.nenki_calculator import (
    get_anniversaries_for_year,
    get_upcoming_anniversaries,
    get_anniversaries_in_range,
)
from memorial_app.core.era_converter import format_date_era


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
            # Paginate through all persons so memory stays bounded regardless of DB size.
            page = 1000
            offset = 0
            persons = []
            while True:
                try:
                    chunk = self.db.get_all_persons(offset=offset, limit=page)
                except DatabaseError as e:
                    self.error.emit(str(e))
                    return
                if not chunk:
                    break
                persons.extend(chunk)
                offset += len(chunk)
                if len(chunk) < page:
                    break

            results = []
            total = len(persons)
            for i, person in enumerate(persons):
                self.progress.emit(i + 1, total)
                death_date = person.safe_death_date
                if death_date is None:
                    continue

                if self.mode == "year":
                    anns = get_anniversaries_for_year(death_date, self.target_year)
                elif self.mode == "upcoming":
                    anns = get_upcoming_anniversaries(death_date, months_ahead=12)
                elif self.mode == "range":
                    anns = get_anniversaries_in_range(
                        death_date, self.start_date, self.end_date
                    )
                else:
                    continue

                attrs = {a.column_name: (a.value or "") for a in person.attributes}
                for ann in anns:
                    results.append((ann, person.name, attrs, person.id))

            results.sort(key=lambda x: (x[0].date, x[0].name))
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class AnniversaryPage(QWidget):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self._worker: CalculationWorker | None = None
        self._results = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("年忌計算")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        mode_group = QGroupBox("計算モード")
        mode_layout = QHBoxLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("指定年の年忌一覧", "year")
        self.mode_combo.addItem("今後12ヶ月の年忌", "upcoming")
        self.mode_combo.addItem("期間指定", "range")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2200)
        self.year_spin.setValue(datetime.date.today().year + 1)
        self.year_spin.setPrefix("対象年: ")
        mode_layout.addWidget(self.year_spin)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        mode_layout.addWidget(QLabel("開始:"))
        mode_layout.addWidget(self.start_date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate().addYears(1))
        mode_layout.addWidget(QLabel("終了:"))
        mode_layout.addWidget(self.end_date_edit)

        calc_btn = QPushButton("計算実行")
        calc_btn.setStyleSheet("background: #3498db; color: white; padding: 8px 20px;")
        calc_btn.clicked.connect(self._calculate)
        mode_layout.addWidget(calc_btn)

        layout.addWidget(mode_group)

        # Progress bar wired to the worker
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["年忌", "日付（元号）", "日付（西暦）", "氏名", "法名"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #7f8c8d;")
        bottom_layout.addWidget(self.status_label, 1)

        self.export_btn = QPushButton("ドキュメント生成へ")
        self.export_btn.setStyleSheet(
            "background: #8e44ad; color: white; padding: 8px 16px;"
        )
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._go_to_document_gen)
        bottom_layout.addWidget(self.export_btn)

        layout.addLayout(bottom_layout)

        # Initialize mode-dependent widget visibility
        self._on_mode_changed()

    def refresh(self):
        pass

    def _on_mode_changed(self):
        mode = self.mode_combo.currentData()
        self.year_spin.setVisible(mode == "year")
        is_range = mode == "range"
        self.start_date_edit.setVisible(is_range)
        self.end_date_edit.setVisible(is_range)
        for w in self.findChildren(QLabel):
            if w.text() == "開始:" or w.text() == "終了:":
                w.setVisible(is_range)

    def _stop_worker(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        self._worker = None

    def _calculate(self):
        self._stop_worker()
        mode = self.mode_combo.currentData()

        if mode == "range":
            s = self.start_date_edit.date().toPython()
            e = self.end_date_edit.date().toPython()
            if e < s:
                QMessageBox.warning(
                    self, "入力エラー", "終了日は開始日以降にしてください。"
                )
                return
        else:
            s = e = None

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 0)  # indeterminate until first progress event

        self._worker = CalculationWorker(
            self.db,
            mode=mode,
            target_year=self.year_spin.value(),
            start_date=s,
            end_date=e,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_results)
        self._worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker.error.connect(self._on_error)
        self._worker.error.connect(lambda _: setattr(self, "_worker", None))
        self._worker.start()

    def _on_progress(self, current: int, total: int):
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)

    def _on_error(self, msg: str):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "エラー", msg)

    def hideEvent(self, event):
        self._stop_worker()
        super().hideEvent(event)

    def _on_results(self, results):
        self.progress_bar.setVisible(False)
        self._results = results
        self.table.setRowCount(len(results))

        for i, (ann, name, attrs, _pid) in enumerate(results):
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
            target_year = self.year_spin.value()
            if self.mode_combo.currentData() != "year":
                target_year = datetime.date.today().year
            results_page.set_anniversary_data(self._results, target_year)
            main_window._select_page("結果一覧")

    def get_results(self):
        return self._results
