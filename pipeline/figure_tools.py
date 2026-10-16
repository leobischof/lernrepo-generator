"""Unreviewed region proposals and explicitly licensed local SVG icons."""
from copy import deepcopy
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .io import file_hash, read, write

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)


def safe_svg(text):
    root = ET.fromstring(text)
    allowed = {'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon',
               'text', 'tspan', 'title', 'desc', 'defs', 'clipPath', 'linearGradient', 'radialGradient', 'stop', 'marker', 'symbol', 'use', 'style'}
    for element in root.iter():
        if element.tag.split('}')[-1] not in allowed:
            raise ValueError('Nicht erlaubter Inhalt in SVG')
        for key, value in element.attrib.items():
            key = key.split('}')[-1].lower()
            urls = re.findall(r'url\((.*?)\)', value, flags=re.I)
            if (key.startswith('on') or key == 'src' or key == 'href' and not value.startswith('#')
                    or any(not url.strip().strip('\"\'').startswith('#') for url in urls)
                    or '<' in value or 'javascript:' in value.lower()):
                raise ValueError('Aktiver oder externer SVG-Inhalt ist nicht erlaubt')
        if element.tag.split('}')[-1] == 'style' and element.text:
            if '@' in element.text or 'url(' in element.text.lower() or 'javascript:' in element.text.lower():
                raise ValueError('Externe SVG-Styles sind nicht erlaubt')
    if root.tag.split('}')[-1] != 'svg':
        raise ValueError('SVG-Wurzel fehlt')
    return root


def detect(course):
    import pymupdf
    candidates = []
    for sid, entry in read(course.path('manifest'))['sources'].items():
        if Path(entry['spec']['path']).suffix.lower() != '.pdf':
            continue
        source = course.path('originals') / f'{sid}.pdf'
        with pymupdf.open(source) as doc:
            for number, page in enumerate(doc, 1):
                regions = [(info['bbox'], 'raster') for info in page.get_image_info()]
                regions.extend((list(rect), 'vector') for rect in page.cluster_drawings())
                seen = set()
                for bounds, kind in regions:
                    rect = pymupdf.Rect(bounds) & page.rect
                    key = tuple(round(v, 2) for v in rect)
                    if rect.is_empty or rect.width < 12 or rect.height < 12 or key in seen:
                        continue
                    seen.add(key)
                    candidates.append(dict(id=f'candidate-{len(candidates)+1}', source=sid, page=number,
                                           bbox=list(key), kind=kind, status='unreviewed',
                                           reason='Bild-/Vektorgeometrie; Bedeutung und Grenzen visuell prüfen'))
    write(course.path('reports') / 'figure-candidates.json', candidates)
    return {'candidates': len(candidates)}


def icons(course):
    library = {}
    for item in read(course.root / 'curation/icon-library.json', {'icons': []})['icons']:
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in ('id', 'license', 'copyright', 'source', 'path')):
            raise ValueError('Jedes Icon braucht ID, Quelle, Lizenz und Copyright')
        if item['id'] in library:
            raise ValueError('Doppelte Icon-ID')
        source = course.local(item['path'])
        library[item['id']] = (item, safe_svg(source.read_text(encoding='utf-8')), file_hash(source))
    embedded, provenance, outputs = 0, [], []
    for target in sorted(course.path('figures').glob('*.svg')):
        root = safe_svg(target.read_text(encoding='utf-8'))
        changed = False
        for group in root.iter():
            name = group.get('data-icon')
            if not name:
                continue
            if name not in library:
                raise ValueError(f'Icon fehlt in der lizenzierten Bibliothek: {name}')
            item, icon, fingerprint = library[name]
            for child in list(group):
                group.remove(child)
            nested = deepcopy(icon)
            nested.set('width', group.get('data-width', '24'))
            nested.set('height', group.get('data-height', '24'))
            group.append(nested)
            description = ET.SubElement(group, f'{{{NS}}}desc')
            description.text = f"{item['copyright']}; {item['license']}; {item['source']}"
            provenance.append({**item, 'sha256': fingerprint, 'figure': target.name})
            embedded += 1
            changed = True
        if changed:
            outputs.append((target, ET.tostring(root, encoding='unicode') + '\n'))
    for path, body in outputs:
        write(path, body)
    write(course.root / 'curation/icon-provenance.json', provenance)
    write(course.root / 'curation/icon-library-licenses.txt', '\n\n'.join(
        f"{item['id']}: {item['license']}\n{item['copyright']}\n{item['source']}" for item, _, _ in library.values()) + '\n')
    return {'embedded': embedded}
