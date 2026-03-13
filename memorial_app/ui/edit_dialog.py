"""Edit/Add dialog for person records with dynamic attribute fields and Excel sync."""

import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QLabel, QPushButton, QScrollArea, QWidget, QMessageBox, QDateEdit,
    QComboBox,
)
from PySide6.QtCore import Qt, QDate

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.core.japanese_date_parser import parse_date, DateValidationError
from memorial_app.core.era_converter import format_date_era


class EditDialog(QDialog):
    def __init__(self, db_manager: DatabaseManager, person_id: int | None = None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.person_id = person_id
        self.is_edit = person_id is not None

        self.setWindowTitle("編集" if self.is_edit else "新規追加")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Form
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例: 山田太郎")
        form.addRow("氏名:", self.name_input)

        # Death date input - text field that accepts any format
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("例: 令和3年5月1日, 2021-05-01, R3.5.1")
        form.addRow("没年月日:", self.date_input)

        self.date_preview = QLabel("")
        self.date_preview.setStyleSheet("color: #27ae60; font-size: 12px;")
        form.addRow("", self.date_preview)
        self.date_input.textChanged.connect(self._preview_date)

        self.source_label = QLabel("")
        self.source_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        form.addRow("元Excel:", self.source_label)

        layout.addLayout(form)

        # Dynamic attributes section
        attr_header = QLabel("追加項目")
        attr_header.setStyleSheet("font-weight: bold; font-size: 13px; margin-top: 12px;")
        layout.addWidget(attr_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.attr_container = QWidget()
        self.attr_layout = QFormLayout(self.attr_container)
        scroll.setWidget(self.attr_container)
        layout.addWidget(scroll)

        self.attr_inputs: dict[str, QLineEdit] = {}

        # Add new attribute row button
        add_attr_btn = QPushButton("＋ 項目追加")
        add_attr_btn.setStyleSheet("padding: 4px 12px; font-size: 12px;")
        add_attr_btn.clicked.connect(self._add_new_attribute_row)
        layout.addWidget(add_attr_btn)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("background: #3498db; color: white; padding: 8px 24px;")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        # Load existing data
        self._load_dynamic_columns()
        if self.is_edit:
            self._load_person()

    def _load_dynamic_columns(self):
        """Create input fields for all known dynamic attribute columns."""
        columns = self.db.get_all_column_names()
        for col_name in columns:
            inp = QLineEdit()
            self.attr_layout.addRow(f"{col_name}:", inp)
            self.attr_inputs[col_name] = inp

    def _load_person(self):
        person = self.db.get_person(self.person_id)
        if person is None:
            return
        self.name_input.setText(person.name)
        try:
            self.date_input.setText(format_date_era(person.death_date_obj))
        except (ValueError, TypeError):
            self.date_input.setText(person.death_date)

        self.source_label.setText(person.source_file_path or "（手動入力）")

        # Fill attribute fields
        for attr in person.attributes:
            if attr.column_name in self.attr_inputs:
                self.attr_inputs[attr.column_name].setText(attr.value or "")
            else:
                # Add new row for unknown column
                inp = QLineEdit(attr.value or "")
                self.attr_layout.addRow(f"{attr.column_name}:", inp)
                self.attr_inputs[attr.column_name] = inp

    def _preview_date(self, text: str):
        if not text.strip():
            self.date_preview.setText("")
            return
        try:
            parsed = parse_date(text)
            self.date_preview.setText(f"→ {parsed.era_display} ({parsed.date.isoformat()})")
            self.date_preview.setStyleSheet("color: #27ae60; font-size: 12px;")
        except DateValidationError:
            self.date_preview.setText("日付を認識できません")
            self.date_preview.setStyleSheet("color: #e74c3c; font-size: 12px;")

    def _add_new_attribute_row(self):
        """Add a new empty attribute input row."""
        name_input = QLineEdit()
        name_input.setPlaceholderText("項目名")
        value_input = QLineEdit()
        value_input.setPlaceholderText("値")

        row_layout = QHBoxLayout()
        row_layout.addWidget(name_input)
        row_layout.addWidget(value_input)

        container = QWidget()
        container.setLayout(row_layout)
        self.attr_layout.addRow(container)

        # Store reference with a placeholder key
        self._new_attr_rows = getattr(self, "_new_attr_rows", [])
        self._new_attr_rows.append((name_input, value_input))

    def _on_save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "氏名を入力してください。")
            return

        date_text = self.date_input.text().strip()
        if not date_text:
            QMessageBox.warning(self, "入力エラー", "没年月日を入力してください。")
            return

        try:
            parsed = parse_date(date_text)
        except DateValidationError as e:
            QMessageBox.warning(self, "日付エラー", str(e))
            return

        if parsed.date > datetime.date.today():
            QMessageBox.warning(self, "日付エラー", "没年月日が未来の日付です。")
            return

        # Collect attributes
        attributes = {}
        for col_name, inp in self.attr_inputs.items():
            val = inp.text().strip()
            if val:
                attributes[col_name] = val

        # Collect new attribute rows
        for name_inp, value_inp in getattr(self, "_new_attr_rows", []):
            col = name_inp.text().strip()
            val = value_inp.text().strip()
            if col and val:
                attributes[col] = val

        death_date_iso = parsed.date.isoformat()

        if self.is_edit:
            person = self.db.update_person(
                self.person_id, name=name, death_date=death_date_iso, attributes=attributes,
            )
            if person and person.source_file_path:
                self._sync_excel(person)
        else:
            self.db.add_person(name, death_date_iso, attributes=attributes)

        self.accept()

    def _sync_excel(self, person):
        """Sync edited data back to the original Excel file."""
        source = person.source_file_path
        if not source:
            return
        path = Path(source)
        if not path.exists():
            return

        try:
            import openpyxl
            wb = openpyxl.load_workbook(path)
            ws = wb.active

            # Find matching row by name in first data column
            header_row = list(ws.iter_rows(min_row=1, max_row=1, values_only=True))[0]
            name_col_idx = None
            for i, h in enumerate(header_row):
                if h and person.name in str(h):
                    name_col_idx = i
                    break

            if name_col_idx is not None:
                for row in ws.iter_rows(min_row=2):
                    cell_val = str(row[name_col_idx].value or "")
                    if cell_val.strip() == person.name:
                        # Update death_date column if found
                        for i, h in enumerate(header_row):
                            h_str = str(h or "")
                            if h_str in ("没年月日", "命日", "死亡日", "逝去日", "往生日"):
                                row[i].value = person.death_date
                        # Update attribute columns
                        for attr in person.attributes:
                            for i, h in enumerate(header_row):
                                if str(h or "") == attr.column_name:
                                    row[i].value = attr.value
                        break

                wb.save(path)
                QMessageBox.information(self, "Excel同期", "元のExcelファイルも更新しました。")
        except Exception as e:
            QMessageBox.warning(self, "Excel同期エラー", f"Excelファイルの更新に失敗しました:\n{e}")
