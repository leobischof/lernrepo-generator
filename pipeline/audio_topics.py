"""Persistent topic context behind precise audio cues, including spoken examples."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def annotation_digest(annotations: list[dict]) -> str:
    return hashlib.sha256(json.dumps(annotations,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def untouched_generated(value: dict) -> bool:
    annotations = value.get("annotations",[])
    return bool(value.get("generated_annotations_sha256")) and (
        value["generated_annotations_sha256"] == annotation_digest(annotations)
        and all(a.get("status") == "unreviewed" and a.get("origin") in {"local-asr-lexical","local-topic-context"} for a in annotations))


def pdf_sections(path: Path) -> list[dict]:
    import pymupdf
    with pymupdf.open(path) as doc:
        entries = [(title,page) for level,title,page in doc.get_toc() if level == 2]
        sections = []
        for title,page in entries:
            matches = doc[page-1].search_for(title)
            y = matches[-1].y0/doc[page-1].rect.height if matches else .08
            sections.append(dict(id=title.split()[0],title=title,page=page,y=max(.08,min(.85,y)),last_page=len(doc)))
        for index,section in enumerate(sections):
            following = sections[index+1] if index+1 < len(sections) else None
            section["last_page"] = following["page"] if following else len(doc)
            section["end_y"] = following["y"] if following else .94
    return sections


def section_for(cue: dict, sections: list[dict]) -> dict:
    page,y = cue["page"],cue["rect"][1]
    return next((s for s in reversed(sections) if s["page"] < page or (s["page"] == page and s["y"] <= y+.05)),sections[0])


def add_topic_context(details: list[dict], sections: list[dict], duration: float) -> list[dict]:
    if not sections or duration <= 0:
        return details
    details = sorted(details,key=lambda a:a["start"])
    for index,cue in enumerate(details):
        cue["scope"] = "detail"; cue["topic_id"] = section_for(cue,sections)["id"]
        cue["matched_end"] = cue["end"]
        # Detail cues are brief; only the broad topic frame persists through examples.
        cue["end"] = min(duration,cue["end"])
    transitions = [dict(start=0,section=sections[0],page=sections[0]["page"])]
    for index,cue in enumerate(details):
        section = section_for(cue,sections)
        if section["id"] == transitions[-1]["section"]["id"] or cue.get("confidence",0) < .23:
            continue
        corroborated = any(other["topic_id"] == section["id"] and other.get("confidence",0) >= .20
                           for other in details[index+1:] if 0 < other["start"]-cue["start"] <= 60)
        if corroborated or cue.get("confidence",0) >= .36:
            transitions.append(dict(start=cue["start"],section=section,page=cue["page"]))
    topics = []
    for index,transition in enumerate(transitions):
        start = transition["start"]; end = transitions[index+1]["start"] if index+1 < len(transitions) else duration
        if end <= start:
            continue
        section = transition["section"]
        for page in range(section["page"],section["last_page"]+1):
            y = section["y"]-.02 if page == section["page"] else .08
            bottom = section["end_y"]-.02 if page == section["last_page"] and section["end_y"] < .94 else .94
            if bottom-y < .06:
                continue
            topics.append(dict(id=f"topic-{index+1}-page-{page}",start=round(start,3),end=round(end,3),page=page,
                               type="rect",rect=[.07,round(y,5),.86,round(bottom-y,5)],scope="topic",
                               topic_id=section["id"],primary=page == transition["page"],pointer=False,
                               label=f"Thema: {section['title']}",status="unreviewed",origin="local-topic-context"))
    return topics+details
