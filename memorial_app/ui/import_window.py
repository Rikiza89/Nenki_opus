"""Data import page - Excel/CSV file import with validation pipeline UI."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QMessageBox, QGroupBox, QFormLayout, QHeaderView, QDialog, QDialogButtonBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.importer.excel_importer import read_file, get_sheet_info, auto_detect_mapping, ColumnMapping
from memorial_app.importer.validation_pipeline import (
    ValidationPipeline, ValidationResult, ValidatedRow, ErrorRow,
    import_validated_rows, export_error_rows,
)


class ImportWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(object)  # ValidationResult
    error = Signal(str)

    def __init__(self, db, df, mapping, source_path):
        super().__init__()
        self.db = db
        self.df = df
        self.mapping = mapping
        self.source_path = source_path

    def run(self):
        try:
            pipeline = ValidationPipeline(self.db, self.mapping, self.source_path)
            result = pipeline.validate(self.df, progress_callback=lambda c, t: self.progress.emit(c, t))
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ImportPage(QWidget):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.sheets = None
        self.current_df = None
        self.mapping = None
        self.source_path = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("データインポート")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        # File selection
        file_group = QGroupBox("ファイル選択")
        file_layout = QHBoxLayout(file_group)

        self.file_label = QLabel("ファイルが選択されていません")
        self.file_label.setStyleSheet("color: #7f8c8d;")
        file_layout.addWidget(self.file_label, 1)

        browse_btn = QPushButton("ファイルを選択")
        browse_btn.setStyleSheet("padding: 8px 16px;")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        layout.addWidget(file_group)

        # Sheet selection
        sheet_group = QGroupBox("シート選択")
        sheet_layout = QHBoxLayout(sheet_group)
        self.sheet_combo = QComboBox()
        self.sheet_combo.currentIndexChanged.connect(self._on_sheet_changed)
        sheet_layout.addWidget(self.sheet_combo, 1)
        self.sheet_info_label = QLabel("")
        sheet_layout.addWidget(self.sheet_info_label)
        layout.addWidget(sheet_group)

        # Column mapping
        mapping_group = QGroupBox("列マッピング")
        mapping_layout = QFormLayout(mapping_group)

        self.name_combo = QComboBox()
        mapping_layout.addRow("氏名列:", self.name_combo)
        self.date_combo = QComboBox()
        mapping_layout.addRow("没年月日列:", self.date_combo)
        self.buddhist_combo = QComboBox()
        mapping_layout.addRow("法名列:", self.buddhist_combo)
        layout.addWidget(mapping_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.import_btn = QPushButton("インポート実行")
        self.import_btn.setStyleSheet("background: #27ae60; color: white; padding: 10px 24px; font-size: 14px;")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._run_import)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

        # Results area
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("font-size: 13px; padding: 8px;")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        layout.addStretch()

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "データファイルを選択",
            "", "Excel/CSV (*.xlsx *.xls *.csv);;全てのファイル (*)",
        )
        if not path:
            return
        self.source_path = path
        self.file_label.setText(path)

        try:
            self.sheets = read_file(Path(path))
            infos = get_sheet_info(self.sheets)

            self.sheet_combo.clear()
            for info in infos:
                self.sheet_combo.addItem(f"{info.name} ({info.row_count}行)", info.name)

            if infos:
                self._on_sheet_changed(0)
                self.import_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "読込エラー", f"ファイルの読み込みに失敗しました:\n{e}")

    def _on_sheet_changed(self, index: int):
        if self.sheets is None or index < 0:
            return
        sheet_name = self.sheet_combo.currentData()
        if sheet_name is None:
            return
        self.current_df = self.sheets[sheet_name]
        columns = list(self.current_df.columns)

        # Update mapping combos
        for combo in [self.name_combo, self.date_combo, self.buddhist_combo]:
            combo.clear()
            combo.addItem("（自動検出）", None)
            for col in columns:
                combo.addItem(col, col)

        # Auto-detect and pre-select
        mapping = auto_detect_mapping(columns)
        self._select_combo(self.name_combo, mapping.name_col)
        self._select_combo(self.date_combo, mapping.death_date_col)
        self._select_combo(self.buddhist_combo, mapping.buddhist_name_col)

        self.sheet_info_label.setText(f"{len(columns)}列 × {len(self.current_df)}行")

    def _select_combo(self, combo: QComboBox, value: str | None):
        if value is None:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _build_mapping(self) -> ColumnMapping:
        columns = list(self.current_df.columns)
        base = auto_detect_mapping(columns)

        # Override with user selections
        name_sel = self.name_combo.currentData()
        if name_sel:
            base.name_col = name_sel
        date_sel = self.date_combo.currentData()
        if date_sel:
            base.death_date_col = date_sel
        buddhist_sel = self.buddhist_combo.currentData()
        if buddhist_sel:
            base.buddhist_name_col = buddhist_sel

        # Rebuild extra cols
        used = {base.name_col, base.death_date_col, base.buddhist_name_col,
                base.era_col, base.year_col, base.month_col, base.day_col}
        base.extra_cols = [c for c in columns if c not in used]
        return base

    def _run_import(self):
        if self.current_df is None:
            return

        mapping = self._build_mapping()
        if not mapping.name_col:
            QMessageBox.warning(self, "マッピングエラー", "氏名列を選択してください。")
            return
        if not mapping.death_date_col and not mapping.uses_split_date:
            QMessageBox.warning(self, "マッピングエラー", "没年月日列を選択してください。")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.current_df))
        self.import_btn.setEnabled(False)

        self._worker = ImportWorker(self.db, self.current_df, mapping, self.source_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_import_finished)
        self._worker.error.connect(self._on_import_error)
        self._worker.start()

    def _on_progress(self, current, total):
        self.progress_bar.setValue(current)

    def _on_import_finished(self, result: ValidationResult):
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(True)

        # Handle duplicates
        for validated, existing_id in result.duplicate_rows:
            reply = QMessageBox.question(
                self, "重複データ",
                f"「{validated.name}」({validated.era_display}) は既に登録されています。\n"
                "どうしますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Ignore,
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Update existing
                self.db.update_person(existing_id, name=validated.name,
                                      death_date=validated.death_date, attributes=validated.attributes)
            elif reply == QMessageBox.StandardButton.No:
                # Add as new
                result.valid_rows.append(validated)
            # Ignore = skip

        # Import valid rows
        count = import_validated_rows(self.db, result.valid_rows)

        # Show results
        msg_parts = [f"インポート完了: {count}件を追加しました。"]
        if result.error_rows:
            msg_parts.append(f"エラー: {len(result.error_rows)}件")
        if result.duplicate_rows:
            msg_parts.append(f"重複: {len(result.duplicate_rows)}件")

        self.result_label.setText("\n".join(msg_parts))
        self.result_label.setStyleSheet("color: #27ae60; font-size: 13px; padding: 8px;")

        # Offer to export errors
        if result.error_rows:
            reply = QMessageBox.question(
                self, "エラー行の出力",
                f"{len(result.error_rows)}件のエラー行があります。\n"
                "Excelファイルに出力しますか？",
            )
            if reply == QMessageBox.Yes:
                path, _ = QFileDialog.getSaveFileName(
                    self, "エラー行を保存", "errors.xlsx", "Excel (*.xlsx)",
                )
                if path:
                    export_error_rows(result.error_rows, Path(path))

    def _on_import_error(self, error_msg: str):
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(True)
        self.result_label.setText(f"インポートエラー: {error_msg}")
        self.result_label.setStyleSheet("color: #e74c3c; font-size: 13px; padding: 8px;")
