"""HTML preview renderer for the visual editor.

Pure function — no Qt dependency. Builds a self-contained HTML document that
renders Japanese vertical text (tategaki) using CSS writing-mode to match
the Word output layout as closely as possible:
  • title is the rightmost vertical column (flex-direction: row-reverse)
  • body text flows top-to-bottom, columns advance right-to-left
  • optional 2-column layout via CSS column-count
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field


@dataclass
class LayoutSettings:
    title: str = "年忌表"
    single_column: bool = True
    header_font_size: int = 28   # points — matches Word single-column default
    entry_font_size: int = 18    # points — matches Word single-column default
    field_names: list[str] = field(default_factory=list)


# Title is always 36pt in Word (hardcoded in word_generator); keep preview in sync.
_TITLE_PT = 36


def build_html(grouped_data: list, layout: LayoutSettings) -> str:
    """Return a self-contained HTML string for the document preview.

    The layout mirrors the Word tategaki output:
      right side  → title column
      left area   → data columns (1 or 2)

    Args:
        grouped_data: [(group_key, [(field_values, person_id), ...])]
            group_key: "年忌名|years_offset|death_year_era"
            field_values: list of strings (one per selected field)
        layout: Current layout settings.
    """
    # pt → px at 96 dpi (1 pt ≈ 1.333 px)
    title_px = round(_TITLE_PT * 1.333)
    h_px = round(layout.header_font_size * 1.333)
    e_px = round(layout.entry_font_size * 1.333)
    col2_class = "col2" if not layout.single_column else ""

    groups_html_parts: list[str] = []
    for group_key, entries in grouped_data:
        parts = group_key.split("|")
        nenki_name = parts[0]
        death_year = parts[2] if len(parts) >= 3 else ""
        header_text = f"{nenki_name}　{death_year}" if death_year else nenki_name

        entry_divs = []
        for field_values, *_ in entries:
            text = "　".join(str(v) for v in field_values if v is not None and v != "")
            entry_divs.append(f'<div class="entry">{_html.escape(text)}</div>')

        groups_html_parts.append(
            f'<div class="group">'
            f'<div class="header">{_html.escape(header_text)}</div>'
            f'{"".join(entry_divs)}'
            f'</div>'
        )

    groups_html = "\n".join(groups_html_parts)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #7f8c8d;
    display: flex;
    justify-content: center;
    padding: 20px;
    min-height: 100vh;
    font-family: 'MS Mincho', 'Yu Mincho', 'Noto Serif JP', serif;
  }}

  /* ---- Page shell: landscape A4 at 96 dpi ---- */
  .page {{
    background: white;
    box-shadow: 0 4px 20px rgba(0, 0, 0, .4);
    width: 1122px;
    height: 794px;
    padding: 48px;
    /* row-reverse: first child (title) goes to the RIGHT */
    display: flex;
    flex-direction: row-reverse;
    gap: 0;
    overflow: hidden;
  }}

  /* ---- Title column: rightmost, vertical text ---- */
  .title-col {{
    writing-mode: vertical-rl;
    text-align: center;
    font-size: {title_px}px;
    font-weight: bold;
    color: #1a1a1a;
    flex-shrink: 0;
    padding: 0 14px;
    /* separator line between title and data */
    border-left: 2px solid #2c3e50;
  }}

  /* ---- Data area: fills the left, tategaki ---- */
  .data-col {{
    writing-mode: vertical-rl;
    text-orientation: mixed;
    flex: 1;
    height: 100%;
    overflow: hidden;
  }}
  /* Two-column: CSS columns advance right-to-left in writing-mode: vertical-rl */
  .data-col.col2 {{
    column-count: 2;
    column-fill: auto;
  }}

  /* ---- Nenki group ---- */
  .group {{
    break-inside: avoid-column;
    margin-left: 16px;
  }}
  .header {{
    font-size: {h_px}px;
    font-weight: bold;
    text-align: center;
    color: #1a1a1a;
    padding: 4px 0;
    border-right: 3px solid #2c3e50;
    margin-bottom: 8px;
  }}
  .entry {{
    font-size: {e_px}px;
    padding-right: 14px;
    color: #222;
    margin-bottom: 4px;
  }}
</style>
</head>
<body>
<div class="page">
  <div class="title-col">{_html.escape(layout.title)}</div>
  <div class="data-col {col2_class}">
    {groups_html}
  </div>
</div>
</body>
</html>"""
