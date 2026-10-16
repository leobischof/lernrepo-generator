"""Self-contained chapter HTML from verified reader assets."""
import base64
import json
import mimetypes
import re
from pathlib import Path
from .artifacts import index, listed
from .chapters import discover
from .io import read, write

def encoded(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")

def inline_css(text: str, directory: Path) -> str:
    def replace(match):
        target = match[2].strip()
        if target.startswith(("data:","#")):
            return match[0]
        path = (directory / target).resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError(f"CSS-Ressource kann nicht eingebettet werden: {target}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return f'url("data:{mime};base64,{encoded(path)}")'
    return re.sub(r"url\(\s*(['\"]?)([^)'\"]+)\1\s*\)",replace,text)

def render_html(template: str,css: str,boot: str,payload: dict,licenses: dict) -> str:
    template = re.sub(r'\s*<link[^>]+rel="(?:stylesheet|manifest|apple-touch-icon|icon)"[^>]*>',"",template)
    template = template.replace("</head>",f"<style>{css}</style>\n</head>")
    template = template.replace('href="reader.html"','href="#"')
    data = json.dumps(payload,ensure_ascii=False,separators=(",",":")).replace("<","\\u003c")
    rights = json.dumps(licenses,ensure_ascii=False).replace("<","\\u003c")
    return template.replace('<script type="module" src="reader-app.mjs"></script>',
        f'<script type="application/json" id="lernrepo-licenses">{rights}</script>\n'
        f'<script type="application/json" id="lernrepo-payload">{data}</script>\n'
        f'<script type="module">{boot}</script>')


def run(course):
    root = course.root / 'build/interactive'
    if not listed(course, root):
        raise ValueError('Reader fehlt; zuerst interactive ausführen')
    manifest = read(root / 'reader-manifest.json')
    chapters = {chapter['number']: chapter for chapter in discover(course)}
    sources = dict(core=root / 'vendor/build/pdf.mjs', worker=root / 'vendor/build/pdf.worker.mjs',
                   viewer=root / 'vendor/web/pdf_viewer.mjs', app=root / 'reader-app.mjs',
                   timeline=root / 'reader-timeline.mjs', navigation=root / 'reader-navigation.mjs', offline=root / 'reader-offline.mjs')
    modules = {key: encoded(path) for key, path in sources.items()}
    binary = {kind: {p.name: encoded(p) for p in (root / 'vendor' / folder).iterdir() if p.is_file()}
              if (root / 'vendor' / folder).is_dir() else {}
              for kind, folder in [('cMapUrl', 'cmaps'), ('standardFontDataUrl', 'standard_fonts'), ('wasmUrl', 'wasm')]}
    css = inline_css((root / 'vendor/web/pdf_viewer.css').read_text(encoding='utf-8'), root / 'vendor/web') + '\n' + (root / 'reader.css').read_text(encoding='utf-8')
    template = (root / 'reader.html').read_text(encoding='utf-8')
    boot = (course.root / 'interactive/reader-singlefile-boot.mjs').read_text(encoding='utf-8')
    licenses = {p.name: p.read_text(encoding='utf-8') for p in [root / 'vendor/PDFJS-LICENSE', root / 'icon-library-licenses.txt'] if p.is_file()}
    output, produced = course.root / 'build/standalone', []
    for record in manifest['chapters']:
        payload = dict(manifest={**manifest, 'chapters': [record]}, timeline=read(root / record['timeline']),
                       modules=modules, binary=binary, pdf=encoded(root / record['pdf']),
                       audio=encoded(root / record['audio']) if record['audio'] else None,
                       audio_mime=mimetypes.guess_type(record['audio'] or '')[0] or 'audio/mp4')
        path = output / (chapters[record['number']]['stem'] + '-Lernreader.html')
        write(path, render_html(template, css, boot, payload, licenses))
        produced.append(path)
    index(course, output, produced, [root / 'artifact-index.json', course.root / 'interactive/reader-singlefile-boot.mjs'])
    return {'chapters': len(produced), 'directory': str(output)}
