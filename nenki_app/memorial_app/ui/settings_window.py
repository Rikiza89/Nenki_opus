"""Settings page - date display, backup/restore, database reset, era management."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QFileDialog,
    QLineEdit,
    QDateEdit,
    QTableWidget,
    QTableWidgetItem,
    QInputDialog,
    QDialog,
    QDialogButtonBox,
    QRadioButton,
    QButtonGroup,
)
from PySide6.QtCore import Qt, QDate

from memorial_app.database.db_manager import DatabaseManager, DatabaseError
from memorial_app.core.era_converter import get_custom_eras, save_custom_eras, Era

import datetime


class _RestoreChoiceDialog(QDialog):
    """Asks whether to merge JSON-restored data with the current DB or replace it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("復元モードの選択")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "復元の方法を選択してください:\n"
                "・追加: 既存データを残し、JSONの内容を追加します\n"
                "・置換: 既存データを全て削除してJSONの内容で置き換えます\n"
                "  （置換前に自動バックアップが作成されます）"
            )
        )
        self._merge_rb = QRadioButton("追加（既存データを残す）")
        self._merge_rb.setChecked(True)
        self._replace_rb = QRadioButton("置換（既存データを削除）")
        group = QButtonGroup(self)
        group.addButton(self._merge_rb)
        group.addButton(self._replace_rb)
        layout.addWidget(self._merge_rb)
        layout.addWidget(self._replace_rb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def replace(self) -> bool:
        return self._replace_rb.isChecked()


class SettingsPage(QWidget):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("設定")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        # Backup/Restore
        backup_group = QGroupBox("バックアップ・復元")
        backup_layout = QVBoxLayout(backup_group)

        backup_btn_layout = QHBoxLayout()
        backup_btn = QPushButton("バックアップ作成")
        backup_btn.setStyleSheet("padding: 8px 16px;")
        backup_btn.clicked.connect(self._backup)
        backup_btn_layout.addWidget(backup_btn)

        restore_btn = QPushButton("JSONから復元")
        restore_btn.setStyleSheet("padding: 8px 16px;")
        restore_btn.clicked.connect(self._restore)
        backup_btn_layout.addWidget(restore_btn)
        backup_btn_layout.addStretch()
        backup_layout.addLayout(backup_btn_layout)

        layout.addWidget(backup_group)

        # Database Reset (typed confirmation)
        reset_group = QGroupBox("データベースリセット")
        reset_layout = QHBoxLayout(reset_group)
        reset_label = QLabel(
            "全データを削除してデータベースを初期化します。バックアップが自動作成されます。"
        )
        reset_label.setStyleSheet("color: #e74c3c;")
        reset_layout.addWidget(reset_label, 1)
        reset_btn = QPushButton("リセット実行")
        reset_btn.setStyleSheet("background: #e74c3c; color: white; padding: 8px 16px;")
        reset_btn.clicked.connect(self._reset_db)
        reset_layout.addWidget(reset_btn)
        layout.addWidget(reset_group)

        # Custom Era Management
        era_group = QGroupBox("カスタム元号管理")
        era_layout = QVBoxLayout(era_group)

        self.era_table = QTableWidget()
        self.era_table.setColumnCount(3)
        self.era_table.setHorizontalHeaderLabels(["元号名", "略称", "開始日"])
        self.era_table.horizontalHeader().setStretchLastSection(True)
        era_layout.addWidget(self.era_table)

        add_era_layout = QFormLayout()
        self.era_name_input = QLineEdit()
        self.era_name_input.setPlaceholderText("例: 新元号")
        add_era_layout.addRow("元号名:", self.era_name_input)

        self.era_abbr_input = QLineEdit()
        self.era_abbr_input.setPlaceholderText("例: N")
        add_era_layout.addRow("略称:", self.era_abbr_input)

        self.era_date_input = QDateEdit()
        self.era_date_input.setDisplayFormat("yyyy-MM-dd")
        self.era_date_input.setCalendarPopup(True)
        self.era_date_input.setDate(QDate.currentDate())
        add_era_layout.addRow("開始日:", self.era_date_input)

        era_layout.addLayout(add_era_layout)

        era_btn_layout = QHBoxLayout()
        add_era_btn = QPushButton("元号追加")
        add_era_btn.setStyleSheet(
            "background: #27ae60; color: white; padding: 6px 16px;"
        )
        add_era_btn.clicked.connect(self._add_era)
        era_btn_layout.addWidget(add_era_btn)

        del_era_btn = QPushButton("選択削除")
        del_era_btn.setStyleSheet(
            "background: #e74c3c; color: white; padding: 6px 16px;"
        )
        del_era_btn.clicked.connect(self._delete_era)
        era_btn_layout.addWidget(del_era_btn)
        era_btn_layout.addStretch()
        era_layout.addLayout(era_btn_layout)

        layout.addWidget(era_group)
        layout.addStretch()

    def refresh(self):
        self._load_eras()

    def _load_eras(self):
        eras = get_custom_eras()
        self.era_table.setRowCount(len(eras))
        for i, era in enumerate(eras):
            self.era_table.setItem(i, 0, QTableWidgetItem(era.name))
            self.era_table.setItem(i, 1, QTableWidgetItem(era.abbreviation))
            self.era_table.setItem(i, 2, QTableWidgetItem(era.start_date.isoformat()))

    def _backup(self):
        try:
            db_path, json_path = self.db.backup()
            QMessageBox.information(
                self,
                "バックアップ完了",
                f"バックアップを作成しました:\n{db_path}\n{json_path}",
            )
        except DatabaseError as e:
            QMessageBox.critical(self, "エラー", str(e))
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"バックアップに失敗しました:\n{e}")

    def _restore(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "復元するJSONファイルを選択", "", "JSON (*.json)"
        )
        if not path:
            return

        dlg = _RestoreChoiceDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        replace = dlg.replace()

        try:
            result = self.db.restore_from_json(Path(path), replace=replace)
        except DatabaseError as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"復元に失敗しました:\n{e}")
            return

        msg = (
            f"復元完了:\n"
            f"  追加: {result.inserted}件\n"
            f"  失敗: {len(result.failures)}件"
        )
        if result.failures:
            preview = "\n".join(
                f"  行{idx + 1}: {reason}" for idx, reason in result.failures[:5]
            )
            msg += "\n\n失敗の一部:\n" + preview
        QMessageBox.information(self, "復元結果", msg)

    def _reset_db(self):
        text, ok = QInputDialog.getText(
            self,
            "リセット確認",
            "本当にデータベースをリセットしますか？\n"
            "全データが削除されます（バックアップは自動作成されます）。\n\n"
            "実行するには、半角で 'RESET' と入力して OK を押してください。",
        )
        if not ok or text.strip() != "RESET":
            QMessageBox.information(
                self, "キャンセル", "リセットはキャンセルされました。"
            )
            return
        try:
            backup_path = self.db.reset_database()
            QMessageBox.information(
                self,
                "完了",
                f"データベースをリセットしました。\nバックアップ: {backup_path}",
            )
        except DatabaseError as e:
            QMessageBox.critical(self, "エラー", str(e))
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"リセットに失敗しました:\n{e}")

    def _add_era(self):
        name = self.era_name_input.text().strip()
        abbr = self.era_abbr_input.text().strip()
        qdate = self.era_date_input.date()
        start = datetime.date(qdate.year(), qdate.month(), qdate.day())

        if not name or not abbr:
            QMessageBox.warning(self, "入力エラー", "元号名と略称を入力してください。")
            return

        eras = get_custom_eras()
        if any(e.name == name for e in eras):
            QMessageBox.warning(
                self, "重複", f"元号「{name}」は既に登録されています。"
            )
            return
        if any(e.abbreviation.upper() == abbr.upper() for e in eras):
            QMessageBox.warning(
                self, "重複", f"略称「{abbr}」は既に登録されています。"
            )
            return

        eras.append(Era(name=name, abbreviation=abbr, start_date=start))
        try:
            save_custom_eras(eras)
        except OSError as e:
            QMessageBox.critical(self, "エラー", f"元号の保存に失敗しました:\n{e}")
            return
        self._load_eras()
        self.era_name_input.clear()
        self.era_abbr_input.clear()
        QMessageBox.information(self, "完了", f"元号「{name}」を追加しました。")

    def _delete_era(self):
        row = self.era_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "情報", "削除する元号を選択してください。")
            return
        eras = get_custom_eras()
        if row >= len(eras):
            return
        era = eras.pop(row)
        try:
            save_custom_eras(eras)
        except OSError as e:
            QMessageBox.critical(self, "エラー", f"元号の保存に失敗しました:\n{e}")
            return
        self._load_eras()
        QMessageBox.information(self, "完了", f"元号「{era.name}」を削除しました。")
