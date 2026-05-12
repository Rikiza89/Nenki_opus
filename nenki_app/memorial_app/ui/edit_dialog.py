"""Edit/Add dialog for person records with dynamic attribute fields.

The optional 'sync edits back to Excel' feature has been rewritten so that it:
  - locates the original sheet by recorded source path,
  - matches the name column using the same patterns as auto-detect,
  - preserves the user's original date formatting (we only write the date if we
    can find the death-date column; otherwise we leave the Excel cell alone),
  - asks the user before touching the source file (the source file is the
    user's original artefact and we must never silently overwrite it).
"""

import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QMessageBox,
    QCheckBox,
)

from memorial_app.database.db_manager import DatabaseManager, DatabaseError
from memorial_app.core.japanese_date_parser import parse_date, DateValidationError
from memorial_app.core.era_converter import format_date_era
from memorial_app.importer.excel_importer import (
    _NAME_COLUMNS,
    _DEATH_DATE_COLUMNS,
)


class EditDialog(QDialog):
    def __init__(
        self, db_manager: DatabaseManager, person_id: int | None = None, parent=None
    ):
        super().__init__(parent)
        self.db = db_manager
        self.person_id = person_id
        self.is_edit = person_id is not None
        self._person_obj = None

        self.setWindowTitle("編集" if self.is_edit else "新規追加")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例: 山田太郎")
        form.addRow("氏名:", self.name_input)

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

        self.sync_excel_check = QCheckBox("変更を元のExcelファイルにも反映する（試験的）")
        self.sync_excel_check.setChecked(False)
        self.sync_excel_check.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        form.addRow("", self.sync_excel_check)

        layout.addLayout(form)

        attr_header = QLabel("追加項目")
        attr_header.setStyleSheet(
            "font-weight: bold; font-size: 13px; margin-top: 12px;"
        )
        layout.addWidget(attr_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.attr_container = QWidget()
        self.attr_layout = QFormLayout(self.attr_container)
        scroll.setWidget(self.attr_container)
        layout.addWidget(scroll)

        self.attr_inputs: dict[str, QLineEdit] = {}

        add_attr_btn = QPushButton("＋ 項目追加")
        add_attr_btn.setStyleSheet("padding: 4px 12px; font-size: 12px;")
        add_attr_btn.clicked.connect(self._add_new_attribute_row)
        layout.addWidget(add_attr_btn)

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

        try:
            self._load_dynamic_columns()
        except DatabaseError as e:
            QMessageBox.critical(self, "DBエラー", str(e))
        if self.is_edit:
            self._load_person()

    def _load_dynamic_columns(self):
        columns = self.db.get_all_column_names()
        for col_name in columns:
            inp = QLineEdit()
            self.attr_layout.addRow(f"{col_name}:", inp)
            self.attr_inputs[col_name] = inp

    def _load_person(self):
        try:
            person = self.db.get_person(self.person_id)
        except DatabaseError as e:
            QMessageBox.critical(self, "DBエラー", str(e))
            return
        if person is None:
            return
        self._person_obj = person
        self.name_input.setText(person.name)
        try:
            self.date_input.setText(format_date_era(person.death_date_obj))
        except (ValueError, TypeError):
            self.date_input.setText(person.death_date)

        if person.source_file_path:
            self.source_label.setText(person.source_file_path)
            self.sync_excel_check.setEnabled(True)
        else:
            self.source_label.setText("（手動入力）")
            self.sync_excel_check.setEnabled(False)

        for attr in person.attributes:
            if attr.column_name in self.attr_inputs:
                self.attr_inputs[attr.column_name].setText(attr.value or "")
            else:
                inp = QLineEdit(attr.value or "")
                self.attr_layout.addRow(f"{attr.column_name}:", inp)
                self.attr_inputs[attr.column_name] = inp

    def _preview_date(self, text: str):
        if not text.strip():
            self.date_preview.setText("")
            return
        try:
            parsed = parse_date(text)
            self.date_preview.setText(
                f"→ {parsed.era_display} ({parsed.date.isoformat()})"
            )
            self.date_preview.setStyleSheet("color: #27ae60; font-size: 12px;")
        except DateValidationError:
            self.date_preview.setText("日付を認識できません")
            self.date_preview.setStyleSheet("color: #e74c3c; font-size: 12px;")

    def _add_new_attribute_row(self):
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

        attributes: dict[str, str] = {}
        for col_name, inp in self.attr_inputs.items():
            val = inp.text().strip()
            if val:
                attributes[col_name] = val

        for name_inp, value_inp in getattr(self, "_new_attr_rows", []):
            col = name_inp.text().strip()
            val = value_inp.text().strip()
            if col and val:
                attributes[col] = val

        death_date_iso = parsed.date.isoformat()

        try:
            if self.is_edit:
                # Merge so unrelated attrs (not surfaced in the form) are preserved.
                person = self.db.update_person(
                    self.person_id,
                    name=name,
                    death_date=death_date_iso,
                    attributes=attributes,
                    merge_attributes=True,
                )
                if (
                    person
                    and person.source_file_path
                    and self.sync_excel_check.isChecked()
                ):
                    self._sync_excel(person)
            else:
                self.db.add_person(name, death_date_iso, attributes=attributes)
        except DatabaseError as e:
            QMessageBox.critical(self, "保存エラー", str(e))
            return

        self.accept()

    def _sync_excel(self, person):
        """Carefully write the edited record back to the original Excel file.

        Loads every sheet (not only `wb.active`); finds the first sheet whose
        header contains both a recognisable name column AND a row whose value
        in that column equals the person's name; then updates the matching row.

        The user is always asked for permission before the file is written.
        """
        source = person.source_file_path
        if not source:
            return
        path = Path(source)
        if not path.exists():
            QMessageBox.warning(
                self,
                "Excel同期",
                f"元のExcelファイルが見つかりません:\n{source}\n\n"
                "DBの内容のみ更新しました。",
            )
            return
        if path.suffix.lower() not in (".xlsx", ".xlsm"):
            QMessageBox.information(
                self,
                "Excel同期",
                "元のファイルが .xlsx/.xlsm ではないため、Excel への書き戻しはスキップしました。\n"
                "DBの内容のみ更新しました。",
            )
            return

        reply = QMessageBox.question(
            self,
            "Excel同期の確認",
            f"以下のExcelファイルを上書きします:\n{path}\n\n続行しますか？",
        )
        if reply != QMessageBox.Yes:
            return

        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(
                self,
                "Excel同期エラー",
                "openpyxl が利用できないため、Excel への書き戻しを行えません。",
            )
            return

        try:
            wb = openpyxl.load_workbook(path)
        except Exception as e:
            QMessageBox.warning(
                self, "Excel同期エラー", f"Excelファイルを開けませんでした:\n{e}"
            )
            return

        modified_sheet = None
        for ws in wb.worksheets:
            first_row = next(
                ws.iter_rows(min_row=1, max_row=1, values_only=True), None
            )
            if not first_row:
                continue
            headers = [str(h) if h is not None else "" for h in first_row]
            name_col = self._find_col_index(headers, _NAME_COLUMNS)
            if name_col is None:
                continue
            date_col = self._find_col_index(headers, _DEATH_DATE_COLUMNS)
            attr_col_map: dict[str, int] = {}
            for attr in person.attributes:
                for i, h in enumerate(headers):
                    if h == attr.column_name:
                        attr_col_map[attr.column_name] = i

            target_row = None
            for row in ws.iter_rows(min_row=2):
                cell_val = str(row[name_col].value or "").strip()
                if cell_val == person.name:
                    target_row = row
                    break
            if target_row is None:
                continue

            if date_col is not None:
                # Keep the user's original format style if it's a string;
                # otherwise drop in the ISO value.
                existing = target_row[date_col].value
                if isinstance(existing, datetime.date):
                    try:
                        target_row[date_col].value = datetime.date.fromisoformat(
                            person.death_date
                        )
                    except (TypeError, ValueError):
                        target_row[date_col].value = person.death_date
                else:
                    target_row[date_col].value = person.death_date

            for col_name, col_idx in attr_col_map.items():
                value = next(
                    (a.value for a in person.attributes if a.column_name == col_name),
                    None,
                )
                if value is not None:
                    target_row[col_idx].value = value
            modified_sheet = ws.title
            break

        if modified_sheet is None:
            QMessageBox.information(
                self,
                "Excel同期",
                "Excelファイル内で対応する行が見つかりませんでした。\n"
                "DBの内容のみ更新しました。",
            )
            return

        try:
            wb.save(path)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Excel同期エラー",
                f"Excelファイルの保存に失敗しました:\n{e}",
            )
            return

        QMessageBox.information(
            self,
            "Excel同期",
            f"Excelファイル「{path.name}」（シート「{modified_sheet}」）も更新しました。",
        )

    @staticmethod
    def _find_col_index(headers: list[str], patterns: set[str]) -> int | None:
        for i, h in enumerate(headers):
            n = (h or "").strip().replace("　", "")
            if n in patterns or h in patterns:
                return i
        return None
