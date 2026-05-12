"""Data import page - Excel/CSV file import with multi-step validation,
in-UI error correction and a checkpoint at every stage.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QComboBox,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QGroupBox,
    QFormLayout,
    QHeaderView,
    QStackedWidget,
    QFrame,
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QDialog,
    QDialogButtonBox,
    QButtonGroup,
    QRadioButton,
)
from PySide6.QtCore import Qt, QThread, Signal

from memorial_app.database.db_manager import DatabaseManager, DatabaseError
from memorial_app.importer.excel_importer import (
    read_file,
    get_sheet_info,
    auto_detect_mapping,
    ColumnMapping,
    FileReadError,
)
from memorial_app.importer.validation_pipeline import (
    ValidationPipeline,
    ValidationResult,
    ValidatedRow,
    ErrorRow,
    import_validated_rows,
    export_error_rows,
)


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
            result = pipeline.validate(
                self.df, progress_callback=lambda c, t: self.progress.emit(c, t)
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DuplicateResolutionDialog(QDialog):
    """Lets the user resolve every duplicate-against-DB row at once, with the
    decisions applied atomically only when the user runs the import. Nothing
    is written to the DB from this dialog itself.
    """

    def __init__(self, duplicate_rows: list[ValidatedRow], parent=None):
        super().__init__(parent)
        self.setWindowTitle("重複データの処理")
        self.setMinimumWidth(700)
        self.setMinimumHeight(450)
        self._duplicates = duplicate_rows
        self._choices: dict[int, str] = {
            i: "overwrite" for i in range(len(duplicate_rows))
        }

        layout = QVBoxLayout(self)
        info = QLabel(
            f"既存データと一致する {len(duplicate_rows)} 件のレコードがあります。\n"
            "各行について処理方法を選んでください。"
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 13px; color: #2c3e50; padding: 4px;")
        layout.addWidget(info)

        # Bulk actions
        bulk = QHBoxLayout()
        bulk.addWidget(QLabel("一括設定:"))
        for label, action in (
            ("全て上書き", "overwrite"),
            ("全て新規追加", "insert"),
            ("全てスキップ", "skip"),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked=False, a=action: self._set_all(a))
            bulk.addWidget(btn)
        bulk.addStretch()
        layout.addLayout(bulk)

        # Per-row choices
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["氏名", "没年月日", "上書き", "新規追加", "スキップ"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setRowCount(len(duplicate_rows))
        self._row_groups: list[QButtonGroup] = []

        for i, row in enumerate(duplicate_rows):
            self.table.setItem(i, 0, QTableWidgetItem(row.name))
            self.table.setItem(i, 1, QTableWidgetItem(row.era_display))
            group = QButtonGroup(self)
            for col, action in ((2, "overwrite"), (3, "insert"), (4, "skip")):
                rb = QRadioButton()
                rb.setChecked(action == "overwrite")
                rb.toggled.connect(
                    lambda checked, idx=i, a=action: self._on_choice(idx, a, checked)
                )
                group.addButton(rb)
                container = QWidget()
                lay = QHBoxLayout(container)
                lay.setContentsMargins(0, 0, 0, 0)
                lay.addStretch()
                lay.addWidget(rb)
                lay.addStretch()
                self.table.setCellWidget(i, col, container)
            self._row_groups.append(group)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("確定")
        buttons.button(QDialogButtonBox.Cancel).setText("キャンセル")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all(self, action: str):
        col_for_action = {"overwrite": 2, "insert": 3, "skip": 4}[action]
        for i in range(self.table.rowCount()):
            container = self.table.cellWidget(i, col_for_action)
            rb = container.findChild(QRadioButton)
            if rb:
                rb.setChecked(True)
            self._choices[i] = action

    def _on_choice(self, idx: int, action: str, checked: bool):
        if checked:
            self._choices[idx] = action

    def apply_to(self, duplicate_rows: list[ValidatedRow]):
        """Stamp the user's choices onto the ValidatedRow objects in-place."""
        for i, row in enumerate(duplicate_rows):
            row.duplicate_action = self._choices.get(i, "overwrite")


class ImportPage(QWidget):
    """Multi-step import wizard with checkpoints at each stage.

    Steps:
        1. File selection + sheet selection
        2. Column mapping (name, date, buddhist_name)
        3. Extra column remapping (map to existing DB columns or import as-is)
        4. Data preview
        5. Validation + inline error correction
        6. Import confirmation (with duplicate resolution)
        7. Result
    """

    STEP_NAMES = [
        "ステップ 1/7: ファイル・シート選択",
        "ステップ 2/7: 基本列マッピング",
        "ステップ 3/7: 追加列の統合設定",
        "ステップ 4/7: データプレビュー",
        "ステップ 5/7: データ検証・修正",
        "ステップ 6/7: インポート確認",
        "ステップ 7/7: 完了",
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.sheets: dict | None = None
        self.current_df = None
        self.mapping: ColumnMapping | None = None
        self.source_path: str | None = None
        self._worker: ImportWorker | None = None
        self._validation_result: ValidationResult | None = None
        self._remap_combos: dict[str, QComboBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("データインポート")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        self.step_label = QLabel("")
        self.step_label.setStyleSheet(
            "font-size: 13px; color: #3498db; font-weight: bold; "
            "padding: 8px; background: #eaf2f8; border-radius: 4px;"
        )
        layout.addWidget(self.step_label)

        self.steps = QStackedWidget()
        layout.addWidget(self.steps)

        self._build_step1_file_and_sheet()
        self._build_step2_column_mapping()
        self._build_step3_column_remap()
        self._build_step4_data_preview()
        self._build_step5_validation()
        self._build_step6_confirm_import()
        self._build_step7_result()

        self._go_to_step(0)

    # ─── Step 1: File Selection + Sheet Selection ───

    def _build_step1_file_and_sheet(self):
        page = QWidget()
        layout = QVBoxLayout(page)

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

        self.sheet_group = QGroupBox("シートを選択してください")
        sheet_layout = QVBoxLayout(self.sheet_group)
        self.sheet_hint = QLabel(
            "このファイルには複数のシートがあります。インポートするシートを選んでください。"
        )
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

        self.single_sheet_label = QLabel("")
        self.single_sheet_label.setStyleSheet(
            "color: #27ae60; font-size: 13px; padding: 8px; "
            "background: #eafaf1; border-radius: 4px;"
        )
        self.single_sheet_label.setVisible(False)
        layout.addWidget(self.single_sheet_label)

        nav = QHBoxLayout()
        nav.addStretch()
        self.step1_next = QPushButton("次へ: 列マッピング →")
        self.step1_next.setStyleSheet(
            "background: #3498db; color: white; padding: 10px 24px; font-size: 14px;"
        )
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

        info = QLabel(
            "基本列マッピングを確認してください（自動検出結果を変更できます）"
        )
        info.setStyleSheet("font-size: 13px; color: #2c3e50; font-weight: bold;")
        layout.addWidget(info)

        self.mapping_sheet_info = QLabel("")
        self.mapping_sheet_info.setStyleSheet(
            "color: #7f8c8d; font-size: 12px; padding: 4px;"
        )
        layout.addWidget(self.mapping_sheet_info)

        mapping_group = QGroupBox("基本列マッピング")
        mapping_layout = QFormLayout(mapping_group)
        self.name_combo = QComboBox()
        mapping_layout.addRow("氏名列:", self.name_combo)
        self.date_combo = QComboBox()
        mapping_layout.addRow("没年月日列:", self.date_combo)
        self.buddhist_combo = QComboBox()
        mapping_layout.addRow("法名列:", self.buddhist_combo)
        layout.addWidget(mapping_group)

        preview_group = QGroupBox("マッピング結果プレビュー（先頭5行）")
        preview_layout = QVBoxLayout(preview_group)
        self.mapping_preview_table = QTableWidget()
        self.mapping_preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mapping_preview_table.setMaximumHeight(180)
        self.mapping_preview_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.mapping_preview_table)
        layout.addWidget(preview_group)

        nav = QHBoxLayout()
        back_btn = QPushButton("← 戻る")
        back_btn.setStyleSheet("padding: 8px 16px;")
        back_btn.clicked.connect(lambda: self._go_to_step(0))
        nav.addWidget(back_btn)
        nav.addStretch()
        self.step2_next = QPushButton("次へ →")
        self.step2_next.setStyleSheet(
            "background: #3498db; color: white; padding: 10px 24px; font-size: 14px;"
        )
        self.step2_next.clicked.connect(self._step2_next)
        nav.addWidget(self.step2_next)
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step 3: Extra Column Remapping ───

    def _build_step3_column_remap(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.remap_info = QLabel("")
        self.remap_info.setStyleSheet(
            "font-size: 13px; color: #2c3e50; font-weight: bold;"
        )
        self.remap_info.setWordWrap(True)
        layout.addWidget(self.remap_info)

        self.remap_hint = QLabel("")
        self.remap_hint.setStyleSheet(
            "color: #7f8c8d; font-size: 12px; padding: 8px; "
            "background: #fef9e7; border: 1px solid #f9e79f; border-radius: 4px;"
        )
        self.remap_hint.setWordWrap(True)
        layout.addWidget(self.remap_hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.remap_container = QWidget()
        self.remap_form_layout = QFormLayout(self.remap_container)
        self.remap_form_layout.setSpacing(8)
        scroll.setWidget(self.remap_container)
        layout.addWidget(scroll)

        self.remap_preview_group = QGroupBox("データサンプル（先頭3行）")
        remap_preview_layout = QVBoxLayout(self.remap_preview_group)
        self.remap_preview_table = QTableWidget()
        self.remap_preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.remap_preview_table.setMaximumHeight(120)
        self.remap_preview_table.horizontalHeader().setStretchLastSection(True)
        remap_preview_layout.addWidget(self.remap_preview_table)
        layout.addWidget(self.remap_preview_group)

        nav = QHBoxLayout()
        back_btn = QPushButton("← 戻る")
        back_btn.setStyleSheet("padding: 8px 16px;")
        back_btn.clicked.connect(lambda: self._go_to_step(1))
        nav.addWidget(back_btn)
        nav.addStretch()
        next_btn = QPushButton("次へ: データプレビュー →")
        next_btn.setStyleSheet(
            "background: #3498db; color: white; padding: 10px 24px; font-size: 14px;"
        )
        next_btn.clicked.connect(self._step3_next)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step 4: Data Preview ───

    def _build_step4_data_preview(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel("インポートするデータを確認してください")
        info.setStyleSheet("font-size: 13px; color: #2c3e50; font-weight: bold;")
        layout.addWidget(info)

        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        layout.addWidget(self.preview_table)

        self.preview_info = QLabel("")
        self.preview_info.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(self.preview_info)

        nav = QHBoxLayout()
        back_btn = QPushButton("← 戻る")
        back_btn.setStyleSheet("padding: 8px 16px;")
        back_btn.clicked.connect(self._step4_back)
        nav.addWidget(back_btn)
        nav.addStretch()
        next_btn = QPushButton("次へ: 検証実行 →")
        next_btn.setStyleSheet(
            "background: #3498db; color: white; padding: 10px 24px; font-size: 14px;"
        )
        next_btn.clicked.connect(self._step4_next)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step 5: Validation + In-UI Error Editor ───

    def _build_step5_validation(self):
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

        error_label = QLabel(
            "エラー行（セルをダブルクリックして修正できます。修正後「再検証」を押してください）:"
        )
        error_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        error_label.setWordWrap(True)
        layout.addWidget(error_label)

        self.error_table = QTableWidget()
        self.error_table.horizontalHeader().setStretchLastSection(True)
        self.error_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # User can edit raw cells inline; the error column stays read-only.
        self.error_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        layout.addWidget(self.error_table)

        error_actions = QHBoxLayout()
        self.revalidate_btn = QPushButton("修正後に再検証")
        self.revalidate_btn.setStyleSheet(
            "background: #16a085; color: white; padding: 6px 14px;"
        )
        self.revalidate_btn.clicked.connect(self._revalidate_errors)
        self.revalidate_btn.setEnabled(False)
        error_actions.addWidget(self.revalidate_btn)

        self.export_errors_btn = QPushButton("エラー行をExcelに出力")
        self.export_errors_btn.setStyleSheet("padding: 6px 14px;")
        self.export_errors_btn.setEnabled(False)
        self.export_errors_btn.clicked.connect(self._export_errors)
        error_actions.addWidget(self.export_errors_btn)

        self.delete_errors_btn = QPushButton("選択行を破棄")
        self.delete_errors_btn.setStyleSheet("padding: 6px 14px;")
        self.delete_errors_btn.setEnabled(False)
        self.delete_errors_btn.clicked.connect(self._delete_selected_errors)
        error_actions.addWidget(self.delete_errors_btn)

        error_actions.addStretch()
        layout.addLayout(error_actions)

        nav = QHBoxLayout()
        back_btn = QPushButton("← 戻る")
        back_btn.setStyleSheet("padding: 8px 16px;")
        back_btn.clicked.connect(lambda: self._go_to_step(3))
        nav.addWidget(back_btn)
        nav.addStretch()
        self.step5_next = QPushButton("次へ: インポート確認 →")
        self.step5_next.setStyleSheet(
            "background: #3498db; color: white; padding: 10px 24px; font-size: 14px;"
        )
        self.step5_next.setEnabled(False)
        self.step5_next.clicked.connect(self._step5_next)
        nav.addWidget(self.step5_next)
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step 6: Confirm Import ───

    def _build_step6_confirm_import(self):
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

        # Duplicate resolution button (visible when duplicates exist)
        self.dup_btn = QPushButton("重複データの処理を確認")
        self.dup_btn.setStyleSheet(
            "background: #f39c12; color: white; padding: 8px 16px;"
        )
        self.dup_btn.clicked.connect(self._open_duplicate_dialog)
        self.dup_btn.setVisible(False)
        layout.addWidget(self.dup_btn)

        valid_label = QLabel("インポート予定のデータ:")
        valid_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(valid_label)
        self.valid_table = QTableWidget()
        self.valid_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.valid_table.horizontalHeader().setStretchLastSection(True)
        self.valid_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        layout.addWidget(self.valid_table)

        nav = QHBoxLayout()
        back_btn = QPushButton("← 戻る")
        back_btn.setStyleSheet("padding: 8px 16px;")
        back_btn.clicked.connect(lambda: self._go_to_step(4))
        nav.addWidget(back_btn)
        nav.addStretch()
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.setStyleSheet("padding: 8px 16px;")
        cancel_btn.clicked.connect(lambda: self._go_to_step(0))
        nav.addWidget(cancel_btn)
        self.import_btn = QPushButton("インポート実行")
        self.import_btn.setStyleSheet(
            "background: #27ae60; color: white; padding: 10px 24px; "
            "font-size: 14px; font-weight: bold;"
        )
        self.import_btn.clicked.connect(self._execute_import)
        nav.addWidget(self.import_btn)
        layout.addLayout(nav)

        self.steps.addWidget(page)

    # ─── Step 7: Results ───

    def _build_step7_result(self):
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

        self.failures_table = QTableWidget()
        self.failures_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.failures_table.setColumnCount(2)
        self.failures_table.setHorizontalHeaderLabels(["行番号", "失敗理由"])
        self.failures_table.horizontalHeader().setStretchLastSection(True)
        self.failures_table.setVisible(False)
        layout.addWidget(self.failures_table)

        layout.addStretch()

        nav = QHBoxLayout()
        nav.addStretch()
        new_import_btn = QPushButton("新しいインポートを開始")
        new_import_btn.setStyleSheet(
            "background: #3498db; color: white; padding: 10px 24px; font-size: 14px;"
        )
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

    def _stop_worker(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        self._worker = None

    def _reset(self):
        self._stop_worker()
        self.sheets = None
        self.current_df = None
        self.mapping = None
        self.source_path = None
        self._validation_result = None
        self._remap_combos.clear()
        self.file_label.setText("ファイルが選択されていません")
        self.file_label.setStyleSheet("color: #7f8c8d;")
        self.sheet_list.clear()
        self.sheet_group.setVisible(False)
        self.single_sheet_label.setVisible(False)
        self.step1_next.setEnabled(False)
        self.failures_table.setVisible(False)
        self._go_to_step(0)

    def hideEvent(self, event):
        self._stop_worker()
        super().hideEvent(event)

    # ─── Step 1 Logic ───

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "データファイルを選択",
            "",
            "Excel/CSV (*.xlsx *.xlsm *.xls *.csv);;全てのファイル (*)",
        )
        if not path:
            return
        self.source_path = path
        self.file_label.setText(Path(path).name)
        self.file_label.setStyleSheet("color: #2c3e50; font-weight: bold;")

        try:
            self.sheets = read_file(Path(path))
        except FileReadError as e:
            QMessageBox.critical(self, "読込エラー", str(e))
            return
        except Exception as e:
            QMessageBox.critical(
                self, "読込エラー", f"ファイルの読み込みに失敗しました:\n{e}"
            )
            return

        infos = get_sheet_info(self.sheets)
        if not infos:
            QMessageBox.warning(
                self,
                "データなし",
                "ファイルに有効なデータが見つかりませんでした。\n"
                "全てのシートが空、もしくはヘッダのみです。",
            )
            self.sheets = None
            self.current_df = None
            self.step1_next.setEnabled(False)
            return

        if len(infos) == 1:
            self.sheet_group.setVisible(False)
            self.current_df = self.sheets[infos[0].name]
            self.single_sheet_label.setText(
                f"シート「{infos[0].name}」を読み込みました"
                f"（{infos[0].row_count}行 × {len(list(self.current_df.columns))}列）"
            )
            self.single_sheet_label.setVisible(True)
            self.step1_next.setEnabled(True)
        else:
            self.single_sheet_label.setVisible(False)
            self.sheet_group.setVisible(True)
            self.sheet_list.clear()
            for info in infos:
                cols = len(list(self.sheets[info.name].columns))
                item = QListWidgetItem(
                    f"{info.name}　（{info.row_count}行 × {cols}列）"
                )
                item.setData(Qt.UserRole, info.name)
                self.sheet_list.addItem(item)
            self.step1_next.setEnabled(False)
            self.current_df = None

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

    # ─── Step 2 Logic ───

    def _setup_column_mapping(self):
        columns = list(self.current_df.columns)
        sheet_name = self._get_current_sheet_name()
        self.mapping_sheet_info.setText(
            f"シート: {sheet_name}　|　{len(columns)}列 × {len(self.current_df)}行"
        )

        for combo, slot in (
            (self.name_combo, self._update_mapping_preview),
            (self.date_combo, self._update_mapping_preview),
            (self.buddhist_combo, self._update_mapping_preview),
        ):
            try:
                combo.currentIndexChanged.disconnect(slot)
            except RuntimeError:
                pass

        for combo in (self.name_combo, self.date_combo, self.buddhist_combo):
            combo.clear()
            combo.addItem("（自動検出）", None)
            for col in columns:
                combo.addItem(col, col)

        mapping = auto_detect_mapping(columns)
        self._select_combo(self.name_combo, mapping.name_col)
        self._select_combo(self.date_combo, mapping.death_date_col)
        self._select_combo(self.buddhist_combo, mapping.buddhist_name_col)

        self._update_mapping_preview()
        self.name_combo.currentIndexChanged.connect(self._update_mapping_preview)
        self.date_combo.currentIndexChanged.connect(self._update_mapping_preview)
        self.buddhist_combo.currentIndexChanged.connect(self._update_mapping_preview)

    def _update_mapping_preview(self):
        if self.current_df is None:
            return
        preview_df = self.current_df.head(5)
        name_col = self.name_combo.currentData()
        date_col = self.date_combo.currentData()
        buddhist_col = self.buddhist_combo.currentData()

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
            self.mapping_preview_table.setColumnCount(0)
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
        used = {
            base.name_col,
            base.death_date_col,
            base.buddhist_name_col,
            base.era_col,
            base.year_col,
            base.month_col,
            base.day_col,
        }
        used.discard(None)
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
            QMessageBox.warning(
                self, "マッピングエラー", "没年月日列を選択してください。"
            )
            return
        self.mapping = mapping

        try:
            existing_db_cols = self.db.get_all_column_names()
        except DatabaseError as e:
            QMessageBox.critical(self, "DBエラー", str(e))
            return

        remappable: list[str] = []
        if mapping.buddhist_name_col:
            remappable.append(mapping.buddhist_name_col)
        remappable.extend(mapping.extra_cols)

        if existing_db_cols and remappable:
            self._setup_column_remap(remappable, existing_db_cols)
            self._go_to_step(2)
        else:
            mapping.column_remap = {}
            self._populate_preview()
            self._go_to_step(3)

    # ─── Step 3 Logic ───

    def _setup_column_remap(
        self, remappable_cols: list[str], existing_db_cols: list[str]
    ):
        self.remap_info.setText(
            f"データベースには既存の属性列が {len(existing_db_cols)} 件あります。\n"
            "インポートファイルの各列を、既存の列に統合するか、新規列として追加するか選んでください。"
        )
        self.remap_hint.setText(
            "同じ種類のデータで列名だけ異なる場合（例: ファイルの「戒名」→ DBの「法名」）、\n"
            "既存の列にマッピングすることで、データの重複を避けられます。\n"
            "「そのまま（新規列）」を選ぶと、ファイルの列名がそのまま使われます。"
        )

        while self.remap_form_layout.rowCount() > 0:
            self.remap_form_layout.removeRow(0)
        self._remap_combos.clear()

        for excel_col in remappable_cols:
            combo = QComboBox()
            combo.addItem(f"そのまま（{excel_col}）", excel_col)
            for db_col in existing_db_cols:
                if db_col == excel_col:
                    combo.addItem(f"既存列: {db_col}（同名）", db_col)
                else:
                    combo.addItem(f"既存列: {db_col}", db_col)
            if excel_col in existing_db_cols:
                for i in range(combo.count()):
                    if combo.itemData(i) == excel_col and i > 0:
                        combo.setCurrentIndex(i)
                        break
            label = QLabel(f"<b>{excel_col}</b>　→")
            self.remap_form_layout.addRow(label, combo)
            self._remap_combos[excel_col] = combo

        if self.current_df is not None:
            preview_df = self.current_df.head(3)
            show_cols = [c for c in remappable_cols if c in preview_df.columns]
            if show_cols:
                self.remap_preview_table.setColumnCount(len(show_cols))
                self.remap_preview_table.setHorizontalHeaderLabels(show_cols)
                self.remap_preview_table.setRowCount(len(preview_df))
                for i, (_, row) in enumerate(preview_df.iterrows()):
                    for j, col in enumerate(show_cols):
                        val = str(row.get(col, ""))
                        self.remap_preview_table.setItem(i, j, QTableWidgetItem(val))
                self.remap_preview_group.setVisible(True)
            else:
                self.remap_preview_group.setVisible(False)

    def _step3_next(self):
        # Each column ends up writing to (remap_target or col_itself); detect
        # any two sources that converge on the same target — including the
        # case where one source kept its name as-is.
        final_targets: dict[str, list[str]] = {}
        for excel_col, combo in self._remap_combos.items():
            target = combo.currentData() or excel_col
            final_targets.setdefault(target, []).append(excel_col)
        conflicts = {t: srcs for t, srcs in final_targets.items() if len(srcs) > 1}

        if conflicts:
            msgs = [f"  「{t}」← {', '.join(srcs)}" for t, srcs in conflicts.items()]
            QMessageBox.warning(
                self,
                "マッピング競合",
                "複数の列が同じ最終列名にマッピングされています:\n\n"
                + "\n".join(msgs)
                + "\n\n各最終列にはファイルの1列のみマッピングできます。",
            )
            return

        remap = {
            excel_col: (combo.currentData() or excel_col)
            for excel_col, combo in self._remap_combos.items()
            if (combo.currentData() or excel_col) != excel_col
        }
        self.mapping.column_remap = remap

        if remap:
            lines = [f"  {src} → {dst}" for src, dst in remap.items()]
            reply = QMessageBox.question(
                self,
                "列の統合確認",
                "以下の列名変換を適用してインポートします:\n\n"
                + "\n".join(lines)
                + "\n\nよろしいですか？",
            )
            if reply != QMessageBox.Yes:
                return

        self._populate_preview()
        self._go_to_step(3)

    # ─── Step 4 Logic ───

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

    def _step4_back(self):
        # Step 3 may have been skipped if remap was not needed; go back to
        # whichever step actually owns the data prior to preview.
        try:
            db_cols = self.db.get_all_column_names()
        except DatabaseError:
            db_cols = []
        has_remap_step = bool(db_cols) and bool(
            (self.mapping.extra_cols if self.mapping else [])
            or (self.mapping.buddhist_name_col if self.mapping else None)
        )
        self._go_to_step(2 if has_remap_step else 1)

    def _step4_next(self):
        reply = QMessageBox.question(
            self,
            "検証の実行",
            f"全{len(self.current_df)}行のデータを検証します。\n"
            "日付の解析、必須項目の確認、重複チェックを行います。\n\n"
            "実行しますか？",
        )
        if reply != QMessageBox.Yes:
            return
        self._go_to_step(4)
        self._run_validation()

    # ─── Step 5 Logic ───

    def _run_validation(self):
        self.validation_progress.setMaximum(max(1, len(self.current_df)))
        self.validation_progress.setValue(0)
        self.validation_status.setText("検証中...")
        self.step5_next.setEnabled(False)
        self.export_errors_btn.setEnabled(False)
        self.revalidate_btn.setEnabled(False)
        self.delete_errors_btn.setEnabled(False)

        self._worker = ImportWorker(
            self.db, self.current_df, self.mapping, self.source_path
        )
        self._worker.progress.connect(
            lambda c, _t: self.validation_progress.setValue(c)
        )
        self._worker.finished.connect(self._on_validation_finished)
        self._worker.error.connect(self._on_validation_error)
        self._worker.start()

    def _on_validation_finished(self, result: ValidationResult):
        self._worker = None
        self._validation_result = result
        self.validation_progress.setValue(self.validation_progress.maximum())
        self._render_validation_summary()
        self._render_error_table()

    def _on_validation_error(self, error_msg: str):
        self._worker = None
        self.validation_status.setText(f"検証エラー: {error_msg}")
        self.validation_status.setStyleSheet(
            "color: #e74c3c; font-size: 13px; padding: 8px;"
        )

    def _render_validation_summary(self):
        result = self._validation_result
        if result is None:
            return
        valid_count = len(result.valid_rows)
        error_count = len(result.error_rows)
        dup_count = len(result.duplicate_rows)
        color = "#27ae60" if error_count == 0 else "#e67e22"
        self.validation_status.setText(
            "検証完了:\n"
            f"  正常: {valid_count}件\n"
            f"  エラー: {error_count}件（修正または破棄してください）\n"
            f"  重複: {dup_count}件（次の画面で処理方法を選択できます）"
        )
        self.validation_status.setStyleSheet(
            f"color: {color}; font-size: 13px; padding: 8px;"
        )
        # The "next" button is enabled even with errors — the user can choose
        # to import only the rows that are valid and discard the rest.
        self.step5_next.setEnabled((valid_count + dup_count) > 0)

    def _render_error_table(self):
        result = self._validation_result
        if result is None:
            return
        errors = result.error_rows
        if not errors:
            self.error_table.setRowCount(0)
            self.error_table.setColumnCount(0)
            self.revalidate_btn.setEnabled(False)
            self.export_errors_btn.setEnabled(False)
            self.delete_errors_btn.setEnabled(False)
            return

        # Header: original row number, every raw column from the source, and
        # the human-readable error message at the end (read-only).
        all_cols = list(self.current_df.columns)
        headers = ["元の行"] + all_cols + ["エラー内容"]
        self.error_table.setColumnCount(len(headers))
        self.error_table.setHorizontalHeaderLabels(headers)
        self.error_table.setRowCount(len(errors))

        for i, err in enumerate(errors):
            row_item = QTableWidgetItem(str(err.row_index + 2))
            row_item.setFlags(row_item.flags() & ~Qt.ItemIsEditable)
            self.error_table.setItem(i, 0, row_item)
            for j, col in enumerate(all_cols, start=1):
                item = QTableWidgetItem(str(err.raw_data.get(col, "")))
                self.error_table.setItem(i, j, item)
            err_item = QTableWidgetItem(err.error_message)
            err_item.setFlags(err_item.flags() & ~Qt.ItemIsEditable)
            err_item.setForeground(Qt.red)
            self.error_table.setItem(i, len(headers) - 1, err_item)
        self.error_table.resizeColumnsToContents()

        self.revalidate_btn.setEnabled(True)
        self.export_errors_btn.setEnabled(True)
        self.delete_errors_btn.setEnabled(True)

    def _revalidate_errors(self):
        """Run the pipeline on each (possibly edited) error row again and
        promote any rows that now validate."""
        result = self._validation_result
        if result is None or not result.error_rows:
            return

        all_cols = list(self.current_df.columns)
        pipeline = ValidationPipeline(self.db, self.mapping, self.source_path)

        new_errors: list[ErrorRow] = []
        promoted_valid = 0
        promoted_dup = 0

        for i, err in enumerate(result.error_rows):
            row_data: dict[str, str] = {}
            for j, col in enumerate(all_cols, start=1):
                item = self.error_table.item(i, j)
                row_data[col] = item.text() if item else ""
            outcome = pipeline.validate_one(row_data, err.row_index)
            if isinstance(outcome, ErrorRow):
                new_errors.append(outcome)
            else:
                # ValidatedRow — route to dup or valid bucket
                if outcome.duplicate_of is not None:
                    result.duplicate_rows.append(outcome)
                    promoted_dup += 1
                else:
                    result.valid_rows.append(outcome)
                    promoted_valid += 1

        result.error_rows = new_errors
        self._render_validation_summary()
        self._render_error_table()
        QMessageBox.information(
            self,
            "再検証完了",
            f"正常に修正: {promoted_valid}件\n"
            f"重複として検出: {promoted_dup}件\n"
            f"未解決のエラー: {len(new_errors)}件",
        )

    def _delete_selected_errors(self):
        result = self._validation_result
        if result is None or not result.error_rows:
            return
        rows = sorted({idx.row() for idx in self.error_table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "情報", "削除する行を選択してください。")
            return
        reply = QMessageBox.question(
            self,
            "破棄確認",
            f"選択された{len(rows)}件のエラー行をインポートから除外します。\n続行しますか？",
        )
        if reply != QMessageBox.Yes:
            return
        for r in rows:
            if 0 <= r < len(result.error_rows):
                result.error_rows.pop(r)
        self._render_validation_summary()
        self._render_error_table()

    def _export_errors(self):
        if not self._validation_result or not self._validation_result.error_rows:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "エラー行を保存", "errors.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            export_error_rows(self._validation_result.error_rows, Path(path))
            QMessageBox.information(self, "完了", f"エラー行を保存しました:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"エクスポートに失敗しました:\n{e}")

    def _step5_next(self):
        self._populate_confirm()
        self._go_to_step(5)

    # ─── Step 6 Logic ───

    def _open_duplicate_dialog(self):
        if not self._validation_result or not self._validation_result.duplicate_rows:
            return
        dlg = DuplicateResolutionDialog(
            self._validation_result.duplicate_rows, parent=self
        )
        if dlg.exec():
            dlg.apply_to(self._validation_result.duplicate_rows)
            self._populate_confirm()

    def _populate_confirm(self):
        result = self._validation_result
        if not result:
            return

        # Default duplicate action to "overwrite" so the summary is accurate
        # even if the user hasn't opened the resolution dialog yet.
        for row in result.duplicate_rows:
            if row.duplicate_action is None:
                row.duplicate_action = "overwrite"

        sheet_name = self._get_current_sheet_name()
        remap_text = ""
        if self.mapping and self.mapping.column_remap:
            lines = [f"  {src} → {dst}" for src, dst in self.mapping.column_remap.items()]
            remap_text = "\n列名変換:\n" + "\n".join(lines) + "\n"

        # Compose count breakdown for the dup rows
        to_overwrite = sum(
            1 for r in result.duplicate_rows if r.duplicate_action == "overwrite"
        )
        to_insert_again = sum(
            1 for r in result.duplicate_rows if r.duplicate_action == "insert"
        )
        to_skip = sum(
            1 for r in result.duplicate_rows if r.duplicate_action == "skip"
        )

        dup_summary = ""
        if result.duplicate_rows:
            dup_summary = (
                f"\n重複データの処理:\n"
                f"  上書き: {to_overwrite}件\n"
                f"  新規追加: {to_insert_again}件\n"
                f"  スキップ: {to_skip}件\n"
            )
            self.dup_btn.setVisible(True)
            self.dup_btn.setText(
                f"重複データの処理を確認（{len(result.duplicate_rows)}件）"
            )
        else:
            self.dup_btn.setVisible(False)

        self.confirm_summary.setText(
            f"インポート対象: 正常 {len(result.valid_rows)}件 / "
            f"重複 {len(result.duplicate_rows)}件\n"
            f"ファイル: {Path(self.source_path).name}\n"
            f"シート: {sheet_name}\n"
            f"{remap_text}{dup_summary}\n"
            "「インポート実行」を押すとデータベースに書き込まれます。"
        )

        rows_to_show = result.valid_rows + [
            r for r in result.duplicate_rows if r.duplicate_action != "skip"
        ]
        self.valid_table.setColumnCount(4)
        self.valid_table.setHorizontalHeaderLabels(
            ["氏名", "没年月日", "属性数", "処理"]
        )
        self.valid_table.setRowCount(min(len(rows_to_show), 200))
        for i, row in enumerate(rows_to_show[:200]):
            self.valid_table.setItem(i, 0, QTableWidgetItem(row.name))
            self.valid_table.setItem(i, 1, QTableWidgetItem(row.era_display))
            self.valid_table.setItem(i, 2, QTableWidgetItem(str(len(row.attributes))))
            if row.duplicate_of is None:
                action_text = "新規追加"
            elif row.duplicate_action == "overwrite":
                action_text = "上書き"
            elif row.duplicate_action == "insert":
                action_text = "新規追加（重複）"
            else:
                action_text = "スキップ"
            self.valid_table.setItem(i, 3, QTableWidgetItem(action_text))

    def _execute_import(self):
        result = self._validation_result
        if not result:
            return

        all_rows = result.valid_rows + result.duplicate_rows
        write_count = sum(1 for r in all_rows if r.duplicate_action != "skip")

        reply = QMessageBox.question(
            self,
            "最終確認",
            f"{write_count}件のデータをデータベースに書き込みます。\n\n実行しますか？",
        )
        if reply != QMessageBox.Yes:
            return

        try:
            outcome = import_validated_rows(self.db, all_rows)
        except DatabaseError as e:
            self.result_icon.setText("NG")
            self.result_icon.setStyleSheet(
                "font-size: 48px; padding: 16px; color: #e74c3c;"
            )
            self.result_label.setText(f"インポートに失敗しました\n\n{e}")
            self.result_label.setStyleSheet(
                "color: #e74c3c; font-size: 16px; padding: 16px;"
            )
            self.failures_table.setVisible(False)
            self._go_to_step(6)
            return

        inserted = outcome["inserted"]
        updated = outcome["updated"]
        skipped = outcome["skipped"]
        failures = outcome["failures"]

        if failures:
            self.result_icon.setText("⚠")
            self.result_icon.setStyleSheet(
                "font-size: 48px; padding: 16px; color: #e67e22;"
            )
        else:
            self.result_icon.setText("OK")
            self.result_icon.setStyleSheet(
                "font-size: 48px; padding: 16px; color: #27ae60;"
            )

        msg_lines = [
            "インポート結果:",
            f"  新規追加: {inserted}件",
            f"  上書き: {updated}件",
            f"  スキップ: {skipped}件",
        ]
        if failures:
            msg_lines.append(f"  失敗: {len(failures)}件（下記参照）")
        self.result_label.setText("\n".join(msg_lines))
        self.result_label.setStyleSheet(
            "color: #2c3e50; font-size: 16px; padding: 16px;"
        )

        if failures:
            self.failures_table.setRowCount(len(failures))
            for i, (idx, reason) in enumerate(failures):
                self.failures_table.setItem(i, 0, QTableWidgetItem(str(idx + 2)))
                self.failures_table.setItem(i, 1, QTableWidgetItem(reason))
            self.failures_table.setVisible(True)
        else:
            self.failures_table.setVisible(False)

        self._go_to_step(6)

    # ─── Helpers ───

    def _get_current_sheet_name(self) -> str:
        if self.sheet_list.currentItem():
            return self.sheet_list.currentItem().data(Qt.UserRole)
        elif self.sheets:
            return list(self.sheets.keys())[0]
        return ""
