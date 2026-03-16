"""Word document generator for nenki anniversary tables.

Generates .docx files with vertical Japanese text (縦書き / tategaki),
landscape A4 orientation, and proper Japanese formatting.
Field values are padded to fixed widths so that columns align across entries.
Optionally converts to PDF via docx2pdf.
"""

from pathlib import Path
import unicodedata

from docx import Document
from docx.shared import Pt, Inches, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def _display_width(text: str) -> int:
    """Calculate display width treating fullwidth/CJK chars as 2, others as 1."""
    w = 0
    for ch in text:
        eaw = unicodedata.east_asian_width(ch)
        w += 2 if eaw in ("F", "W", "A") else 1
    return w


def _pad_to_width(text: str, target_width: int) -> str:
    """Pad text with full-width spaces to reach target display width."""
    current = _display_width(text)
    # Each full-width space has display width 2
    needed = (target_width - current) // 2
    if needed > 0:
        return text + "\u3000" * needed
    return text


class WordGenerator:
    """Generate Word documents for nenki anniversary listings with vertical text."""

    FONT_NAME = "MS Mincho"
    # Full-width space used as field separator
    FIELD_SEP = "\u3000"

    def create_combined_document(
        self,
        sorted_data: list,
        title: str,
        output_path: Path,
        field_names: list[str] | None = None,
        single_column: bool = True,
    ):
        """Create a combined nenki document with vertical Japanese text.

        Args:
            sorted_data: List of (key, entries).
                key: "年忌名|years_offset"
                entries: list of field-value lists (ordered by field_names)
            title: Document title (e.g. "年忌表 - 令和八年の年忌法要")
            output_path: Path to save the .docx file.
            field_names: List of field names corresponding to each entry's values.
            single_column: True for single column, False for dual column layout.
        """
        doc = Document()

        section = doc.sections[0]
        self._setup_section(section)

        # Set default font
        style = doc.styles["Normal"]
        style.font.name = self.FONT_NAME
        rPr = style.element.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = rPr.makeelement(qn("w:rFonts"), {})
            rPr.insert(0, rFonts)
        rFonts.set(qn("w:eastAsia"), self.FONT_NAME)

        # Main title (always full page width)
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(title)
        title_run.font.size = Pt(36)
        title_run.font.bold = True
        title_run.font.name = self.FONT_NAME
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_para.paragraph_format.space_after = Pt(4)

        # Compute global field widths across ALL groups for consistent alignment
        all_entries = []
        for _, people_data in sorted_data:
            all_entries.extend(people_data)
        field_widths = self._compute_field_widths(all_entries, field_names)

        if single_column:
            self._build_single_column_content(doc, sorted_data, field_names, field_widths)
        else:
            self._build_dual_column_content(doc, sorted_data, field_widths)

        doc.save(str(output_path))

        # Auto-convert to PDF
        self._convert_to_pdf(output_path)

    def _setup_section(self, section):
        """Configure a section with landscape A4, tategaki, and margins."""
        section.page_width = Inches(11.69)
        section.page_height = Inches(8.27)
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

        # Set vertical text direction (tategaki)
        sectPr = section._sectPr
        textDirection = OxmlElement("w:textDirection")
        textDirection.set(qn("w:val"), "tbRl")
        sectPr.append(textDirection)

    def _compute_field_widths(self, all_entries: list, field_names: list[str] | None) -> list[int]:
        """Compute the max display width for each field position across all entries."""
        if not all_entries:
            return []
        num_fields = len(all_entries[0]) if all_entries else 0
        widths = [0] * num_fields

        for entry in all_entries:
            for i, val in enumerate(entry):
                w = _display_width(str(val) if val else "")
                if w > widths[i]:
                    widths[i] = w

        # Round up each width to even number (full-width space alignment)
        widths = [w + (w % 2) for w in widths]
        return widths

    def _format_aligned_entry(self, entry: list, field_widths: list[int]) -> str:
        """Format entry fields padded to fixed widths for alignment."""
        parts = []
        for i, val in enumerate(entry):
            text = str(val) if val else ""
            if i < len(field_widths):
                text = _pad_to_width(text, field_widths[i])
            parts.append(text)
        return self.FIELD_SEP.join(parts)

    def _build_single_column_content(
        self, doc: Document, sorted_data: list,
        field_names: list[str] | None, field_widths: list[int],
    ):
        """Single column layout: each nenki group with subtitle + entries."""
        for key, people_data in sorted_data:
            nenki_name = key.split("|")[0]

            subtitle = doc.add_paragraph()
            subtitle_run = subtitle.add_run(nenki_name)
            subtitle_run.font.size = Pt(28)
            subtitle_run.font.bold = True
            subtitle_run.font.name = self.FONT_NAME
            subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
            subtitle.paragraph_format.space_after = Pt(12)

            for entry in people_data:
                text = self.FIELD_SEP + self._format_aligned_entry(entry, field_widths)
                para = doc.add_paragraph()
                run = para.add_run(text)
                run.font.size = Pt(18)
                run.font.name = self.FONT_NAME
                para.paragraph_format.left_indent = Inches(1.5)
                para.paragraph_format.space_after = Pt(8)

            # Space between groups
            doc.add_paragraph()

    def _build_dual_column_content(
        self, doc: Document, sorted_data: list, field_widths: list[int],
    ):
        """Dual column layout using a borderless table with 2 cells.

        Splits nenki groups across two columns by total entry count,
        keeping each group intact in one column.
        """
        # Count total entries per group to split evenly
        group_sizes = []
        for key, people_data in sorted_data:
            # +1 for the subtitle line
            group_sizes.append(len(people_data) + 1)

        total = sum(group_sizes)
        half = total / 2

        # Find split point: keep groups intact
        running = 0
        split_idx = len(sorted_data)
        for i, size in enumerate(group_sizes):
            running += size
            if running >= half:
                split_idx = i + 1
                break

        col1_groups = sorted_data[:split_idx]
        col2_groups = sorted_data[split_idx:]

        # Create borderless table with 1 row, 2 cells
        usable_width = Inches(11.69) - Inches(1.0)  # page width minus margins
        col_width_twips = int(usable_width / 2 / 635)  # EMU to twips
        table = doc.add_table(rows=1, cols=2)
        table.autofit = False

        # Remove all borders
        tbl = table._tbl
        tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = OxmlElement(f"w:{ edge}")
            el.set(qn("w:val"), "none")
            el.set(qn("w:sz"), "0")
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), "auto")
            borders.append(el)
        tblPr.append(borders)

        # Set column widths
        for col_idx in range(2):
            cell = table.cell(0, col_idx)
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            tcW = OxmlElement("w:tcW")
            tcW.set(qn("w:w"), str(col_width_twips))
            tcW.set(qn("w:type"), "dxa")
            tcPr.append(tcW)

        # Fill column 1
        self._fill_table_cell(table.cell(0, 0), col1_groups, field_widths)
        # Fill column 2
        self._fill_table_cell(table.cell(0, 1), col2_groups, field_widths)

    def _fill_table_cell(self, cell, groups: list, field_widths: list[int]):
        """Fill a table cell with nenki groups (subtitle + entries)."""
        # Remove the default empty paragraph
        for p in cell.paragraphs:
            p._element.getparent().remove(p._element)

        for group_idx, (key, people_data) in enumerate(groups):
            nenki_name = key.split("|")[0]

            # Subtitle
            subtitle = OxmlElement("w:p")
            subtitle_pPr = OxmlElement("w:pPr")
            subtitle_jc = OxmlElement("w:jc")
            subtitle_jc.set(qn("w:val"), "center")
            subtitle_pPr.append(subtitle_jc)

            # Space after subtitle
            spacing = OxmlElement("w:spacing")
            spacing.set(qn("w:after"), "160")  # ~8pt
            subtitle_pPr.append(spacing)

            subtitle.append(subtitle_pPr)
            subtitle_run = OxmlElement("w:r")
            subtitle_rPr = OxmlElement("w:rPr")
            subtitle_sz = OxmlElement("w:sz")
            subtitle_sz.set(qn("w:val"), "32")  # 16pt * 2 = 32 half-points
            subtitle_rPr.append(subtitle_sz)
            subtitle_b = OxmlElement("w:b")
            subtitle_rPr.append(subtitle_b)
            subtitle_font = OxmlElement("w:rFonts")
            subtitle_font.set(qn("w:ascii"), self.FONT_NAME)
            subtitle_font.set(qn("w:eastAsia"), self.FONT_NAME)
            subtitle_font.set(qn("w:hAnsi"), self.FONT_NAME)
            subtitle_rPr.append(subtitle_font)
            subtitle_run.append(subtitle_rPr)
            subtitle_text = OxmlElement("w:t")
            subtitle_text.text = nenki_name
            subtitle_run.append(subtitle_text)
            subtitle.append(subtitle_run)
            cell._tc.append(subtitle)

            # Entries
            for entry in people_data:
                text = self.FIELD_SEP + self._format_aligned_entry(entry, field_widths)

                para = OxmlElement("w:p")
                pPr = OxmlElement("w:pPr")
                # Left indent
                ind = OxmlElement("w:ind")
                ind.set(qn("w:left"), "720")  # ~0.5 inch
                pPr.append(ind)
                # Space after
                sp = OxmlElement("w:spacing")
                sp.set(qn("w:after"), "80")  # ~4pt
                pPr.append(sp)
                para.append(pPr)

                run = OxmlElement("w:r")
                rPr = OxmlElement("w:rPr")
                sz = OxmlElement("w:sz")
                sz.set(qn("w:val"), "22")  # 11pt * 2 = 22 half-points
                rPr.append(sz)
                font = OxmlElement("w:rFonts")
                font.set(qn("w:ascii"), self.FONT_NAME)
                font.set(qn("w:eastAsia"), self.FONT_NAME)
                font.set(qn("w:hAnsi"), self.FONT_NAME)
                rPr.append(font)
                run.append(rPr)
                t = OxmlElement("w:t")
                t.set(qn("xml:space"), "preserve")
                t.text = text
                run.append(t)
                para.append(run)
                cell._tc.append(para)

            # Spacer between groups (except after last)
            if group_idx < len(groups) - 1:
                spacer = OxmlElement("w:p")
                sp_pPr = OxmlElement("w:pPr")
                sp_spacing = OxmlElement("w:spacing")
                sp_spacing.set(qn("w:after"), "0")
                sp_pPr.append(sp_spacing)
                spacer.append(sp_pPr)
                cell._tc.append(spacer)

    def _convert_to_pdf(self, docx_path: Path):
        """Try to convert .docx to .pdf using docx2pdf."""
        try:
            from docx2pdf import convert
            pdf_path = docx_path.with_suffix(".pdf")
            convert(str(docx_path), str(pdf_path))
        except Exception:
            pass
