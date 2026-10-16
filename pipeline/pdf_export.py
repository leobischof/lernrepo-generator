"""Direct local PDFs with tables, math, own SVGs, bookmarks and source labels."""
import hashlib
import html
import re

from .artifacts import index
from .build import assert_build_current
from .chapter_exports import guides, script
from .chapters import discover, prefix
from .io import digest, file_hash, read, write
from .jobs import approved

CSS = '''body{font-family:sans-serif;font-size:10.5pt;line-height:1.45;color:#202020}
h1{font-size:22pt}h2{font-size:16pt}h3{font-size:12pt}table{border-collapse:collapse;width:100%}
td,th{border:0.5pt solid #999;padding:5pt}th{background:#eee}img{max-width:100%}
.figure{page-break-inside:avoid}code,pre{font-family:monospace}'''


def convert(text, course, assets, problems):
    import markdown
    import pymupdf
    placeholders = {}

    def keep(value):
        key = f'LEARNREPOASSET{len(placeholders)}END'
        placeholders[key] = value
        return key

    def formula(match):
        from .pdf_math import render_formula
        source = match[1].strip()
        images = render_formula(source)
        if images is None:
            problems.append(f'Formel als Quelltext erhalten: {source}')
            return keep('<code>' + html.escape(source) + '</code>')
        tags = []
        for image in images:
            name = 'math-' + hashlib.sha256(image.png).hexdigest()[:16] + '.png'
            assets[name] = image.png
            width = min(450, image.width_pt)
            tags.append(f'<img src="{name}" width="{width}"/>')
        return keep('<span>' + ''.join(tags) + '</span>')

    text = re.sub(r'\$\$(.+?)\$\$', formula, text, flags=re.S)
    text = re.sub(r'(?<![\\$])\$([^$\n]+?)\$(?!\$)', formula, text)

    def image(match):
        label, target = match.groups()
        # Only curated reconstructions are redistributable; never original crops.
        fid = target.rsplit('/', 1)[-1].split('.')[0].removesuffix('-blank')
        path = course.path('figures') / f'{fid}.svg'
        if not path.is_file():
            problems.append(f'Abbildung ohne Rekonstruktion: {label}')
            return keep('<p>Abbildung: ' + html.escape(label) + ' (Rekonstruktion fehlt)</p>')
        from .svg_mupdf import for_mupdf
        data = for_mupdf(path.read_bytes())
        with pymupdf.open(stream=data, filetype='svg') as svg:
            pixmap = svg[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=True)
            name = f'figure-{file_hash(path)[:16]}.png'
            assets[name] = pixmap.tobytes('png')
            width = min(450, svg[0].rect.width)
        return keep(f'<div class="figure"><img src="{name}" width="{width}"/><p>{html.escape(label)}</p></div>')

    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', image, text)
    output = markdown.markdown(html.escape(text), extensions=['tables', 'sane_lists', 'footnotes'])
    for key, value in placeholders.items():
        output = output.replace(key, value)
    return output


def render(course, title, text, target):
    import pymupdf
    assets, problems, headings = {}, [], []
    body = convert(text, course, assets, problems)
    archive = pymupdf.Archive()
    for name, data in assets.items():
        archive.add(data, name)
    story = pymupdf.Story(html='<h1>' + html.escape(title) + '</h1>' + body, user_css=CSS, archive=archive)
    media = pymupdf.paper_rect('a4')
    content = media + (42, 42, -42, -48)

    def position(item):
        if item.heading and item.open_close & 1:
            headings.append((item.heading, item.text or title, item.page_num))

    doc = story.write_with_links(lambda *_: (media, content, None), positionfn=position)
    if len(doc) > 2000:
        doc.close()
        raise ValueError('PDF-Layout überschreitet 2000 Seiten')
    outline, previous = [], 0
    for level, label, page in headings:
        level = min(level, previous + 1)
        outline.append([level, label, page])
        previous = level
    doc.set_toc(outline or [[1, title, 1]])
    doc.set_metadata({'title': title, 'creator': 'Lernrepo-Generator', 'subject': 'Lernunterlage; Quellen- und KI-Schichten beachten'})
    for n, page in enumerate(doc, 1):
        page.insert_text((42, media.height - 25), f'{n} / {len(doc)}', fontsize=8)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(doc.tobytes(garbage=4, deflate=True, no_new_id=True))
    doc.close()
    return problems


def run(course):
    approved(course)
    assert_build_current(course)
    output, produced, problems = course.root / 'build/pdf', [], []
    stamps = read(output / '.pdf-stamps.json', {})
    figures = {p.name: file_hash(p) for p in course.path('figures').glob('*.svg')}
    tasks, complete_parts = [], []
    chapters = discover(course)
    for chapter in chapters:
        body = script(course, chapter['sections'])
        related = [f for f in read(course.path('structure')).get('figures', []) if any(
            s['id'] in chapter['sections'] and s['source'] == f['source'] and f['page'] in s['pages']
            for s in read(course.path('structure'))['sections'])]
        body += '\n\n' + '\n\n'.join(f"![{f.get('title', f['id'])}](figures/reconstructed/{f['id']}.svg)" for f in related)
        complete_parts.append(body)
        tasks.append((chapter['stem'], chapter['title'], body))
        tasks.append((chapter['stem'] + '-Zusammenfassung', chapter['title'] + ' – KI-Lernleitfaden', guides(course, chapter['sections'])))
    tasks.extend([(prefix(course) + '-Gesamtskript', course.data['course']['title'], '\n\n'.join(complete_parts)),
                  (prefix(course) + '-Musterloesungen', 'Musterlösungen – KI-Erklärung, ungeprüft',
                   (course.path('learning') / 'musterloesungen.md').read_text(encoding='utf-8'))])
    for name, title, body in tasks:
        path = output / f'{name}.pdf'
        key = digest({'version': 1, 'title': title, 'body': body, 'figures': figures})
        if not path.exists() or stamps.get(name, {}).get('key') != key or stamps[name].get('sha256') != file_hash(path):
            problems.extend(render(course, title, body, path))
            stamps[name] = {'key': key, 'sha256': file_hash(path)}
        produced.append(path)
    write(output / '.pdf-stamps.json', stamps)
    index(course, output, produced, [course.path('figures') / f"{f['id']}.svg"
                                   for f in read(course.path('structure')).get('figures', [])])
    write(course.path('reports') / 'pdf-export.md', '# PDF-Export\n\nLayout benötigt Sichtprüfung.\n\n' + '\n'.join(problems) + '\n')
    return {'chapters': len(chapters), 'files': len(produced), 'warnings': problems}
