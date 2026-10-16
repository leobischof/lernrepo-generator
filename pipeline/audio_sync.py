"""Explicit local ASR with hash-bound caching; no model is loaded during planning."""
import math

from .audio_alignment import align, pdf_blocks
from .audio_topics import annotation_digest, untouched_generated, add_topic_context, pdf_sections
from .artifacts import listed
from .chapters import discover, prefix
from .io import file_hash, read, write
from .reader import recordings
from .timeline import validate


def run(course, model='tiny', start=False):
    from .jobs import approved
    from .build import assert_build_current
    approved(course)
    assert_build_current(course)
    chapters = discover(course)
    audio = recordings(course, chapters)
    pdfs = set(listed(course, course.root / 'build/pdf'))
    jobs = []
    for chapter in chapters:
        number = chapter['number']
        if number not in audio:
            continue
        pdf = course.root / 'build/pdf' / (chapter['stem'] + '.pdf')
        if pdf not in pdfs:
            raise ValueError('Aktuelles Kapitel-PDF fehlt: render-pdf ausführen')
        stem = f'{prefix(course)}-{number}'
        cache = course.root / f'build/transcripts/{stem}-Transkript.json'
        audio_hash = file_hash(audio[number])
        previous = read(cache, {})
        current = previous.get('audio_sha256') == audio_hash and previous.get('model') == model
        jobs.append((chapter, pdf, audio[number], cache, previous if current else None, audio_hash))
    pending = sum(data is None for _, _, _, _, data, _ in jobs)
    if not start:
        return {'audio_jobs': len(jobs), 'pending': pending,
                'note': 'Nur Plan. --start erlaubt lokale ASR; ein fehlendes Modell kann heruntergeladen werden.'}
    recognizer = None
    for chapter, pdf, audio_path, cache, data, audio_hash in jobs:
        number = chapter['number']
        if data is None:
            if recognizer is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise ValueError('Lokale ASR fehlt: pip install -e ".[audio]"') from exc
                recognizer = WhisperModel(model, device='cpu', compute_type='int8', cpu_threads=4)
            stream, info = recognizer.transcribe(str(audio_path), language=course.data['course'].get('language', 'de'),
                                                beam_size=1, vad_filter=True, condition_on_previous_text=False)
            segments = [dict(start=s.start, end=s.end, text=s.text) for s in stream]
            data = dict(audio_sha256=audio_hash, model=model, duration=info.duration, segments=segments)
            write(cache, data)
            from .ailog import append
            append(course.path('log'), stage='local-audio-transcription', model=f'faster-whisper/{model}',
                   inputs=[audio_path.relative_to(course.root).as_posix()], result='Lokale Transkription, ungeprüft', usage=None)
        duration = data.get('duration')
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            raise ValueError('Ungültige Transkriptdauer')
        for segment in data['segments']:
            if (not isinstance(segment.get('text'), str)
                    or not all(type(segment.get(k)) in (int, float) and math.isfinite(segment[k]) for k in ('start', 'end'))
                    or not 0 <= segment['start'] < segment['end'] <= duration):
                raise ValueError('Ungültiges Transkriptsegment')
        cues = add_topic_context(align(data['segments'], pdf_blocks(pdf)), pdf_sections(pdf), duration)
        value = dict(version=1, chapter=number, pdf_sha256=file_hash(pdf), audio_sha256=audio_hash,
                     generator=f'faster-whisper/{model} + lexical matching; unreviewed', annotations=cues,
                     generated_annotations_sha256=annotation_digest(cues))
        import pymupdf
        with pymupdf.open(pdf) as doc:
            validate(value, {'number': number, 'pdf_sha256': file_hash(pdf), 'audio_sha256': audio_hash}, len(doc), duration)
        path = course.root / f'curation/interactive/{prefix(course)}-{number}-Timeline.json'
        if path.exists() and not untouched_generated(read(path)):
            path = course.root / f'build/transcripts/{prefix(course)}-{number}-Timeline-Vorschlag.json'
        write(path, value)
    return {'processed': len(jobs), 'transcribed': pending}
