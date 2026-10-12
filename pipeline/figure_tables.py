"""Readable native SVG tables from reviewed source transcriptions."""
import math
import textwrap
from html import escape


def table_svg(title, columns, rows, source, weights=None):
    if len(columns) < 2 or not rows or any(len(row) != len(columns) for row in rows):
        raise ValueError('Tabelle braucht mindestens zwei Spalten und vollständige Zeilen')
    weights = weights or [1] * len(columns)
    if len(weights) != len(columns) or any(not isinstance(w, (int,float)) or not math.isfinite(w) or w <= 0 for w in weights):
        raise ValueError('Ungültige Tabellenbreiten')
    widths = [1520*w/sum(weights) for w in weights]
    font, line_height = 19, 25
    def wrapped(row):
        return [textwrap.wrap(str(cell),width=max(5,int((width-24)/(font*.56))),break_long_words=False) or ['']
                for cell,width in zip(row,widths)]
    content=[];y=100
    for index,row in enumerate([columns]+rows):
        lines=wrapped(row);height=max(len(cell) for cell in lines)*line_height+24;x=20
        for col,(width,cell) in enumerate(zip(widths,lines)):
            fill='#e5edf5' if index==0 else ('#f6f8fa' if index%2 else '#ffffff')
            content.append(f'<rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="{height}" fill="{fill}" stroke="#8090a0"/>')
            css=' class="answer"' if index and col else ''
            for n,line in enumerate(cell):
                content.append(f'<text{css} x="{x+12:.2f}" y="{y+29+n*line_height}" font-weight="{600 if index==0 else 400}">{escape(line)}</text>')
            x+=width
        y+=height
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1560" height="{y+70}" viewBox="0 0 1560 {y+70}" role="img" aria-label="{escape(title,quote=True)}">'
            '<style>text{font-family:Arial,sans-serif;font-size:19px;fill:#172b3a}</style>'
            f'<rect width="1560" height="{y+70}" fill="white"/><text x="20" y="42" style="font-size:28px;font-weight:700">{escape(title)}</text>'
            '<text x="20" y="76">Tabelleninhalt nach Original; Layout für das Lernen neu gesetzt.</text>'
            +''.join(content)+f'<text x="20" y="{y+42}">{escape(source)}</text></svg>')
