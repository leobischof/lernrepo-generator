"""Deterministic local packages from verified positive artifact lists only."""
import zipfile

from .artifacts import listed
from .build import assert_build_current
from .chapters import prefix
from .io import write
from .jobs import approved


def zip_files(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, source in sorted(files):
            entry = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            with archive.open(entry, 'w') as target, source.open('rb') as stream:
                while block := stream.read(1024 * 1024):
                    target.write(block)


def run(course):
    approved(course)
    assert_build_current(course)
    groups = {}
    for folder in ('exports', 'notebooklm', 'pdf', 'anki', 'interactive', 'standalone'):
        paths = listed(course, course.root / 'build' / folder)
        if paths:
            groups[folder] = paths
    if not groups:
        raise ValueError('Keine aktuellen Exporte; zuerst export ausführen')
    output = course.root / 'build/release'
    assets, combined = [], []
    for folder, paths in groups.items():
        base = course.root / 'build' / folder
        files = [(p.relative_to(base).as_posix(), p) for p in paths]
        combined.extend((folder + '/' + name, path) for name, path in files)
        target = output / f'{prefix(course)}-{folder}.zip'
        zip_files(target, files)
        assets.append(target.name)
    target = output / f'{prefix(course)}-Wissensbasis-komplett.zip'
    zip_files(target, combined)
    assets.append(target.name)
    write(output / 'release-manifest.json', {'assets': assets})
    return {'zip': target.relative_to(course.root).as_posix(), 'assets': assets}
