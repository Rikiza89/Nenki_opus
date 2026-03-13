"""PDF document generator for nenki anniversary tables.

Generates PDF files with Japanese text using reportlab with CID fonts.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# CID font for Japanese text (bundled with reportlab, no external font files needed)
_FONT_REGISTERED = False


def _ensure_fonts():
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        _FONT_REGISTERED = True


class PdfGenerator:
    """Generate PDF documents for nenki anniversary listings."""

    FONT_MINCHO = "HeiseiMin-W3"
    FONT_GOTHIC = "HeiseiKakuGo-W5"

    def __init__(self):
        _ensure_fonts()
        self._styles = self._build_styles()

    def _build_styles(self) -> dict:
        """Create paragraph styles for the document."""
        base = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "NenkiTitle",
            parent=base["Title"],
            fontName=self.FONT_GOTHIC,
            fontSize=16,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=12,
        )

        section_style = ParagraphStyle(
            "NenkiSection",
            parent=base["Heading2"],
            fontName=self.FONT_GOTHIC,
            fontSize=11,
            leading=15,
            textColor=HexColor("#2C3E50"),
            spaceBefore=10,
            spaceAfter=6,
        )

        cell_style = ParagraphStyle(
            "NenkiCell",
            parent=base["Normal"],
            fontName=self.FONT_MINCHO,
            fontSize=9,
            leading=12,
            alignment=TA_LEFT,
        )

        header_cell_style = ParagraphStyle(
            "NenkiHeaderCell",
            parent=base["Normal"],
            fontName=self.FONT_GOTHIC,
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
        )

        return {
            "title": title_style,
            "section": section_style,
            "cell": cell_style,
            "header_cell": header_cell_style,
        }

    def create_document(
        self,
        sorted_data: list,
        title: str,
        output_path: Path,
    ):
        """Create a PDF nenki document.

        Args:
            sorted_data: List of (key, entries) from ResultsPage._get_sorted_data().
            title: Document title.
            output_path: Path to save the PDF.
        """
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
        )

        elements = []

        # Title
        elements.append(Paragraph(title, self._styles["title"]))
        elements.append(Spacer(1, 6 * mm))

        # Each nenki group
        for key, entries in sorted_data:
            nenki_name, _, death_info = key.split("|", 2)

            # Section header
            header_text = f"■ {nenki_name}　{death_info}"
            elements.append(Paragraph(header_text, self._styles["section"]))

            # Build table data
            table_data = [
                [
                    Paragraph("氏名", self._styles["header_cell"]),
                    Paragraph("法名", self._styles["header_cell"]),
                    Paragraph("法要日", self._styles["header_cell"]),
                ],
            ]

            for name, display_name, date_str in entries:
                bname = display_name if display_name != name else ""
                table_data.append([
                    Paragraph(name, self._styles["cell"]),
                    Paragraph(bname, self._styles["cell"]),
                    Paragraph(date_str, self._styles["cell"]),
                ])

            # Available width
            page_width = A4[0] - 5 * cm  # left + right margins
            col_widths = [page_width * 0.30, page_width * 0.35, page_width * 0.35]

            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#D5D8DC")),
                ("FONTNAME", (0, 0), (-1, 0), self.FONT_GOTHIC),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                # Data rows
                ("FONTNAME", (0, 1), (-1, -1), self.FONT_MINCHO),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#BDC3C7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                # Alternating row colors
                *[
                    ("BACKGROUND", (0, i), (-1, i), HexColor("#F8F9FA"))
                    for i in range(2, len(table_data), 2)
                ],
            ]))

            elements.append(table)
            elements.append(Spacer(1, 8 * mm))

        doc.build(elements)
