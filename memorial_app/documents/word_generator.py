"""Word document generator for nenki anniversary tables.

Generates .docx files with vertical Japanese text (縦書き / tategaki),
landscape A4 orientation, and proper Japanese formatting.
Field values are padded to fixed widths so that columns align across entries.
Optionally converts to PDF via docx2pdf.
"""

from pathlib import Path
import unicodedata

from docx import Document
from docx.shared import Pt, Inches
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

        # Compute global field widths across ALL groups for consistent alignment
        all_entries = []
        for _, people_data in sorted_data:
            all_entries.extend(people_data)
        field_widths = self._compute_field_widths(all_entries, field_names)

        if single_column:
            # Single column: title + data, no columns
            self._add_title(doc, title)
            self._build_single_column_content(doc, sorted_data, field_names, field_widths)
        else:
            # Two columns on the section
            sectPr = section._sectPr
            cols = OxmlElement("w:cols")
            cols.set(qn("w:num"), "2")
            cols.set(qn("w:space"), "720")
            sectPr.append(cols)

            # Build: title_part1 → col1 data → col break → title_part2 → col2 data
            self._build_dual_column_content(doc, title, sorted_data, field_widths)

        doc.save(str(output_path))

        # Auto-convert to PDF
        self._convert_to_pdf(output_path)

    def _add_title(self, doc: Document, title: str):
        """Add full-width centered title (single column mode)."""
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(title)
        title_run.font.size = Pt(36)
        title_run.font.bold = True
        title_run.font.name = self.FONT_NAME
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_para.paragraph_format.space_after = Pt(4)

    def _split_title(self, title: str) -> tuple[str, str]:
        """Split title into two parts for dual-column display."""
        if " - " in title:
            return title.split(" - ", 1)
        if "\u3000" in title:
            idx = title.index("\u3000")
            return title[:idx], title[idx + 1:]
        mid = len(title) // 2
        return title[:mid], title[mid:]

    def _split_groups(self, sorted_data: list) -> tuple[list, list]:
        """Split nenki groups into two halves by entry count, keeping groups intact."""
        group_sizes = [len(people_data) + 1 for _, people_data in sorted_data]
        total = sum(group_sizes)
        half = total / 2

        running = 0
        split_idx = len(sorted_data)
        for i, size in enumerate(group_sizes):
            running += size
            if running >= half:
                split_idx = i + 1
                break

        return sorted_data[:split_idx], sorted_data[split_idx:]

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

    def _add_column_title(self, doc: Document, text: str):
        """Add a title paragraph for one column in dual-column mode."""
        para = doc.add_paragraph()
        run = para.add_run(text)
        run.font.size = Pt(36)
        run.font.bold = True
        run.font.name = self.FONT_NAME
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_after = Pt(4)
        return para

    def _add_column_groups(self, doc: Document, groups: list, field_widths: list[int]):
        """Add nenki groups (subtitle + entries) for one column."""
        for key, people_data in groups:
            nenki_name = key.split("|")[0]

            subtitle = doc.add_paragraph()
            subtitle_run = subtitle.add_run(nenki_name)
            subtitle_run.font.size = Pt(16)
            subtitle_run.font.bold = True
            subtitle_run.font.name = self.FONT_NAME
            subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
            subtitle.paragraph_format.space_after = Pt(8)

            for entry in people_data:
                text = self.FIELD_SEP + self._format_aligned_entry(entry, field_widths)
                para = doc.add_paragraph()
                run = para.add_run(text)
                run.font.size = Pt(11)
                run.font.name = self.FONT_NAME
                para.paragraph_format.left_indent = Inches(0.5)
                para.paragraph_format.space_after = Pt(4)

            # Space between groups
            doc.add_paragraph()

    def _add_column_break(self, doc: Document):
        """Insert a column break at the end of the last paragraph."""
        # Add column break to the last paragraph
        last_para = doc.paragraphs[-1]
        run = last_para.add_run()
        br = OxmlElement("w:br")
        br.set(qn("w:type"), "column")
        run._element.append(br)

    def _build_dual_column_content(
        self, doc: Document, title: str, sorted_data: list, field_widths: list[int],
    ):
        """Dual column layout: title_part1 → col1 data → break → title_part2 → col2 data."""
        title_part1, title_part2 = self._split_title(title)
        col1_groups, col2_groups = self._split_groups(sorted_data)

        # Column 1: title part 1 + data
        self._add_column_title(doc, title_part1)
        self._add_column_groups(doc, col1_groups, field_widths)

        # Column break to move to column 2
        self._add_column_break(doc)

        # Column 2: title part 2 + data
        self._add_column_title(doc, title_part2)
        self._add_column_groups(doc, col2_groups, field_widths)

    def _convert_to_pdf(self, docx_path: Path):
        """Try to convert .docx to .pdf using docx2pdf."""
        try:
            from docx2pdf import convert
            pdf_path = docx_path.with_suffix(".pdf")
            convert(str(docx_path), str(pdf_path))
        except Exception:
            pass
