"""Results page - display calculated anniversaries and generate documents with confirmations."""

import datetime
from pathlib import Path
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QCheckBox, QGroupBox,
    QFileDialog, QMessageBox, QScrollArea, QGridLayout,
    QHeaderView, QComboBox, QAbstractItemView, QDialog,
    QFormLayout, QDialogButtonBox, QSpinBox,
)
from PySide6.QtCore import Qt

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.core.nenki_calculator import STANDARD_NENKI, DEFAULT_SELECTED_NENKI, NenkiAnniversary
from memorial_app.core.era_converter import format_date_era
from memorial_app.core.date_converter import format_date_kanji_era, format_nenki_title


class DocumentSettingsDialog(QDialog):
    """Dialog to confirm document generation settings before export."""

    def __init__(self, sorted_data, target_year, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ドキュメント生成設定")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._sorted_data = sorted_data
        self._target_year = target_year

        layout = QVBoxLayout(self)

        # Summary
        summary_group = QGroupBox("出力内容の確認")
        summary_layout = QVBoxLayout(summary_group)

        total_people = sum(len(entries) for _, entries in sorted_data)
        total_groups = len(sorted_data)

        summary_text = (
            f"対象年: {target_year}年\n"
            f"年忌グループ数: {total_groups}\n"
            f"対象人数: {total_people}名\n\n"
            "含まれる年忌:"
        )

        for key, entries in sorted_data:
            nenki_name, _, death_info = key.split("|", 2)
            summary_text += f"\n  {nenki_name} {death_info} — {len(entries)}名"

        summary_label = QLabel(summary_text)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-size: 12px; padding: 8px;")
        summary_layout.addWidget(summary_label)
        layout.addWidget(summary_group)

        # Layout option
        options_group = QGroupBox("レイアウト設定")
        options_layout = QFormLayout(options_group)

        self.layout_combo = QComboBox()
        self.layout_combo.addItem("1列レイアウト（大きい文字）", True)
        self.layout_combo.addItem("2列レイアウト（コンパクト）", False)
        options_layout.addRow("配置:", self.layout_combo)

        layout.addWidget(options_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("生成する")
        buttons.button(QDialogButtonBox.Cancel).setText("キャンセル")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_single_column(self) -> bool:
        return self.layout_combo.currentData()


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

        # Nenki type filter
        nenki_group = QGroupBox("表示する年忌の種類（チェックを外すと出力から除外されます）")
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

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["年忌", "日付（元号漢字）", "日付（西暦）", "氏名", "法名"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

        # Status & export buttons
        btn_layout = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #7f8c8d;")
        btn_layout.addWidget(self.status_label, 1)

        word_btn = QPushButton("Word出力（縦書き）")
        word_btn.setStyleSheet("background: #2980b9; color: white; padding: 8px 20px; font-weight: bold;")
        word_btn.clicked.connect(self._export_word)
        btn_layout.addWidget(word_btn)

        pdf_btn = QPushButton("PDF出力")
        pdf_btn.setStyleSheet("background: #c0392b; color: white; padding: 8px 20px; font-weight: bold;")
        pdf_btn.clicked.connect(self._export_pdf)
        btn_layout.addWidget(pdf_btn)

        layout.addLayout(btn_layout)

    def refresh(self):
        pass

    def set_anniversary_data(self, results, target_year):
        self._results = results
        self._target_year = target_year
        self._filter_results()

    def _filter_results(self):
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
        selected = {name for name, cb in self.nenki_checks.items() if cb.isChecked()}
        filtered = [r for r in self._results if r[0].name in selected]

        groups = defaultdict(list)
        for ann, name, buddhist_name, pid in filtered:
            death_year_era = format_date_kanji_era(ann.death_date)
            key = f"{ann.name}|{ann.years_offset}|（{death_year_era}没）"
            display_name = buddhist_name if buddhist_name else name
            date_str = format_date_kanji_era(ann.date)
            groups[key].append((name, display_name, date_str))

        nenki_order = {name: i for i, (name, _) in enumerate([("百ヶ日", 0)] + STANDARD_NENKI)}
        sorted_data = sorted(groups.items(), key=lambda x: nenki_order.get(x[0].split("|")[0], 999))
        return sorted_data

    def _export_word(self):
        sorted_data = self._get_sorted_data()
        if not sorted_data:
            QMessageBox.information(self, "情報", "出力するデータがありません。\n年忌計算を先に実行してください。")
            return

        # Show settings dialog
        dialog = DocumentSettingsDialog(sorted_data, self._target_year, parent=self)
        if not dialog.exec():
            return

        single_column = dialog.get_single_column()
        title = format_nenki_title(self._target_year)

        path, _ = QFileDialog.getSaveFileName(
            self, "Word文書の保存先を選択",
            f"年忌表_{self._target_year}.docx",
            "Word (*.docx)",
        )
        if not path:
            return

        # Final confirmation
        reply = QMessageBox.question(
            self, "生成確認",
            f"以下の設定でWord文書を生成します:\n\n"
            f"ファイル: {Path(path).name}\n"
            f"レイアウト: {'1列' if single_column else '2列'}\n"
            f"縦書き（tategaki）: はい\n"
            f"対象: {sum(len(e) for _, e in sorted_data)}名\n\n"
            f"生成しますか？",
        )
        if reply != QMessageBox.Yes:
            return

        try:
            from memorial_app.documents.word_generator import WordGenerator
            gen = WordGenerator()
            gen.create_combined_document(sorted_data, title, Path(path), single_column=single_column)

            # Check if PDF was also generated
            pdf_path = Path(path).with_suffix(".pdf")
            if pdf_path.exists():
                QMessageBox.information(
                    self, "完了",
                    f"文書を保存しました:\n\n"
                    f"Word: {path}\n"
                    f"PDF: {pdf_path}",
                )
            else:
                QMessageBox.information(self, "完了", f"Word文書を保存しました:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"文書生成に失敗しました:\n{e}")

    def _export_pdf(self):
        sorted_data = self._get_sorted_data()
        if not sorted_data:
            QMessageBox.information(self, "情報", "出力するデータがありません。\n年忌計算を先に実行してください。")
            return

        # Show settings dialog
        dialog = DocumentSettingsDialog(sorted_data, self._target_year, parent=self)
        if not dialog.exec():
            return

        single_column = dialog.get_single_column()
        title = format_nenki_title(self._target_year)

        path, _ = QFileDialog.getSaveFileName(
            self, "PDFの保存先を選択",
            f"年忌表_{self._target_year}.pdf",
            "PDF (*.pdf)",
        )
        if not path:
            return

        reply = QMessageBox.question(
            self, "生成確認",
            f"PDFを生成します:\n\n"
            f"ファイル: {Path(path).name}\n"
            f"対象: {sum(len(e) for _, e in sorted_data)}名\n\n"
            f"生成しますか？",
        )
        if reply != QMessageBox.Yes:
            return

        try:
            from memorial_app.documents.pdf_generator import PdfGenerator
            gen = PdfGenerator()
            gen.create_document(sorted_data, title, Path(path), single_column=single_column)
            QMessageBox.information(self, "完了", f"PDFを保存しました:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"PDF生成に失敗しました:\n{e}")
