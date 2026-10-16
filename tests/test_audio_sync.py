import pytest

from test_reader import reader_course
from test_pipeline import course, git_available
from pipeline.io import file_hash, read, write


def test_alignment_handles_out_of_order_topics_and_omits_unrelated_text():
    from pipeline.audio_sync import align
    blocks = [dict(page=1, rect=[0,0,1,.3], text='Energie Masse Geschwindigkeit Licht'),
              dict(page=2, rect=[0,0,1,.3], text='Arbeit Kraft Strecke Bewegung')]
    segments = [dict(start=0, end=5, text='Arbeit Kraft Strecke Bewegung'),
                dict(start=20, end=25, text='Banane Apfel Birne'),
                dict(start=40, end=45, text='Energie Masse Geschwindigkeit Licht')]
    cues = align(segments, blocks)
    assert [cue['page'] for cue in cues] == [2, 1]
    assert all(cue['status'] == 'unreviewed' for cue in cues)


def test_audio_plan_never_loads_model_and_curated_timeline_survives(reader_course):
    from pipeline.audio_sync import run
    c = reader_course
    audio = c.root / 'audio/testkurs-1-Audio.wav'
    write(audio, 'synthetic recording')
    assert run(c, model='tiny', start=False)['pending'] == 1
    assert not (c.root / 'build/transcripts').exists()
    pdf = c.root / 'build/pdf/testkurs-1-Energie.pdf'
    write(c.root / 'build/transcripts/testkurs-1-Transkript.json',
          {'audio_sha256': file_hash(audio), 'model': 'tiny', 'duration': 10,
           'segments': [{'start': 0, 'end': 5, 'text': 'Energie bleibt erhalten Arbeit Energieübertragung'}]})
    timeline = c.root / 'curation/interactive/testkurs-1-Timeline.json'
    write(timeline, {'version': 1, 'chapter': 1, 'pdf_sha256': file_hash(pdf),
                     'audio_sha256': file_hash(audio), 'annotations': []})
    before = timeline.read_bytes()
    assert run(c, model='tiny', start=True)['processed'] == 1
    assert timeline.read_bytes() == before
    assert (c.root / 'build/transcripts/testkurs-1-Timeline-Vorschlag.json').is_file()
