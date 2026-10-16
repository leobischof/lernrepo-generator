"""Portable local PDF/audio reader, sourced only from current generated PDFs."""
import html
import json
import re
import shutil

from .artifacts import index, listed
from .build import assert_build_current
from .chapters import discover, prefix
from .io import digest, file_hash, read, write
from .jobs import approved
from .timeline import validate

MEDIA = {'.m4a', '.mp3', '.wav', '.ogg', '.opus', '.mp4', '.webm'}


def recordings(course, chapters=None):
    chapters = chapters or discover(course)
    by_id = {c['id']: c['number'] for c in chapters}
    found = {}
    configured = course.data.get('reader', {}).get('audio', {})
    for cid, relative in configured.items():
        if cid not in by_id:
            raise ValueError(f'Audio für unbekanntes Kapitel: {cid}')
        path = course.local(relative)
        if not path.is_file() or path.suffix.lower() not in MEDIA:
            raise ValueError(f'Audio fehlt oder Format unbekannt: {relative}')
        found[by_id[cid]] = path
    folder = course.root / 'audio'
    for path in sorted(folder.iterdir()) if folder.exists() else []:
        if not path.is_file() or path.suffix.lower() not in MEDIA or path in found.values():
            continue
        if not path.resolve().is_relative_to(course.root):
            raise ValueError('Audio verlässt das Kursrepo')
        match = re.match(re.escape(prefix(course)) + r'-(\d+)-', path.name)
        if not match or int(match[1]) not in by_id.values():
            raise ValueError(f'Audio ohne eindeutiges bekanntes Kapitel: {path.name}; reader.audio konfigurieren')
        number = int(match[1])
        if number in found:
            raise ValueError(f'Mehrere Audios für Kapitel {number}')
        found[number] = path
    return found


def run(course):
    import pymupdf
    approved(course)
    assert_build_current(course)
    current_pdfs = set(listed(course, course.root / 'build/pdf'))
    chapters = discover(course)
    if not chapters:
        raise ValueError('Keine Kapitel für den Reader')
    audio = recordings(course, chapters)
    source = course.root / 'interactive'
    vendor = source / 'node_modules/pdfjs-dist'
    if not (vendor / 'build/pdf.mjs').is_file():
        raise ValueError('PDF.js fehlt: npm ci --prefix interactive --ignore-scripts ausführen')
    planned, inputs = [], []
    for chapter in chapters:
        number = chapter['number']
        pdf = course.root / 'build/pdf' / (chapter['stem'] + '.pdf')
        if pdf not in current_pdfs:
            raise ValueError('Kapitel-PDF fehlt oder ist veraltet: render-pdf ausführen')
        media = audio.get(number)
        folder = f"{prefix(course)}-{number}-Kapitel"
        record = dict(number=number, title=chapter['title'], id=chapter['id'],
                      pdf=f'{folder}/{pdf.name}', pdf_sha256=file_hash(pdf),
                      audio=f'audio/{prefix(course)}-{number}-Audio{media.suffix.lower()}' if media else None,
                      audio_sha256=file_hash(media) if media else None,
                      media_type='video' if media and media.suffix.lower() in {'.mp4', '.webm'} else 'audio',
                      timeline=f'{folder}/{prefix(course)}-{number}-Timeline.json')
        path = course.root / f'curation/interactive/{prefix(course)}-{number}-Timeline.json'
        value = read(path, dict(version=1, chapter=number, pdf_sha256=record['pdf_sha256'],
                                audio_sha256=record['audio_sha256'], annotations=[]))
        inputs.extend([pdf, path])
        if media:
            inputs.append(media)
        with pymupdf.open(pdf) as doc:
            validate(value, record, pages=len(doc))
        planned.append((record, pdf, media, value))
    output = course.root / 'build/interactive'
    produced, shell = [], []

    def copy(source_path, name, static=False):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or file_hash(target) != file_hash(source_path):
            shutil.copy2(source_path, target)
        produced.append(target)
        if static:
            shell.append(name)

    for name in ('reader-app.mjs', 'reader-navigation.mjs', 'reader-offline.mjs', 'reader-timeline.mjs', 'reader.css', 'reader-icon.svg'):
        copy(source / name, name, True)
        inputs.append(source / name)
    inputs.extend([source / 'reader.html', source / 'reader-service-worker.mjs'])
    for relative in ('build/pdf.mjs', 'build/pdf.worker.mjs', 'web', 'cmaps', 'standard_fonts', 'wasm'):
        path = vendor / relative
        for file in sorted(path.rglob('*')) if path.is_dir() else [path]:
            if file.is_file():
                copy(file, 'vendor/' + file.relative_to(vendor).as_posix(), True)
    copy(vendor / 'LICENSE', 'vendor/PDFJS-LICENSE', True)
    licenses = course.root / 'curation/icon-library-licenses.txt'
    if licenses.is_file():
        copy(licenses, licenses.name, True)
    copy(course.root / 'pipeline/reader_serve.py', 'reader_serve.py')
    for record, pdf, media, value in planned:
        copy(pdf, record['pdf'])
        if media:
            copy(media, record['audio'])
        target = output / record['timeline']
        write(target, value)
        produced.append(target)
    course_info = {key: course.data['course'][key] for key in ('id', 'title', 'language') if key in course.data['course']}
    course_info['export_prefix'] = prefix(course)
    write(output / 'reader-manifest.json', dict(version=1, course=course_info, chapters=[item[0] for item in planned]))
    template = (source / 'reader.html').read_text(encoding='utf-8')
    write(output / 'reader.html', template.replace('__COURSE_TITLE__', html.escape(course_info['title']))
          .replace('__COURSE_PREFIX__', html.escape(prefix(course))))
    write(output / 'reader.webmanifest', dict(name=course_info['title'], short_name=prefix(course), start_url='./reader.html',
          scope='./', display='standalone', background_color='#edece7', theme_color='#275e49',
          icons=[dict(src='reader-icon.svg', sizes='any', type='image/svg+xml', purpose='any')]))
    shell.extend(['reader-manifest.json', 'reader.html', 'reader.webmanifest'])
    produced.extend(output / name for name in ['reader-manifest.json', 'reader.html', 'reader.webmanifest'])
    version = digest([(p.relative_to(output).as_posix(), file_hash(p)) for p in produced])[:16]
    worker = (source / 'reader-service-worker.mjs').read_text(encoding='utf-8').replace('__LEARNREPO_CACHE_VERSION__', version)
    write(output / 'reader-service-worker.mjs', worker)
    shell += ['reader-service-worker.mjs', 'reader-offline-index.json']
    write(output / 'reader-offline-index.json', dict(version=version, shell=sorted(shell)))
    write(output / 'Reader-starten.cmd', '@echo off\ncd /d "%~dp0"\npy -3 reader_serve.py --open\nif errorlevel 1 pause\n')
    write(output / 'Reader-Anleitung.txt', course_info['title'] + '\n\nStart: Reader-starten.cmd oder python reader_serve.py --open\n'
          'PDF und optionales Audio liegen lokal. Automatische Markierungen sind ungeprüft.\n'
          'Kapitel offline speichern lädt nur das gewählte Kapitel in diesen Browser.\n')
    produced.extend(output / name for name in ['reader-service-worker.mjs', 'reader-offline-index.json', 'Reader-starten.cmd', 'Reader-Anleitung.txt'])
    index(course, output, produced, inputs)
    return {'chapters': len(planned), 'audios': len(audio), 'directory': str(output)}
