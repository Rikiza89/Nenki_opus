"""HTML preview renderer for the visual editor.

Pure function — no Qt dependency. Builds a self-contained HTML document that
renders Japanese vertical text (tategaki) using CSS writing-mode.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field


@dataclass
class LayoutSettings:
    title: str = "年忌表"
    single_column: bool = True
    header_font_size: int = 28   # points
    entry_font_size: int = 18    # points
    field_names: list[str] = field(default_factory=list)


def build_html(grouped_data: list, layout: LayoutSettings) -> str:
    """Return a self-contained HTML string for the document preview.

    Args:
        grouped_data: [(group_key, [(field_values, person_id), ...])]
            group_key: "年忌名|years_offset|death_year_era"
            field_values: list of strings (one per selected field)
        layout: Current layout settings.
    """
    # CSS font sizes: pt → px at ~96dpi (1pt ≈ 1.333px)
    h_px = round(layout.header_font_size * 1.333)
    e_px = round(layout.entry_font_size * 1.333)
    col_class = "" if layout.single_column else "col2"

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
  .page {{
    background: white;
    box-shadow: 0 4px 20px rgba(0, 0, 0, .4);
    width: 1122px;
    min-height: 794px;
    padding: 48px;
    display: flex;
    flex-direction: column;
  }}
  .doc-title {{
    writing-mode: horizontal-tb;
    text-align: center;
    font-size: {h_px + 10}px;
    font-weight: bold;
    margin-bottom: 16px;
    color: #1a1a1a;
    padding-bottom: 8px;
    border-bottom: 2px solid #2c3e50;
  }}
  .content {{
    writing-mode: vertical-rl;
    text-orientation: mixed;
    flex: 1;
    overflow-x: auto;
    overflow-y: hidden;
  }}
  .content.col2 {{
    columns: 2;
    column-fill: auto;
    height: 660px;
  }}
  .group {{
    break-inside: avoid-column;
    margin-left: 20px;
  }}
  .header {{
    font-size: {h_px}px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 10px;
    color: #1a1a1a;
    padding: 4px 0;
    border-right: 3px solid #2c3e50;
  }}
  .entry {{
    font-size: {e_px}px;
    margin-bottom: 4px;
    padding-right: 16px;
    color: #222;
  }}
</style>
</head>
<body>
<div class="page">
  <div class="doc-title">{_html.escape(layout.title)}</div>
  <div class="content {col_class}">
    {groups_html}
  </div>
</div>
</body>
</html>"""
