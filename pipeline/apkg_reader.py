"""Read the notes of an Anki package (.apkg) without Anki.

An .apkg is a zip that holds the collection as SQLite in one of three generations:
`collection.anki21b` (zstd-compressed, newest), `collection.anki21` and the legacy
`collection.anki2` (which newer exports only fill with a "please update Anki" stub).
The newest generation present is the real one, so it is tried first. Media files
(numbered members) are never touched - the knowledge base does not copy them.
"""
from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import zstandard

COLLECTIONS = ("collection.anki21b", "collection.anki21", "collection.anki2")
FIELD_SEP = "\x1f"


@dataclass(frozen=True)
class RawNote:
    note_id: int
    fields: tuple[str, ...]
    tags: tuple[str, ...]


def _collection_bytes(apkg: Path) -> bytes:
    with zipfile.ZipFile(apkg) as z:
        name = next((n for n in COLLECTIONS if n in z.namelist()), None)
        if name is None:
            raise ValueError(f"{apkg.name}: keine Anki-Collection im Paket")
        data = z.read(name)
    if name.endswith(".anki21b"):
        data = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)).read()
    return data


def _deck_names(con: sqlite3.Connection) -> list[str]:
    """Names of the decks that hold cards (new schema: table `decks`, old: JSON in `col.decks`)."""
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    if "decks" in tables:
        rows = con.execute("select id, name from decks").fetchall()
    else:
        decks = json.loads(con.execute("select decks from col").fetchone()[0])
        rows = [(int(k), v["name"]) for k, v in decks.items()]
    used = {r[0] for r in con.execute("select distinct did from cards")}
    return sorted(name for did, name in rows if did in used)


def read(apkg: Path) -> tuple[list[RawNote], list[str]]:
    """Notes in creation order (note id) and the names of the decks in use."""
    # A real file, not sqlite3.deserialize: Anki collections are in WAL mode, which SQLite
    # refuses to open from memory.
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "collection.sqlite"
        db.write_bytes(_collection_bytes(apkg))
        con = sqlite3.connect(db)
        try:
            notes = [RawNote(int(i), tuple(flds.split(FIELD_SEP)), tuple(tags.split()))
                     for i, flds, tags in con.execute("select id, flds, tags from notes order by id")]
            return notes, _deck_names(con)
        finally:
            con.close()
