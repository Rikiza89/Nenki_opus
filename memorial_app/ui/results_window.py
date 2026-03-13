"""Results page - display calculated anniversaries and generate documents."""

import datetime
from pathlib import Path
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QCheckBox, QGroupBox,
    QFileDialog, QMessageBox, QScrollArea, QGridLayout,
    QHeaderView, QComboBox,
)
from PySide6.QtCore import Qt

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.core.nenki_calculator import STANDARD_NENKI, DEFAULT_SELECTED_NENKI, NenkiAnniversary
from memorial_app.core.era_converter import format_date_era
from memorial_app.core.date_converter import format_date_kanji_era, format_nenki_title


class ResultsPage(QWidget):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self._results = []
        self._target_year = datetime.date.today().year + 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("結果一覧・ドキュメント生成")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        # Nenki type selection
        nenki_group = QGroupBox("表示する年忌の種類")
        nenki_layout = QGridLayout(nenki_group)
        self.nenki_checks = {}

        all_nenki = [("百ヶ日", 0)] + STANDARD_NENKI
        for i, (name, _) in enumerate(all_nenki):
            cb = QCheckBox(name)
            cb.setChecked(name in DEFAULT_SELECTED_NENKI)
            cb.stateChanged.connect(self._filter_results)
            nenki_layout.addWidget(cb, i // 5, i % 5)
            self.nenki_checks[name] = cb
        layout.addWidget(nenki_group)

        # Layout mode
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("レイアウト:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("1列レイアウト", True)
        self.layout_combo.addItem("2列レイアウト", False)
        options_layout.addWidget(self.layout_combo)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["年忌", "日付（元号漢字）", "日付（西暦）", "氏名", "法名"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        # Export buttons
        btn_layout = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #7f8c8d;")
        btn_layout.addWidget(self.status_label, 1)

        word_btn = QPushButton("Word出力")
        word_btn.setStyleSheet("background: #2980b9; color: white; padding: 8px 20px;")
        word_btn.clicked.connect(self._export_word)
        btn_layout.addWidget(word_btn)

        pdf_btn = QPushButton("PDF出力")
        pdf_btn.setStyleSheet("background: #c0392b; color: white; padding: 8px 20px;")
        pdf_btn.clicked.connect(self._export_pdf)
        btn_layout.addWidget(pdf_btn)

        layout.addLayout(btn_layout)

    def refresh(self):
        pass

    def set_anniversary_data(self, results, target_year):
        """Set data from AnniversaryPage."""
        self._results = results
        self._target_year = target_year
        self._filter_results()

    def _filter_results(self):
        """Filter displayed results based on checked nenki types."""
        selected = {name for name, cb in self.nenki_checks.items() if cb.isChecked()}
        filtered = [r for r in self._results if r[0].name in selected]

        self.table.setRowCount(len(filtered))
        for i, (ann, name, buddhist_name, pid) in enumerate(filtered):
            self.table.setItem(i, 0, QTableWidgetItem(ann.name))
            self.table.setItem(i, 1, QTableWidgetItem(format_date_kanji_era(ann.date)))
            self.table.setItem(i, 2, QTableWidgetItem(ann.date.isoformat()))
            self.table.setItem(i, 3, QTableWidgetItem(name))
            self.table.setItem(i, 4, QTableWidgetItem(buddhist_name))

        self.status_label.setText(f"{len(filtered)}件表示中（全{len(self._results)}件）")

    def _get_sorted_data(self):
        """Prepare sorted data grouped by nenki for document generation."""
        selected = {name for name, cb in self.nenki_checks.items() if cb.isChecked()}
        filtered = [r for r in self._results if r[0].name in selected]

        # Group by nenki name + death year
        groups = defaultdict(list)
        for ann, name, buddhist_name, pid in filtered:
            death_year_era = format_date_kanji_era(ann.death_date)
            key = f"{ann.name}|{ann.years_offset}|（{death_year_era}没）"
            display_name = buddhist_name if buddhist_name else name
            date_str = format_date_kanji_era(ann.date)
            groups[key].append((name, display_name, date_str))

        # Sort by nenki order
        nenki_order = {name: i for i, (name, _) in enumerate([("百ヶ日", 0)] + STANDARD_NENKI)}
        sorted_data = sorted(groups.items(), key=lambda x: nenki_order.get(x[0].split("|")[0], 999))
        return sorted_data

    def _export_word(self):
        sorted_data = self._get_sorted_data()
        if not sorted_data:
            QMessageBox.information(self, "情報", "出力するデータがありません。")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Word文書を保存",
            f"年忌表_{self._target_year}.docx",
            "Word (*.docx)",
        )
        if not path:
            return

        try:
            from memorial_app.documents.word_generator import WordGenerator
            gen = WordGenerator()
            single_column = self.layout_combo.currentData()
            title = format_nenki_title(self._target_year)
            gen.create_combined_document(sorted_data, title, Path(path), single_column=single_column)
            QMessageBox.information(self, "完了", f"Word文書を保存しました:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"文書生成に失敗しました:\n{e}")

    def _export_pdf(self):
        sorted_data = self._get_sorted_data()
        if not sorted_data:
            QMessageBox.information(self, "情報", "出力するデータがありません。")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "PDFを保存",
            f"年忌表_{self._target_year}.pdf",
            "PDF (*.pdf)",
        )
        if not path:
            return

        try:
            from memorial_app.documents.pdf_generator import PdfGenerator
            gen = PdfGenerator()
            title = format_nenki_title(self._target_year)
            gen.create_document(sorted_data, title, Path(path))
            QMessageBox.information(self, "完了", f"PDFを保存しました:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"PDF生成に失敗しました:\n{e}")
