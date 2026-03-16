"""Template editor - configure document generation settings and preview."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QGroupBox,
    QGridLayout,
    QPushButton,
    QComboBox,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt

from memorial_app.core.nenki_calculator import STANDARD_NENKI, DEFAULT_SELECTED_NENKI


class TemplateEditorDialog(QDialog):
    """Dialog for configuring document generation options."""

    def __init__(self, available_columns: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("ドキュメント設定")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

        # Column selection
        col_group = QGroupBox("表示する項目")
        col_layout = QGridLayout(col_group)
        self.column_checks = {}
        for i, col in enumerate(available_columns):
            cb = QCheckBox(col)
            cb.setChecked(True)
            col_layout.addWidget(cb, i // 3, i % 3)
            self.column_checks[col] = cb
        layout.addWidget(col_group)

        # Nenki type selection
        nenki_group = QGroupBox("表示する年忌の種類")
        nenki_layout = QGridLayout(nenki_group)
        self.nenki_checks = {}
        all_nenki = [("百ヶ日", 0)] + STANDARD_NENKI
        for i, (name, _) in enumerate(all_nenki):
            cb = QCheckBox(name)
            cb.setChecked(name in DEFAULT_SELECTED_NENKI)
            nenki_layout.addWidget(cb, i // 4, i % 4)
            self.nenki_checks[name] = cb
        layout.addWidget(nenki_group)

        # Layout options
        options_group = QGroupBox("レイアウトオプション")
        options_layout = QHBoxLayout(options_group)
        options_layout.addWidget(QLabel("配置:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("1列レイアウト", True)
        self.layout_combo.addItem("2列レイアウト", False)
        options_layout.addWidget(self.layout_combo)
        options_layout.addStretch()
        layout.addWidget(options_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_columns(self) -> list[str]:
        return [name for name, cb in self.column_checks.items() if cb.isChecked()]

    def get_selected_nenki(self) -> list[str]:
        return [name for name, cb in self.nenki_checks.items() if cb.isChecked()]

    def get_single_column(self) -> bool:
        return self.layout_combo.currentData()
