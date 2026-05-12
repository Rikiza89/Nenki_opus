"""Database page - QTableView with CRUD operations.

Lazy-loaded paginated model. Attribute lookups are pre-indexed at refresh time
so per-cell painting is O(1) regardless of how many EAV attributes a person has.
Search is debounced so typing doesn't hammer the DB.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QPushButton,
    QLineEdit,
    QLabel,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer

from memorial_app.database.db_manager import DatabaseManager, DatabaseError
from memorial_app.database.models import Person
from memorial_app.core.era_converter import format_date_era
from memorial_app.ui.edit_dialog import EditDialog


class PersonTableModel(QAbstractTableModel):
    """Lazy-loading table model for Person records."""

    COLUMNS = ["ID", "氏名", "没年月日（元号）", "没年月日（西暦）", "元Excel"]
    PAGE_SIZE = 100

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self._data: list[Person] = []
        self._attr_index: list[dict[str, str]] = []
        self._total = 0
        self._dynamic_cols: list[str] = []
        self._loaded_all = False

    @staticmethod
    def _index_attrs(person: Person) -> dict[str, str]:
        return {a.column_name: (a.value or "") for a in person.attributes}

    def _safe_get_count(self) -> int:
        try:
            return self.db.get_person_count()
        except DatabaseError:
            return 0

    def _safe_get_all(self, offset: int, limit: int) -> list[Person]:
        try:
            return self.db.get_all_persons(offset=offset, limit=limit)
        except DatabaseError:
            return []

    def _safe_get_columns(self) -> list[str]:
        try:
            return self.db.get_all_column_names()
        except DatabaseError:
            return []

    def refresh(self):
        self.beginResetModel()
        self._total = self._safe_get_count()
        self._data = self._safe_get_all(0, self.PAGE_SIZE)
        self._attr_index = [self._index_attrs(p) for p in self._data]
        self._dynamic_cols = self._safe_get_columns()
        self._loaded_all = len(self._data) >= self._total
        self.endResetModel()

    def canFetchMore(self, parent=QModelIndex()):
        return not self._loaded_all

    def fetchMore(self, parent=QModelIndex()):
        remaining = self._total - len(self._data)
        fetch_count = min(remaining, self.PAGE_SIZE)
        if fetch_count <= 0:
            return
        self.beginInsertRows(
            QModelIndex(), len(self._data), len(self._data) + fetch_count - 1
        )
        new_data = self._safe_get_all(len(self._data), fetch_count)
        self._data.extend(new_data)
        self._attr_index.extend(self._index_attrs(p) for p in new_data)
        if len(self._data) >= self._total:
            self._loaded_all = True
        self.endInsertRows()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS) + len(self._dynamic_cols)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section < len(self.COLUMNS):
                return self.COLUMNS[section]
            dyn_idx = section - len(self.COLUMNS)
            if dyn_idx < len(self._dynamic_cols):
                return self._dynamic_cols[dyn_idx]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None

        row = index.row()
        if row >= len(self._data):
            return None
        person = self._data[row]
        col = index.column()

        if col == 0:
            return str(person.id)
        elif col == 1:
            return person.name
        elif col == 2:
            d = person.safe_death_date
            if d is None:
                return person.death_date
            try:
                return format_date_era(d)
            except (ValueError, TypeError):
                return person.death_date
        elif col == 3:
            return person.death_date
        elif col == 4:
            return person.source_file_path or ""
        else:
            dyn_idx = col - len(self.COLUMNS)
            if dyn_idx < len(self._dynamic_cols):
                col_name = self._dynamic_cols[dyn_idx]
                return self._attr_index[row].get(col_name, "")
            return ""

    def get_person(self, row: int) -> Person | None:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def search(self, query: str):
        self.beginResetModel()
        if query:
            try:
                self._data = self.db.search_persons(query, limit=1000)
            except DatabaseError:
                self._data = []
            self._total = len(self._data)
            self._loaded_all = True
        else:
            self._total = self._safe_get_count()
            self._data = self._safe_get_all(0, self.PAGE_SIZE)
            self._loaded_all = len(self._data) >= self._total
        self._attr_index = [self._index_attrs(p) for p in self._data]
        self._dynamic_cols = self._safe_get_columns()
        self.endResetModel()


class PeopleTablePage(QWidget):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("データベース")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("氏名で検索...")
        self.search_input.setStyleSheet("padding: 6px; font-size: 13px;")
        # Debounce search so we don't hit the DB on every keystroke.
        self._search_timer = QTimer(self)
        self._search_timer.setInterval(300)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)
        self.search_input.textChanged.connect(lambda _t: self._search_timer.start())
        toolbar.addWidget(self.search_input, 1)

        btn_style = "padding: 8px 16px; font-size: 13px;"

        self.add_btn = QPushButton("追加")
        self.add_btn.setStyleSheet(f"background: #27ae60; color: white; {btn_style}")
        self.add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(self.add_btn)

        self.edit_btn = QPushButton("編集")
        self.edit_btn.setStyleSheet(f"background: #3498db; color: white; {btn_style}")
        self.edit_btn.clicked.connect(self._on_edit)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("削除")
        self.delete_btn.setStyleSheet(f"background: #e74c3c; color: white; {btn_style}")
        self.delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(self.delete_btn)

        layout.addLayout(toolbar)

        self.model = PersonTableModel(self.db)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        self.status_label = QLabel()
        self.status_label.setStyleSheet(
            "color: #7f8c8d; font-size: 12px; padding: 4px;"
        )
        layout.addWidget(self.status_label)

    def refresh(self):
        self.model.refresh()
        self._update_status()

    def _update_status(self):
        try:
            total = self.db.get_person_count()
        except DatabaseError as e:
            self.status_label.setText(f"件数取得エラー: {e}")
            return
        self.status_label.setText(f"全 {total} 件")

    def _apply_search(self):
        self.model.search(self.search_input.text())
        self._update_status()

    def _on_add(self):
        dialog = EditDialog(self.db, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_edit(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            QMessageBox.information(self, "情報", "編集する行を選択してください。")
            return
        person = self.model.get_person(idx.row())
        if person:
            dialog = EditDialog(self.db, person_id=person.id, parent=self)
            if dialog.exec():
                self.refresh()

    def _on_delete(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            QMessageBox.information(self, "情報", "削除する行を選択してください。")
            return
        person = self.model.get_person(idx.row())
        if not person:
            return
        reply = QMessageBox.question(
            self,
            "削除確認",
            f"「{person.name}」を削除しますか？\nこの操作は元に戻せません。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.db.delete_person(person.id)
        except DatabaseError as e:
            QMessageBox.critical(self, "削除エラー", str(e))
            return
        self.refresh()

    def _on_double_click(self, index: QModelIndex):
        person = self.model.get_person(index.row())
        if person:
            dialog = EditDialog(self.db, person_id=person.id, parent=self)
            if dialog.exec():
                self.refresh()
