"""Spaced-repetition scheduling (SM-2 variant) – pure functions, no I/O.

One review = one self-assessed result 0–5 for one (topic, competency):

  5 perfekt · 4 richtig, kurz gezögert · 3 richtig, aber mühsam
  2 falsch, Lösung kam bekannt vor · 1 falsch · 0 keine Ahnung

Scheduling follows SM-2 (Wozniak 1990), which is simple, well documented and
good enough for a few hundred items:
  * result < 3  → repetitions restart, next review tomorrow;
  * result ≥ 3  → interval 1 day, then 6 days, then previous interval × ease;
  * ease starts at 2.5 and moves by 0.1 − (5−q)·(0.08 + (5−q)·0.02), never below 1.3.
Deviation from SM-2: a drawing that could *not* be produced independently caps
the interval at SKETCH_CAP_DAYS – an exam drawing must be reproducible from memory;
and no interval exceeds MAX_INTERVAL_DAYS.

Mastery is an exponential moving average of result/5 (weight MASTERY_ALPHA on the
newest result), so one lucky answer does not mark a topic as mastered.
See docs/learning-method.md for the didactic reasoning.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

START_EASE = 2.5
MIN_EASE = 1.3
PASS = 3                    # results ≥ PASS count as remembered
MASTERY_ALPHA = 0.5
SKETCH_CAP_DAYS = 3
# Plain SM-2 grows without bound (and eventually overflows `date`); for exam
# preparation an item not seen for a year is effectively new anyway.
MAX_INTERVAL_DAYS = 365
LEVELS = (                  # (minimum mastery, minimum interval in days, German label)
    (0.9, 21, "beherrscht"),
    (0.8, 6, "gefestigt"),
    (0.5, 0, "lernend"),
    (0.0, 0, "unsicher"),
)


@dataclass(frozen=True)
class Schedule:
    repetitions: int = 0
    interval_days: int = 0
    ease: float = START_EASE
    mastery: float | None = None     # None = never reviewed


def _ease(ease: float, result: int) -> float:
    miss = 5 - result
    return max(MIN_EASE, round(ease + 0.1 - miss * (0.08 + miss * 0.02), 3))


def _interval(s: Schedule) -> int:
    if s.repetitions == 0:
        return 1
    if s.repetitions == 1:
        return 6
    return min(MAX_INTERVAL_DAYS, max(1, round(s.interval_days * s.ease)))


def review(s: Schedule, result: int, sketch_independent: bool | None = None) -> Schedule:
    """New schedule after one review with self-assessed `result` (0–5)."""
    if not 0 <= result <= 5:
        raise ValueError("Ergebnis muss zwischen 0 und 5 liegen")
    mastery = result / 5 if s.mastery is None else round(
        MASTERY_ALPHA * result / 5 + (1 - MASTERY_ALPHA) * s.mastery, 3)
    ease = _ease(s.ease, result)
    if result < PASS:
        return Schedule(repetitions=0, interval_days=1, ease=ease, mastery=mastery)
    interval = _interval(s)
    if sketch_independent is False:
        interval = min(interval, SKETCH_CAP_DAYS)
    return Schedule(repetitions=s.repetitions + 1, interval_days=interval, ease=ease, mastery=mastery)


def next_due(practiced: date, s: Schedule) -> date:
    return practiced + timedelta(days=s.interval_days)


def level(s: Schedule) -> str:
    """German mastery label; 'neu' before the first review."""
    if s.mastery is None:
        return "neu"
    for min_mastery, min_interval, label in LEVELS:
        if s.mastery >= min_mastery and s.interval_days >= min_interval:
            return label
    return LEVELS[-1][2]
