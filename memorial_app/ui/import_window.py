"""Data import page - Excel/CSV file import with multi-step validation and user checkpoints."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QMessageBox, QGroupBox, QFormLayout, QHeaderView, QStackedWidget,
    QFrame, QSizePolicy, QAbstractItemView, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, QThread, Signal

from memorial_app.database.db_manager import DatabaseManager
from memorial_app.importer.excel_importer import read_file, get_sheet_info, auto_detect_mapping, ColumnMapping
from memorial_app.importer.validation_pipeline import (
    ValidationPipeline, ValidationResult, ValidatedRow, ErrorRow,
    import_validated_rows, export_error_rows,
)
from memorial_app.core.era_converter import format_date_era


class ImportWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(object)
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
    """Multi-step import wizard with checkpoints at each stage.

    Steps:
        1. File selection + sheet selection
        2. Column mapping
        3. Data preview
        4. Validation
        5. Import confirmation
        6. Result
    """

    STEP_NAMES = [
        "ステップ 1/6: ファイル・シート選択",
        "ステップ 2/6: 列マッピング",
        "ステップ 3/6: データプレビュー",
        "ステップ 4/6: データ検証",
        "ステップ 5/6: インポート確認",
        "ステップ 6/6: 完了",
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.sheets = None
        self.current_df = None
        self.mapping = None
        self.source_path = None
        self._worker = None
        self._validation_result = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("データインポート")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        # Step indicator
        self.step_label = QLabel("")
        self.step_label.setStyleSheet(
            "font-size: 13px; color: #3498db; font-weight: bold; "
            "padding: 8px; background: #eaf2f8; border-radius: 4px;"
        )
        layout.addWidget(self.step_label)

        # Stacked widget for wizard steps
        self.steps = QStackedWidget()
        layout.addWidget(self.steps)

        self._build_step1_file_and_sheet()
        self._build_step2_column_mapping()
        self._build_step3_data_preview()
        self._build_step4_validation()
        self._build_step5_confirm_import()
        self._build_step6_result()

        self._go_to_step(0)

    # ─── Step 1: File Selection + Sheet Selection ───

    def _build_step1_file_and_sheet(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        # File selection
        file_group = QGroupBox("ファイルを選択してください")
        file_layout = QHBoxLayout(file_group)
        self.file_label = QLabel("ファイルが選択されていません")
        self.file_label.setStyleSheet("color: #7f8c8d;")
        file_layout.addWidget(self.file_label, 1)
        browse_btn = QPushButton("ファイルを選択")
        browse_btn.setStyleSheet("padding: 8px 16px;")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        layout.addWidget(file_group)

        # Sheet selection (visible when multi-sheet)
        self.sheet_group = QGroupBox("シートを選択してください")
        sheet_layout = QVBoxLayout(self.sheet_group)

        self.sheet_hint = QLabel("このファイルには複数のシートがあります。インポートするシートを選んでください。")
        self.sheet_hint.setStyleSheet("color: #2c3e50; font-size: 12px;")
        self.sheet_hint.setWordWrap(True)
        sheet_layout.addWidget(self.sheet_hint)

        self.sheet_list = QListWidget()
        self.sheet_list.currentRowChanged.connect(self._on_sheet_selected)
        sheet_layout.addWidget(self.sheet_list)

        self.sheet_detail_label = QLabel("")
        self.sheet_detail_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        sheet_layout.addWidget(self.sheet_detail_label)

        layout.addWidget(self.sheet_group)
        self.sheet_group.setVisible(False)

        # Single-sheet info (visible when only one sheet)
        self.single_sheet_label = QLabel("")
        self.single_sheet_label.setStyleSheet(
            "color: #27ae60; font-size: 13px; padding: 8px; "
            "background: #eafaf1; border-radius: 4px;"
        )
        self.single_sheet_label.setVisible(False)
        layout.addWidget(self.single_sheet_label)

        # Navigation
        nav = QHBoxLayout()
        nav.addStretch()
        self.step1_next = QPushButton("次へ: 列マッピング →")
        self.step1_next.setStyleSheet("background: #3498db; color: white; padding: 10px 24px; font-size: 14px;")
        self.step1_next.setEnabled(False)
        self.step1_next.clicked.connect(self._step1_next)
        nav.addWidget(self.step1_next)
        layout.addLayout(nav)
        layout.addStretch()

        self.steps.addWidget(page)

    # ─── Step 2: Column Mapping ───

    def _build_step2_column_mapping(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel("列マッピングを確認してください（自動検出結果を変更できます）")
        info.setStyleSheet("font-size: 13px; color: #2c3e50; font-weight: bold;")
        layout.addWidget(info)

        self.mapping_sheet_info = QLabel("")
        self.mapping_sheet_info.setStyleSheet("color: #7f8c8d; font-size: 12px; padding: 4px;")
        layout.addWidget(self.mapping_sheet_info)

        mapping_group = QGroupBox("列マッピング")
        mapping_layout = QFormLayout(mapping_group)
        self.name_combo = QComboBox()
        mapping_layout.addRow("氏名列:", self.name_combo)
        self.date_combo = QComboBox()
        mapping_layout.addRow("没年月日列:", self.date_combo)
        self.buddhist_combo = QComboBox()
        mapping_layout.addRow("法名列:", self.buddhist_combo)
        layout.addWidget(mapping_group)

        # Column preview: show first few rows of mapped columns
        preview_group = QGroupBox("マッピング結果プレビュー（先頭5行）")
        preview_layout = QVBoxLayout(preview_group)
        self.mapping_preview_table = QTableWidget()
        self.mapping_preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mapping_preview_table.setMaximumHeight(180)
        self.mapping_preview_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.mapping_preview_table)
        layout.addWidget(preview_group)

        # Navigation
        nav = QHBoxLayout()
        back_btn = QPushButton("← 戻る")
        back_btn.setStyleSheet("padding: 8px 16px;")
        back_btn.clicked.connect(lambda: self._go_to_step(0))
        nav.addWidget(back_btn)
        nav.addStretch()
        next_btn = QPushButton("次へ: データプレビュー →")
        next_btn.setStyleSheet("background: #3498db; color: white; padding: 10px 24px; font-size: 14px;")
        next_btn.clicked.connect(self._step2_next)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step 3: Data Preview ───

    def _build_step3_data_preview(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel("インポートするデータを確認してください")
        info.setStyleSheet("font-size: 13px; color: #2c3e50; font-weight: bold;")
        layout.addWidget(info)

        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.preview_table)

        self.preview_info = QLabel("")
        self.preview_info.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(self.preview_info)

        nav = QHBoxLayout()
        back_btn = QPushButton("← 戻る")
        back_btn.setStyleSheet("padding: 8px 16px;")
        back_btn.clicked.connect(lambda: self._go_to_step(1))
        nav.addWidget(back_btn)
        nav.addStretch()
        next_btn = QPushButton("次へ: 検証実行 →")
        next_btn.setStyleSheet("background: #3498db; color: white; padding: 10px 24px; font-size: 14px;")
        next_btn.clicked.connect(self._step3_next)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step 4: Validation ───

    def _build_step4_validation(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel("データを検証中...")
        info.setStyleSheet("font-size: 13px; color: #2c3e50; font-weight: bold;")
        layout.addWidget(info)

        self.validation_progress = QProgressBar()
        layout.addWidget(self.validation_progress)

        self.validation_status = QLabel("")
        self.validation_status.setWordWrap(True)
        self.validation_status.setStyleSheet("font-size: 13px; padding: 8px;")
        layout.addWidget(self.validation_status)

        # Error table
        error_label = QLabel("エラー行:")
        error_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(error_label)
        self.error_table = QTableWidget()
        self.error_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.error_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.error_table)

        nav = QHBoxLayout()
        back_btn = QPushButton("← 戻る")
        back_btn.setStyleSheet("padding: 8px 16px;")
        back_btn.clicked.connect(lambda: self._go_to_step(2))
        nav.addWidget(back_btn)

        self.export_errors_btn = QPushButton("エラー行をExcelに出力")
        self.export_errors_btn.setStyleSheet("padding: 8px 16px;")
        self.export_errors_btn.setEnabled(False)
        self.export_errors_btn.clicked.connect(self._export_errors)
        nav.addWidget(self.export_errors_btn)

        nav.addStretch()
        self.step4_next = QPushButton("次へ: インポート確認 →")
        self.step4_next.setStyleSheet("background: #3498db; color: white; padding: 10px 24px; font-size: 14px;")
        self.step4_next.setEnabled(False)
        self.step4_next.clicked.connect(self._step4_next)
        nav.addWidget(self.step4_next)
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step 5: Confirm Import ───

    def _build_step5_confirm_import(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel("インポート内容を最終確認してください")
        info.setStyleSheet("font-size: 13px; color: #2c3e50; font-weight: bold;")
        layout.addWidget(info)

        self.confirm_summary = QLabel("")
        self.confirm_summary.setWordWrap(True)
        self.confirm_summary.setStyleSheet(
            "font-size: 14px; padding: 16px; background: #f8f9fa; "
            "border: 1px solid #dee2e6; border-radius: 4px;"
        )
        layout.addWidget(self.confirm_summary)

        # Valid rows preview
        valid_label = QLabel("インポート予定のデータ:")
        valid_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(valid_label)
        self.valid_table = QTableWidget()
        self.valid_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.valid_table.horizontalHeader().setStretchLastSection(True)
        self.valid_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.valid_table)

        nav = QHBoxLayout()
        back_btn = QPushButton("← 戻る")
        back_btn.setStyleSheet("padding: 8px 16px;")
        back_btn.clicked.connect(lambda: self._go_to_step(3))
        nav.addWidget(back_btn)
        nav.addStretch()
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.setStyleSheet("padding: 8px 16px;")
        cancel_btn.clicked.connect(lambda: self._go_to_step(0))
        nav.addWidget(cancel_btn)
        self.import_btn = QPushButton("インポート実行")
        self.import_btn.setStyleSheet(
            "background: #27ae60; color: white; padding: 10px 24px; font-size: 14px; font-weight: bold;"
        )
        self.import_btn.clicked.connect(self._execute_import)
        nav.addWidget(self.import_btn)
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step 6: Results ───

    def _build_step6_result(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.result_icon = QLabel("")
        self.result_icon.setAlignment(Qt.AlignCenter)
        self.result_icon.setStyleSheet("font-size: 48px; padding: 16px;")
        layout.addWidget(self.result_icon)

        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-size: 16px; padding: 16px;")
        layout.addWidget(self.result_label)

        layout.addStretch()

        nav = QHBoxLayout()
        nav.addStretch()
        new_import_btn = QPushButton("新しいインポートを開始")
        new_import_btn.setStyleSheet("background: #3498db; color: white; padding: 10px 24px; font-size: 14px;")
        new_import_btn.clicked.connect(self._reset)
        nav.addWidget(new_import_btn)
        nav.addStretch()
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step Navigation ───

    def _go_to_step(self, step: int):
        self.step_label.setText(self.STEP_NAMES[step])
        self.steps.setCurrentIndex(step)

    def refresh(self):
        pass

    def _reset(self):
        """Reset to step 1."""
        self.sheets = None
        self.current_df = None
        self.mapping = None
        self.source_path = None
        self._validation_result = None
        self.file_label.setText("ファイルが選択されていません")
        self.sheet_list.clear()
        self.sheet_group.setVisible(False)
        self.single_sheet_label.setVisible(False)
        self.step1_next.setEnabled(False)
        self._go_to_step(0)

    # ─── Step 1 Logic: File + Sheet Selection ───

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "データファイルを選択",
            "", "Excel/CSV (*.xlsx *.xls *.csv);;全てのファイル (*)",
        )
        if not path:
            return
        self.source_path = path
        self.file_label.setText(Path(path).name)
        self.file_label.setStyleSheet("color: #2c3e50; font-weight: bold;")

        try:
            self.sheets = read_file(Path(path))
            infos = get_sheet_info(self.sheets)

            if len(infos) == 1:
                # Single sheet: auto-select and show info
                self.sheet_group.setVisible(False)
                self.current_df = self.sheets[infos[0].name]
                self.single_sheet_label.setText(
                    f"シート「{infos[0].name}」を読み込みました（{infos[0].row_count}行 × {len(list(self.current_df.columns))}列）"
                )
                self.single_sheet_label.setVisible(True)
                self.step1_next.setEnabled(True)
            else:
                # Multi-sheet: show sheet selection
                self.single_sheet_label.setVisible(False)
                self.sheet_group.setVisible(True)
                self.sheet_list.clear()
                for info in infos:
                    cols = len(list(self.sheets[info.name].columns))
                    item = QListWidgetItem(f"{info.name}　（{info.row_count}行 × {cols}列）")
                    item.setData(Qt.UserRole, info.name)
                    self.sheet_list.addItem(item)
                self.step1_next.setEnabled(False)
                self.current_df = None

        except Exception as e:
            QMessageBox.critical(self, "読込エラー", f"ファイルの読み込みに失敗しました:\n{e}")

    def _on_sheet_selected(self, row: int):
        if row < 0 or self.sheets is None:
            return
        item = self.sheet_list.item(row)
        if item is None:
            return
        sheet_name = item.data(Qt.UserRole)
        self.current_df = self.sheets[sheet_name]
        cols = list(self.current_df.columns)
        self.sheet_detail_label.setText(
            f"選択中: {sheet_name}（{len(self.current_df)}行 × {len(cols)}列）"
        )
        self.step1_next.setEnabled(True)

    def _step1_next(self):
        if self.current_df is None:
            QMessageBox.warning(self, "選択エラー", "シートを選択してください。")
            return
        self._setup_column_mapping()
        self._go_to_step(1)

    # ─── Step 2 Logic: Column Mapping ───

    def _setup_column_mapping(self):
        """Populate column mapping combos for the selected sheet."""
        columns = list(self.current_df.columns)

        # Show sheet info
        sheet_name = ""
        if self.sheet_list.currentItem():
            sheet_name = self.sheet_list.currentItem().data(Qt.UserRole)
        elif self.sheets:
            sheet_name = list(self.sheets.keys())[0]
        self.mapping_sheet_info.setText(
            f"シート: {sheet_name}　|　{len(columns)}列 × {len(self.current_df)}行"
        )

        for combo in [self.name_combo, self.date_combo, self.buddhist_combo]:
            combo.clear()
            combo.addItem("（自動検出）", None)
            for col in columns:
                combo.addItem(col, col)

        mapping = auto_detect_mapping(columns)
        self._select_combo(self.name_combo, mapping.name_col)
        self._select_combo(self.date_combo, mapping.death_date_col)
        self._select_combo(self.buddhist_combo, mapping.buddhist_name_col)

        # Show mapping preview
        self._update_mapping_preview()
        self.name_combo.currentIndexChanged.connect(self._update_mapping_preview)
        self.date_combo.currentIndexChanged.connect(self._update_mapping_preview)
        self.buddhist_combo.currentIndexChanged.connect(self._update_mapping_preview)

    def _update_mapping_preview(self):
        """Show first 5 rows with mapped columns highlighted."""
        if self.current_df is None:
            return
        preview_df = self.current_df.head(5)
        name_col = self.name_combo.currentData()
        date_col = self.date_combo.currentData()
        buddhist_col = self.buddhist_combo.currentData()

        # Show mapped columns first, then others
        mapped = []
        labels = []
        if name_col and name_col in preview_df.columns:
            mapped.append(name_col)
            labels.append(f"氏名 [{name_col}]")
        if date_col and date_col in preview_df.columns:
            mapped.append(date_col)
            labels.append(f"没年月日 [{date_col}]")
        if buddhist_col and buddhist_col in preview_df.columns:
            mapped.append(buddhist_col)
            labels.append(f"法名 [{buddhist_col}]")

        if not mapped:
            self.mapping_preview_table.setRowCount(0)
            return

        self.mapping_preview_table.setColumnCount(len(mapped))
        self.mapping_preview_table.setHorizontalHeaderLabels(labels)
        self.mapping_preview_table.setRowCount(len(preview_df))

        for i, (_, row) in enumerate(preview_df.iterrows()):
            for j, col in enumerate(mapped):
                val = str(row.get(col, ""))
                self.mapping_preview_table.setItem(i, j, QTableWidgetItem(val))

    def _select_combo(self, combo: QComboBox, value):
        if value is None:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _build_mapping(self) -> ColumnMapping:
        columns = list(self.current_df.columns)
        base = auto_detect_mapping(columns)
        name_sel = self.name_combo.currentData()
        if name_sel:
            base.name_col = name_sel
        date_sel = self.date_combo.currentData()
        if date_sel:
            base.death_date_col = date_sel
        buddhist_sel = self.buddhist_combo.currentData()
        if buddhist_sel:
            base.buddhist_name_col = buddhist_sel
        used = {base.name_col, base.death_date_col, base.buddhist_name_col,
                base.era_col, base.year_col, base.month_col, base.day_col}
        base.extra_cols = [c for c in columns if c not in used]
        return base

    def _step2_next(self):
        if self.current_df is None:
            return
        mapping = self._build_mapping()
        if not mapping.name_col:
            QMessageBox.warning(self, "マッピングエラー", "氏名列を選択してください。")
            return
        if not mapping.death_date_col and not mapping.uses_split_date:
            QMessageBox.warning(self, "マッピングエラー", "没年月日列を選択してください。")
            return
        self.mapping = mapping
        self._populate_preview()
        self._go_to_step(2)

    # ─── Step 3 Logic: Data Preview ───

    def _populate_preview(self):
        df = self.current_df
        max_preview = 50
        preview_df = df.head(max_preview)

        cols = list(preview_df.columns)
        self.preview_table.setColumnCount(len(cols))
        self.preview_table.setHorizontalHeaderLabels(cols)
        self.preview_table.setRowCount(len(preview_df))

        for i, (_, row) in enumerate(preview_df.iterrows()):
            for j, col in enumerate(cols):
                val = str(row.get(col, ""))
                self.preview_table.setItem(i, j, QTableWidgetItem(val))

        total = len(df)
        if total > max_preview:
            self.preview_info.setText(
                f"先頭{max_preview}行を表示中（全{total}行）。全行がインポート対象です。"
            )
        else:
            self.preview_info.setText(f"全{total}行を表示中")

    def _step3_next(self):
        reply = QMessageBox.question(
            self, "検証の実行",
            f"全{len(self.current_df)}行のデータを検証します。\n"
            "日付の解析、必須項目の確認、重複チェックを行います。\n\n"
            "実行しますか？",
        )
        if reply != QMessageBox.Yes:
            return
        self._go_to_step(3)
        self._run_validation()

    # ─── Step 4 Logic: Validation ───

    def _run_validation(self):
        self.validation_progress.setMaximum(len(self.current_df))
        self.validation_progress.setValue(0)
        self.validation_status.setText("検証中...")
        self.step4_next.setEnabled(False)
        self.export_errors_btn.setEnabled(False)

        self._worker = ImportWorker(self.db, self.current_df, self.mapping, self.source_path)
        self._worker.progress.connect(lambda c, t: self.validation_progress.setValue(c))
        self._worker.finished.connect(self._on_validation_finished)
        self._worker.error.connect(self._on_validation_error)
        self._worker.start()

    def _on_validation_finished(self, result: ValidationResult):
        self._validation_result = result
        self.validation_progress.setValue(self.validation_progress.maximum())

        valid_count = len(result.valid_rows)
        error_count = len(result.error_rows)
        dup_count = len(result.duplicate_rows)

        status_parts = [
            f"検証完了:",
            f"  正常: {valid_count}件",
            f"  エラー: {error_count}件",
            f"  重複: {dup_count}件",
        ]
        color = "#27ae60" if error_count == 0 else "#e67e22"
        self.validation_status.setText("\n".join(status_parts))
        self.validation_status.setStyleSheet(f"color: {color}; font-size: 13px; padding: 8px;")

        # Populate error table
        if result.error_rows:
            self.error_table.setColumnCount(3)
            self.error_table.setHorizontalHeaderLabels(["行番号", "エラー内容", "データ"])
            self.error_table.setRowCount(len(result.error_rows))
            for i, err in enumerate(result.error_rows):
                self.error_table.setItem(i, 0, QTableWidgetItem(str(err.row_index + 2)))
                self.error_table.setItem(i, 1, QTableWidgetItem(err.error_message))
                data_str = ", ".join(f"{k}={v}" for k, v in list(err.raw_data.items())[:3])
                self.error_table.setItem(i, 2, QTableWidgetItem(data_str))
            self.export_errors_btn.setEnabled(True)
        else:
            self.error_table.setRowCount(0)
            self.error_table.setColumnCount(0)

        self.step4_next.setEnabled(valid_count > 0 or dup_count > 0)

    def _on_validation_error(self, error_msg: str):
        self.validation_status.setText(f"検証エラー: {error_msg}")
        self.validation_status.setStyleSheet("color: #e74c3c; font-size: 13px; padding: 8px;")

    def _export_errors(self):
        if not self._validation_result or not self._validation_result.error_rows:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "エラー行を保存", "errors.xlsx", "Excel (*.xlsx)",
        )
        if path:
            export_error_rows(self._validation_result.error_rows, Path(path))
            QMessageBox.information(self, "完了", f"エラー行を保存しました:\n{path}")

    def _step4_next(self):
        self._handle_duplicates()
        self._populate_confirm()
        self._go_to_step(4)

    # ─── Step 5 Logic: Confirm Import ───

    def _handle_duplicates(self):
        """Ask user about each duplicate row."""
        if not self._validation_result:
            return

        for validated, existing_id in self._validation_result.duplicate_rows:
            reply = QMessageBox.question(
                self, "重複データの処理",
                f"「{validated.name}」（{validated.era_display}）は既に登録されています。\n\n"
                "「はい」→ 既存データを上書き\n"
                "「いいえ」→ 新規データとして追加\n"
                "「キャンセル」→ スキップ（インポートしない）",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.db.update_person(
                    existing_id, name=validated.name,
                    death_date=validated.death_date, attributes=validated.attributes,
                )
            elif reply == QMessageBox.StandardButton.No:
                self._validation_result.valid_rows.append(validated)
            # Cancel = skip

    def _populate_confirm(self):
        result = self._validation_result
        if not result:
            return

        valid_count = len(result.valid_rows)
        sheet_name = ""
        if self.sheet_list.currentItem():
            sheet_name = self.sheet_list.currentItem().data(Qt.UserRole)
        elif self.sheets:
            sheet_name = list(self.sheets.keys())[0]

        self.confirm_summary.setText(
            f"インポート対象: {valid_count}件\n"
            f"ファイル: {Path(self.source_path).name}\n"
            f"シート: {sheet_name}\n\n"
            f"「インポート実行」を押すとデータベースに追加されます。"
        )

        # Show valid rows in table
        if result.valid_rows:
            self.valid_table.setColumnCount(3)
            self.valid_table.setHorizontalHeaderLabels(["氏名", "没年月日", "属性数"])
            self.valid_table.setRowCount(min(len(result.valid_rows), 100))
            for i, row in enumerate(result.valid_rows[:100]):
                self.valid_table.setItem(i, 0, QTableWidgetItem(row.name))
                self.valid_table.setItem(i, 1, QTableWidgetItem(row.era_display))
                self.valid_table.setItem(i, 2, QTableWidgetItem(str(len(row.attributes))))

    def _execute_import(self):
        reply = QMessageBox.question(
            self, "最終確認",
            f"{len(self._validation_result.valid_rows)}件のデータをインポートします。\n\n"
            "実行しますか？",
        )
        if reply != QMessageBox.Yes:
            return

        try:
            count = import_validated_rows(self.db, self._validation_result.valid_rows)
            self.result_icon.setText("OK")
            self.result_icon.setStyleSheet("font-size: 48px; padding: 16px; color: #27ae60;")
            self.result_label.setText(
                f"インポートが完了しました\n\n"
                f"{count}件のデータを追加しました。"
            )
            self.result_label.setStyleSheet("color: #27ae60; font-size: 16px; padding: 16px;")
        except Exception as e:
            self.result_icon.setText("NG")
            self.result_icon.setStyleSheet("font-size: 48px; padding: 16px; color: #e74c3c;")
            self.result_label.setText(f"インポートに失敗しました\n\n{e}")
            self.result_label.setStyleSheet("color: #e74c3c; font-size: 16px; padding: 16px;")

        self._go_to_step(5)
