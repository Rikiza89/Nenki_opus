"""Visual editor window for nenki document generation.

Split-panel layout:
  Left  — QTabWidget with "レイアウト" and "データ編集" tabs
  Right — Live HTML preview via QWebEngineView (falls back to plain text)

The window receives the already-computed anniversary results and lets the user:
  • Reorder / show / hide output fields
  • Adjust font sizes and column count
  • Inline-edit person name, death date, and EAV attributes (writes to SQLite)
  • Export directly to Word or PDF using the current settings
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QLabel,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QFormLayout,
    QGroupBox,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    _HAS_WEBENGINE = True
except ImportError:
    _HAS_WEBENGINE = False

from memorial_app.database.db_manager import DatabaseManager, DatabaseError
from memorial_app.core.date_converter import (
    format_date_kanji_era,
    format_nenki_title,
    format_year_kanji_era,
)
from memorial_app.core.nenki_calculator import STANDARD_NENKI
from memorial_app.ui.visual_editor.preview_renderer import LayoutSettings, build_html

# Built-in display fields available in results (not EAV)
_BUILTIN_FIELDS = [
    "法要日（元号漢字）",
    "法要日（西暦）",
    "氏名",
    "命日（元号漢字）",
    "命日（西暦）",
]

# Column indices in the data-editing table
_COL_NAME = 0       # Person.name (editable)
_COL_DEATH = 1      # Person.death_date ISO (editable)
_COL_ANN = 2        # anniversary date (read-only reference)
_COL_EAV_START = 3  # EAV attribute columns start here

_NENKI_ORDER = {
    name: i for i, (name, _) in enumerate([("百ヶ日", 0)] + STANDARD_NENKI)
}


def _field_value(field_key: str, ann, person_name: str, attrs: dict) -> str:
    """Resolve a display-field key to its string value for a given result entry."""
    if field_key == "法要日（元号漢字）":
        return format_date_kanji_era(ann.date)
    if field_key == "法要日（西暦）":
        return ann.date.isoformat()
    if field_key == "氏名":
        return person_name
    if field_key == "命日（元号漢字）":
        return format_date_kanji_era(ann.death_date)
    if field_key == "命日（西暦）":
        return ann.death_date.isoformat()
    return attrs.get(field_key, "")


class VisualEditorWindow(QMainWindow):
    """Visual editor for nenki document layout and data.

    Args:
        results: [(ann, person_name, attrs_dict, person_id), ...]
        target_year: calendar year the anniversaries are calculated for
        field_names: initially selected export fields (年忌名 already excluded)
        single_column: initial column layout
        db_manager: live DatabaseManager for writing edits
    """

    def __init__(
        self,
        results: list,
        target_year: int,
        field_names: list[str],
        single_column: bool,
        db_manager: DatabaseManager,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"ビジュアルエディタ — {target_year}年度 年忌表")
        self.resize(1600, 900)

        self._results: list = list(results)
        self._target_year = target_year
        self._db = db_manager

        # All EAV keys present across all results (stable sorted order)
        self._all_attr_keys: list[str] = sorted(
            {k for _, _, attrs, _ in self._results for k in attrs}
        )

        # Match Word's per-mode default font sizes so preview = export on first open
        default_header, default_entry = (28, 18) if single_column else (16, 11)
        self._layout = LayoutSettings(
            title=format_nenki_title(target_year),
            single_column=single_column,
            header_font_size=default_header,
            entry_font_size=default_entry,
            field_names=list(field_names),
        )

        # Per-group mutable state — populated in _populate_data_tabs()
        self._group_keys: list[str] = []
        self._group_pids: list[list[int]] = []          # person_ids per group row
        self._group_anns: list[list] = []               # ann objects per group row
        self._dirty: list[dict[tuple[int, int], str]] = []  # dirty cells per group
        self._group_tables: list[QTableWidget] = []
        self._group_dirty_labels: list[QLabel] = []

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_refresh)

        self._build_ui()
        self._populate_data_tabs()
        self._schedule_refresh()

    # ------------------------------------------------------------------ #
    # Grouping helpers                                                     #
    # ------------------------------------------------------------------ #

    def _group_results(self) -> list[tuple[str, list[tuple]]]:
        """Return results grouped and sorted by nenki order."""
        groups: dict[str, list] = defaultdict(list)
        for ann, name, attrs, pid in self._results:
            death_year_era = format_year_kanji_era(ann.death_date)
            key = f"{ann.name}|{ann.years_offset}|{death_year_era}"
            groups[key].append((ann, name, attrs, pid))
        return sorted(
            groups.items(),
            key=lambda x: _NENKI_ORDER.get(x[0].split("|")[0], 999),
        )

    def _build_grouped_data(self) -> list:
        """Build grouped_data structure for preview_renderer.build_html()."""
        result = []
        for group_key, entries in self._group_results():
            rows = []
            for ann, name, attrs, pid in entries:
                values = [_field_value(f, ann, name, attrs) for f in self._layout.field_names]
                rows.append((values, pid))
            result.append((group_key, rows))
        return result

    def _available_fields(self) -> list[str]:
        """All selectable display fields (年忌名 is always a group header, not listed)."""
        seen: set[str] = set()
        fields: list[str] = []
        for f in _BUILTIN_FIELDS:
            if f not in seen:
                fields.append(f)
                seen.add(f)
        for k in self._all_attr_keys:
            if k not in seen:
                fields.append(k)
                seen.add(k)
        return fields

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Recalculation notice (shown after death-date edits)
        self._recalc_banner = QLabel(
            "⚠  命日が変更されました。年忌計算画面で再計算を実行してください。"
        )
        self._recalc_banner.setStyleSheet(
            "background:#e67e22;color:white;padding:6px 12px;"
            "font-weight:bold;border-radius:4px;"
        )
        self._recalc_banner.setVisible(False)
        root.addWidget(self._recalc_banner)

        # ---- Splitter: left panel | preview ----
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        self._left_tabs = QTabWidget()
        self._left_tabs.setMinimumWidth(340)
        self._left_tabs.setMaximumWidth(500)
        splitter.addWidget(self._left_tabs)

        self._left_tabs.addTab(self._build_layout_tab(), "レイアウト")
        self._data_tabs = QTabWidget()
        self._left_tabs.addTab(self._data_tabs, "データ編集")

        if _HAS_WEBENGINE:
            self._webview = QWebEngineView()
            splitter.addWidget(self._webview)
        else:
            notice = QLabel(
                "⚠ プレビューを表示するには PySide6-WebEngine が必要です。\n\n"
                "setup_packages.bat を再実行するとインストールされます。\n"
                "Word/PDF出力ボタンは引き続きご利用いただけます。\n\n"
                "─────────────────────────────\n"
            )
            notice.setStyleSheet(
                "color:#c0392b;font-size:13px;padding:16px;"
                "background:#fef9e7;border-bottom:1px solid #f9e79f;"
            )
            notice.setWordWrap(True)
            self._fallback_label = QLabel("")
            self._fallback_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            self._fallback_label.setWordWrap(True)
            self._fallback_label.setStyleSheet(
                "background:white;padding:16px;font-family:monospace;font-size:12px;"
            )
            fallback_container = QWidget()
            fallback_vbox = QVBoxLayout(fallback_container)
            fallback_vbox.setContentsMargins(0, 0, 0, 0)
            fallback_vbox.addWidget(notice)
            scroll = QScrollArea()
            scroll.setWidget(self._fallback_label)
            scroll.setWidgetResizable(True)
            fallback_vbox.addWidget(scroll, 1)
            splitter.addWidget(fallback_container)

        splitter.setSizes([400, 1180])

        # ---- Bottom toolbar ----
        bar = QHBoxLayout()
        bar.setSpacing(8)
        root.addLayout(bar)

        word_btn = QPushButton("Word出力")
        word_btn.setStyleSheet(
            "background:#2980b9;color:white;padding:6px 18px;font-weight:bold;"
        )
        word_btn.clicked.connect(self._export_word)
        bar.addWidget(word_btn)

        pdf_btn = QPushButton("PDF出力")
        pdf_btn.setStyleSheet(
            "background:#c0392b;color:white;padding:6px 18px;font-weight:bold;"
        )
        pdf_btn.clicked.connect(self._export_pdf)
        bar.addWidget(pdf_btn)

        bar.addStretch()

        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(self.close)
        bar.addWidget(close_btn)

    def _build_layout_tab(self) -> QWidget:
        """Build the layout-settings tab (wrapped in a scroll area)."""
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(12, 12, 12, 12)
        inner_layout.setSpacing(12)

        # --- Document settings ---
        doc_group = QGroupBox("文書設定")
        doc_form = QFormLayout(doc_group)

        self._title_edit = QLineEdit(self._layout.title)
        self._title_edit.textChanged.connect(self._on_title_changed)
        doc_form.addRow("タイトル:", self._title_edit)

        self._col_combo = QComboBox()
        self._col_combo.addItem("1列レイアウト（大きい文字）", True)
        self._col_combo.addItem("2列レイアウト（コンパクト）", False)
        self._col_combo.setCurrentIndex(0 if self._layout.single_column else 1)
        self._col_combo.currentIndexChanged.connect(self._on_col_changed)
        doc_form.addRow("列数:", self._col_combo)

        inner_layout.addWidget(doc_group)

        # --- Font sizes ---
        font_group = QGroupBox("フォントサイズ")
        font_form = QFormLayout(font_group)

        self._header_spin = QSpinBox()
        self._header_spin.setRange(8, 72)
        self._header_spin.setSuffix(" pt")
        self._header_spin.setValue(self._layout.header_font_size)
        self._header_spin.valueChanged.connect(self._on_font_changed)
        font_form.addRow("見出し:", self._header_spin)

        self._entry_spin = QSpinBox()
        self._entry_spin.setRange(6, 48)
        self._entry_spin.setSuffix(" pt")
        self._entry_spin.setValue(self._layout.entry_font_size)
        self._entry_spin.valueChanged.connect(self._on_font_changed)
        font_form.addRow("本文:", self._entry_spin)

        inner_layout.addWidget(font_group)

        # --- Field selection ---
        field_group = QGroupBox("出力項目（ドラッグで順序変更・チェックで表示）")
        field_vbox = QVBoxLayout(field_group)

        hint = QLabel("チェックした項目の順にプレビューへ出力されます。")
        hint.setStyleSheet("color:#7f8c8d;font-size:11px;")
        field_vbox.addWidget(hint)

        self._field_list = QListWidget()
        self._field_list.setDragDropMode(QListWidget.InternalMove)
        self._field_list.setDefaultDropAction(Qt.MoveAction)
        self._field_list.setMaximumHeight(240)

        available = self._available_fields()
        checked_set = set(self._layout.field_names)
        # Show checked fields first (preserving user order), then unchecked
        ordered = [f for f in self._layout.field_names if f in set(available)]
        ordered += [f for f in available if f not in set(ordered)]

        for f in ordered:
            item = QListWidgetItem(f)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Checked if f in checked_set else Qt.Unchecked)
            self._field_list.addItem(item)

        self._field_list.itemChanged.connect(self._on_field_list_changed)
        self._field_list.model().rowsMoved.connect(self._on_field_list_changed)
        field_vbox.addWidget(self._field_list)

        btn_row = QHBoxLayout()
        all_btn = QPushButton("全て選択")
        all_btn.clicked.connect(lambda: self._set_all_fields(True))
        none_btn = QPushButton("全て解除")
        none_btn.clicked.connect(lambda: self._set_all_fields(False))
        btn_row.addWidget(all_btn)
        btn_row.addWidget(none_btn)
        btn_row.addStretch()
        field_vbox.addLayout(btn_row)

        inner_layout.addWidget(field_group)
        inner_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        return scroll

    # ------------------------------------------------------------------ #
    # Data-editing tab                                                     #
    # ------------------------------------------------------------------ #

    def _populate_data_tabs(self):
        """Build one sub-tab per nenki group with an editable QTableWidget."""
        self._data_tabs.clear()
        self._group_keys.clear()
        self._group_pids.clear()
        self._group_anns.clear()
        self._dirty.clear()
        self._group_tables.clear()
        self._group_dirty_labels.clear()

        eav_keys = self._all_attr_keys
        all_col_headers = ["氏名", "命日（ISO）", "法要日（参考）"] + list(eav_keys)

        for group_idx, (group_key, entries) in enumerate(self._group_results()):
            nenki_name = group_key.split("|")[0]
            self._group_keys.append(group_key)
            self._dirty.append({})
            self._group_pids.append([pid for _, _, _, pid in entries])
            self._group_anns.append([ann for ann, _, _, _ in entries])

            table = QTableWidget(len(entries), len(all_col_headers))
            table.setHorizontalHeaderLabels(all_col_headers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            table.horizontalHeader().setStretchLastSection(True)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QTableWidget.SelectRows)

            table.blockSignals(True)
            for row, (ann, name, attrs, _) in enumerate(entries):
                table.setItem(row, _COL_NAME, QTableWidgetItem(name))
                table.setItem(row, _COL_DEATH, QTableWidgetItem(ann.death_date.isoformat()))

                ann_item = QTableWidgetItem(format_date_kanji_era(ann.date))
                ann_item.setFlags(ann_item.flags() & ~Qt.ItemIsEditable)
                ann_item.setForeground(Qt.darkGray)
                table.setItem(row, _COL_ANN, ann_item)

                for ci, attr_key in enumerate(eav_keys):
                    table.setItem(
                        row, _COL_EAV_START + ci,
                        QTableWidgetItem(attrs.get(attr_key, "")),
                    )
            table.blockSignals(False)

            gi = group_idx  # capture for lambda
            table.cellChanged.connect(
                lambda r, c, idx=gi: self._on_cell_changed(idx, r, c)
            )
            self._group_tables.append(table)

            # Tab container
            container = QWidget()
            vbox = QVBoxLayout(container)
            vbox.setContentsMargins(6, 6, 6, 6)
            vbox.addWidget(table)

            # Save row
            save_row = QHBoxLayout()
            dirty_lbl = QLabel("")
            dirty_lbl.setStyleSheet("color:#e67e22;font-size:11px;")
            self._group_dirty_labels.append(dirty_lbl)
            save_row.addWidget(dirty_lbl, 1)

            save_btn = QPushButton("保存")
            save_btn.setStyleSheet(
                "background:#27ae60;color:white;padding:4px 16px;font-weight:bold;"
            )
            save_btn.clicked.connect(
                lambda checked=False, idx=gi: self._save_group(idx)
            )
            save_row.addWidget(save_btn)
            vbox.addLayout(save_row)

            self._data_tabs.addTab(container, nenki_name)

    # ------------------------------------------------------------------ #
    # Cell-change handler                                                  #
    # ------------------------------------------------------------------ #

    def _on_cell_changed(self, group_idx: int, row: int, col: int):
        if col == _COL_ANN:
            return  # read-only column; should not be reachable
        table = self._group_tables[group_idx]
        item = table.item(row, col)
        if item is None:
            return

        new_val = item.text()
        self._dirty[group_idx][(row, col)] = new_val
        item.setBackground(Qt.yellow)

        n = len(self._dirty[group_idx])
        self._group_dirty_labels[group_idx].setText(f"未保存の変更: {n}件")

        # Update _results in-memory for name and EAV attrs so preview refreshes
        pid = self._group_pids[group_idx][row]
        idx = next((i for i, (_, _, _, p) in enumerate(self._results) if p == pid), None)
        if idx is None:
            return
        ann, name, attrs, p = self._results[idx]
        if col == _COL_NAME:
            self._results[idx] = (ann, new_val, attrs, p)
        elif col >= _COL_EAV_START:
            eav_key = self._all_attr_keys[col - _COL_EAV_START]
            new_attrs = {**attrs, eav_key: new_val}
            self._results[idx] = (ann, name, new_attrs, p)
        # Death-date changes do not update the preview until saved + recalculated

        self._schedule_refresh()

    # ------------------------------------------------------------------ #
    # Save group changes to DB                                             #
    # ------------------------------------------------------------------ #

    def _save_group(self, group_idx: int):
        dirty = self._dirty[group_idx]
        if not dirty:
            return

        table = self._group_tables[group_idx]
        death_date_changed = False
        errors: list[str] = []

        for (row, col), new_val in list(dirty.items()):
            pid = self._group_pids[group_idx][row]
            try:
                if col == _COL_NAME:
                    self._db.update_person(pid, name=new_val)
                elif col == _COL_DEATH:
                    datetime.date.fromisoformat(new_val)   # validate before writing
                    self._db.update_person(pid, death_date=new_val)
                    death_date_changed = True
                elif col >= _COL_EAV_START:
                    eav_key = self._all_attr_keys[col - _COL_EAV_START]
                    self._db.update_person(
                        pid,
                        attributes={eav_key: new_val},
                        merge_attributes=True,
                    )
                # Clear highlight on success
                item = table.item(row, col)
                if item:
                    item.setBackground(Qt.white)
                del dirty[(row, col)]
            except (DatabaseError, ValueError) as exc:
                errors.append(f"行{row + 1}: {exc}")

        n = len(dirty)
        self._group_dirty_labels[group_idx].setText(f"未保存の変更: {n}件" if n else "")

        if death_date_changed:
            self._recalc_banner.setVisible(True)

        if errors:
            QMessageBox.warning(self, "保存エラー", "\n".join(errors))
        else:
            QMessageBox.information(self, "保存完了", "変更をデータベースに保存しました。")

    # ------------------------------------------------------------------ #
    # Layout-change handlers                                               #
    # ------------------------------------------------------------------ #

    def _on_title_changed(self, text: str):
        self._layout.title = text
        self._schedule_refresh()

    def _on_col_changed(self):
        single = bool(self._col_combo.currentData())
        self._layout.single_column = single
        # Sync spinners to the mode's Word defaults so preview matches export
        default_header, default_entry = (28, 18) if single else (16, 11)
        self._header_spin.setValue(default_header)
        self._entry_spin.setValue(default_entry)
        self._schedule_refresh()

    def _on_font_changed(self):
        self._layout.header_font_size = self._header_spin.value()
        self._layout.entry_font_size = self._entry_spin.value()
        self._schedule_refresh()

    def _on_field_list_changed(self, *_):
        checked = []
        for i in range(self._field_list.count()):
            item = self._field_list.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        self._layout.field_names = checked
        self._schedule_refresh()

    def _set_all_fields(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self._field_list.count()):
            self._field_list.item(i).setCheckState(state)

    # ------------------------------------------------------------------ #
    # Preview refresh                                                      #
    # ------------------------------------------------------------------ #

    def _schedule_refresh(self):
        self._debounce.start(300)

    def _do_refresh(self):
        grouped = self._build_grouped_data()
        html = build_html(grouped, self._layout)
        if _HAS_WEBENGINE:
            self._webview.setHtml(html)
        else:
            lines = [self._layout.title, ""]
            for key, entries in grouped:
                lines.append(f"【{key.split('|')[0]}】")
                for fv, _ in entries:
                    lines.append("　".join(str(v) for v in fv))
                lines.append("")
            self._fallback_label.setText("\n".join(lines))

    # ------------------------------------------------------------------ #
    # Export                                                               #
    # ------------------------------------------------------------------ #

    def _build_export_sorted_data(self) -> list:
        """Build sorted_data list compatible with WordGenerator / PdfGenerator."""
        result = []
        for group_key, entries in self._group_results():
            rows = [
                [_field_value(f, ann, name, attrs) for f in self._layout.field_names]
                for ann, name, attrs, _ in entries
            ]
            result.append((group_key, rows))
        return result

    def _export_word(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Word保存先を選択",
            f"年忌表_{self._target_year}.docx",
            "Word (*.docx)",
        )
        if not path:
            return
        try:
            from memorial_app.documents.word_generator import WordGenerator
            WordGenerator().create_combined_document(
                self._build_export_sorted_data(),
                self._layout.title,
                Path(path),
                field_names=self._layout.field_names,
                single_column=self._layout.single_column,
                auto_pdf=False,
                header_font_size=self._layout.header_font_size,
                entry_font_size=self._layout.entry_font_size,
            )
            QMessageBox.information(self, "完了", f"Word文書を保存しました:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "エラー", f"Word生成に失敗しました:\n{exc}")

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "PDF保存先を選択",
            f"年忌表_{self._target_year}.pdf",
            "PDF (*.pdf)",
        )
        if not path:
            return
        try:
            from memorial_app.documents.pdf_generator import PdfGenerator
            PdfGenerator().create_document(
                self._build_export_sorted_data(),
                self._layout.title,
                Path(path),
                field_names=self._layout.field_names,
                single_column=self._layout.single_column,
                header_font_size=self._layout.header_font_size,
                entry_font_size=self._layout.entry_font_size,
            )
            QMessageBox.information(self, "完了", f"PDFを保存しました:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "エラー", f"PDF生成に失敗しました:\n{exc}")
