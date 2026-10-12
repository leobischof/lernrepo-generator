from dataclasses import asdict
from datetime import date
from .io import read, write
from .srs import Schedule, review, next_due

COMPETENCIES = {"definition", "verstaendnis", "aufzaehlung", "erklaerung", "vergleich", "berechnung", "zeichnung"}


def run(course, action, topic=None, competency=None, score=None, errors="", sketch=None):
    data = read(course.path("progress"), {"version": 1, "topics": {}})
    if action == "record":
        known = {s["id"] for s in read(course.path("structure"))["sections"]}
        known |= {s["id"] for s in read(course.path("structure"))["figures"]}
        if topic not in known or competency not in COMPETENCIES:
            raise ValueError("Unbekanntes Thema oder unbekannte Kompetenz")
        if sketch is not None and competency != "zeichnung":
            raise ValueError("--skizze nur bei zeichnung")
        key = topic + ":" + competency
        old = data["topics"].get(key, {})
        schedule = review(Schedule(**old.get("schedule", {})), score, sketch)
        history = old.get("history", []) + [dict(date=date.today().isoformat(), score=score, errors=errors, sketch=sketch)]
        item = dict(schedule=asdict(schedule), next_due=next_due(date.today(), schedule).isoformat(), history=history)
        data["topics"][key] = item
        write(course.path("progress"), data)
        return item
    rows = data["topics"].items()
    return {key: value for key, value in sorted(rows, key=lambda item: item[1]["next_due"])
            if action != "due" or value["next_due"] <= date.today().isoformat()}
