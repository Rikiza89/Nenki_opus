"""Results page - display calculated anniversaries and generate documents.

User can choose exactly which fields to include in the document output.
"""

import datetime
from pathlib import Path
from collections import defaultdict, OrderedDict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QCheckBox, QGroupBox,
    QFileDialog, QMessageBox, QScrollArea, QGridLayout,
    QHeaderView, QComboBox, QAbstractItemView, QDialog,
    QFormLayout, QDialogButtonBox, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.core.nenki_calculator import STANDARD_NENKI, DEFAULT_SELECTED_NENKI
from memorial_app.core.date_converter import format_date_kanji_era, format_nenki_title
from memorial_app.core.era_converter import format_date_era


# All possible built-in fields the user can choose from
BUILTIN_FIELDS = OrderedDict([
    ("年忌名", "年忌名"),
    ("法要日（元号漢字）", "法要日（元号漢字）"),
    ("法要日（西暦）", "法要日（西暦）"),
    ("氏名", "氏名"),
    ("命日（元号漢字）", "命日（元号漢字）"),
    ("命日（西暦）", "命日（西暦）"),
])


def _get_field_value(field_key: str, ann, person_name: str, attrs: dict) -> str:
    """Extract a field value from the result data."""
    if field_key == "年忌名":
        return ann.name
    elif field_key == "法要日（元号漢字）":
        return format_date_kanji_era(ann.date)
    elif field_key == "法要日（西暦）":
        return ann.date.isoformat()
    elif field_key == "氏名":
        return person_name
    elif field_key == "命日（元号漢字）":
        return format_date_kanji_era(ann.death_date)
    elif field_key == "命日（西暦）":
        return ann.death_date.isoformat()
    else:
        # EAV attribute
        return attrs.get(field_key, "")


class DocumentSettingsDialog(QDialog):
    """Dialog where user selects which fields to include and layout."""

    def __init__(self, available_fields: list[str], sorted_data, target_year, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ドキュメント生成設定")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self._sorted_data = sorted_data
        self._target_year = target_year

        layout = QVBoxLayout(self)

        # Summary
        total_people = sum(len(entries) for _, entries in sorted_data)
        summary = QLabel(
            f"対象年: {target_year}年　|　"
            f"年忌グループ: {len(sorted_data)}　|　"
            f"対象人数: {total_people}名"
        )
        summary.setStyleSheet("font-size: 13px; color: #2c3e50; padding: 8px; background: #eaf2f8; border-radius: 4px;")
        layout.addWidget(summary)

        # Field selection
        field_group = QGroupBox("ドキュメントに含める項目を選んでください（上から順に表示）")
        field_layout = QVBoxLayout(field_group)

        hint = QLabel("チェックした項目がドキュメントに出力されます。ドラッグで順序変更できます。")
        hint.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        field_layout.addWidget(hint)

        self.field_list = QListWidget()
        self.field_list.setDragDropMode(QListWidget.InternalMove)
        self.field_list.setDefaultDropAction(Qt.MoveAction)

        # Default checked fields
        default_checked = {"氏名", "法要日（元号漢字）"}

        for field in available_fields:
            item = QListWidgetItem(field)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Checked if field in default_checked else Qt.Unchecked)
            self.field_list.addItem(item)

        field_layout.addWidget(self.field_list)

        # Select all / none
        sel_layout = QHBoxLayout()
        all_btn = QPushButton("全て選択")
        all_btn.clicked.connect(lambda: self._set_all_checks(True))
        sel_layout.addWidget(all_btn)
        none_btn = QPushButton("全て解除")
        none_btn.clicked.connect(lambda: self._set_all_checks(False))
        sel_layout.addWidget(none_btn)
        sel_layout.addStretch()
        field_layout.addLayout(sel_layout)

        layout.addWidget(field_group)

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
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all_checks(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.field_list.count()):
            self.field_list.item(i).setCheckState(state)

    def _validate_and_accept(self):
        if not self.get_selected_fields():
            QMessageBox.warning(self, "選択エラー", "少なくとも1つの項目を選択してください。")
            return
        self.accept()

    def get_selected_fields(self) -> list[str]:
        """Return checked fields in display order (top to bottom)."""
        fields = []
        for i in range(self.field_list.count()):
            item = self.field_list.item(i)
            if item.checkState() == Qt.Checked:
                fields.append(item.text())
        return fields

    def get_single_column(self) -> bool:
        return self.layout_combo.currentData()


class ResultsPage(QWidget):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self._results = []  # [(ann, person_name, attrs_dict, person_id), ...]
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
        for i, (ann, name, attrs, pid) in enumerate(filtered):
            buddhist_name = attrs.get("法名", "") or attrs.get("戒名", "")
            self.table.setItem(i, 0, QTableWidgetItem(ann.name))
            self.table.setItem(i, 1, QTableWidgetItem(format_date_kanji_era(ann.date)))
            self.table.setItem(i, 2, QTableWidgetItem(ann.date.isoformat()))
            self.table.setItem(i, 3, QTableWidgetItem(name))
            self.table.setItem(i, 4, QTableWidgetItem(buddhist_name))

        self.status_label.setText(f"{len(filtered)}件表示中（全{len(self._results)}件）")

    def _collect_available_fields(self) -> list[str]:
        """Discover all available fields from data: built-in + all EAV attribute keys."""
        fields = list(BUILTIN_FIELDS.keys())
        # Discover all attribute keys across results
        attr_keys = set()
        for _, _, attrs, _ in self._results:
            attr_keys.update(attrs.keys())
        for key in sorted(attr_keys):
            if key not in fields:
                fields.append(key)
        return fields

    def _get_sorted_data_with_fields(self, selected_fields: list[str]):
        """Build grouped data where each person entry is a list of field values.

        The "年忌名" field is excluded from entry rows because it is already
        displayed once as the group header in the generated document.
        """
        selected_nenki = {name for name, cb in self.nenki_checks.items() if cb.isChecked()}
        filtered = [r for r in self._results if r[0].name in selected_nenki]

        # Exclude 年忌名 from per-row fields; it appears as group header
        entry_fields = [f for f in selected_fields if f != "年忌名"]

        groups = defaultdict(list)
        for ann, name, attrs, pid in filtered:
            # Group by nenki name only so all people with same 回忌 are merged
            key = f"{ann.name}|{ann.years_offset}"
            # Build ordered field values for this person
            entry = []
            for field in entry_fields:
                entry.append(_get_field_value(field, ann, name, attrs))
            groups[key].append(entry)

        nenki_order = {name: i for i, (name, _) in enumerate([("百ヶ日", 0)] + STANDARD_NENKI)}
        sorted_data = sorted(groups.items(), key=lambda x: nenki_order.get(x[0].split("|")[0], 999))
        return sorted_data

    def _do_export(self, format_type: str):
        """Common export flow for Word and PDF."""
        if not self._results:
            QMessageBox.information(self, "情報", "出力するデータがありません。\n年忌計算を先に実行してください。")
            return

        # Check nenki filter
        selected_nenki = {name for name, cb in self.nenki_checks.items() if cb.isChecked()}
        filtered = [r for r in self._results if r[0].name in selected_nenki]
        if not filtered:
            QMessageBox.information(self, "情報", "表示中のデータがありません。\n年忌の種類を選択してください。")
            return

        # Discover available fields
        available_fields = self._collect_available_fields()

        # Show settings dialog
        dialog = DocumentSettingsDialog(available_fields, [], self._target_year, parent=self)
        # We pass empty sorted_data to dialog since we haven't built it yet
        # Build a temporary one for the summary count
        temp_groups = defaultdict(list)
        for ann, name, attrs, pid in filtered:
            death_year_era = format_date_kanji_era(ann.death_date)
            key = f"{ann.name}|{ann.years_offset}|（{death_year_era}没）"
            temp_groups[key].append(name)
        dialog._sorted_data = list(temp_groups.items())
        # Update summary label
        total_people = sum(len(entries) for _, entries in dialog._sorted_data)
        dialog.findChildren(QLabel)[0].setText(
            f"対象年: {self._target_year}年　|　"
            f"年忌グループ: {len(dialog._sorted_data)}　|　"
            f"対象人数: {total_people}名"
        )

        if not dialog.exec():
            return

        selected_fields = dialog.get_selected_fields()
        single_column = dialog.get_single_column()
        sorted_data = self._get_sorted_data_with_fields(selected_fields)
        # 年忌名 is shown as group header, not per-row field
        entry_fields = [f for f in selected_fields if f != "年忌名"]

        if not sorted_data:
            QMessageBox.information(self, "情報", "出力するデータがありません。")
            return

        title = format_nenki_title(self._target_year)

        if format_type == "word":
            ext_filter = "Word (*.docx)"
            default_name = f"年忌表_{self._target_year}.docx"
        else:
            ext_filter = "PDF (*.pdf)"
            default_name = f"年忌表_{self._target_year}.pdf"

        path, _ = QFileDialog.getSaveFileName(self, "保存先を選択", default_name, ext_filter)
        if not path:
            return

        # Final confirmation
        field_list = "、".join(selected_fields)
        reply = QMessageBox.question(
            self, "生成確認",
            f"以下の設定でドキュメントを生成します:\n\n"
            f"形式: {format_type.upper()}\n"
            f"ファイル: {Path(path).name}\n"
            f"レイアウト: {'1列' if single_column else '2列'}\n"
            f"出力項目: {field_list}\n"
            f"対象: {sum(len(e) for _, e in sorted_data)}名\n\n"
            f"生成しますか？",
        )
        if reply != QMessageBox.Yes:
            return

        try:
            if format_type == "word":
                from memorial_app.documents.word_generator import WordGenerator
                gen = WordGenerator()
                gen.create_combined_document(
                    sorted_data, title, Path(path),
                    field_names=entry_fields, single_column=single_column,
                )
                pdf_path = Path(path).with_suffix(".pdf")
                if pdf_path.exists():
                    QMessageBox.information(
                        self, "完了",
                        f"文書を保存しました:\nWord: {path}\nPDF: {pdf_path}",
                    )
                else:
                    QMessageBox.information(self, "完了", f"Word文書を保存しました:\n{path}")
            else:
                from memorial_app.documents.pdf_generator import PdfGenerator
                gen = PdfGenerator()
                gen.create_document(
                    sorted_data, title, Path(path),
                    field_names=entry_fields, single_column=single_column,
                )
                QMessageBox.information(self, "完了", f"PDFを保存しました:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"文書生成に失敗しました:\n{e}")

    def _export_word(self):
        self._do_export("word")

    def _export_pdf(self):
        self._do_export("pdf")
