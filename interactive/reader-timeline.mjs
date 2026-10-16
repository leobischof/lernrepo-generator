export function validateTimeline(value, {pages = Infinity, duration = Infinity, chapter, audioHash, pdfHash} = {}) {
  if (!value || value.version !== 1 || !Array.isArray(value.annotations)) throw new Error("Ungültiges Timeline-Format (Version 1 erforderlich).");
  if (chapter !== undefined && value.chapter !== chapter) throw new Error("Timeline gehört zu einem anderen Kapitel.");
  if (audioHash && value.audio_sha256 !== audioHash) throw new Error("Timeline gehört zu einer anderen Audiodatei.");
  if (pdfHash && value.pdf_sha256 !== pdfHash) throw new Error("Timeline gehört zu einer anderen PDF-Version.");
  const ids = new Set();
  for (const a of value.annotations) {
    if (typeof a.id !== "string" || !a.id || ids.has(a.id)) throw new Error("Annotationen brauchen eindeutige IDs.");
    ids.add(a.id);
    if (![a.start, a.end].every(Number.isFinite) || a.start < 0 || a.end <= a.start || a.end > duration + 1) throw new Error(`Ungültige Zeit: ${a.id}`);
    if (!Number.isInteger(a.page) || a.page < 1 || a.page > pages) throw new Error(`Ungültige Seite: ${a.id}`);
    if (!["rect", "highlight", "arrow"].includes(a.type)) throw new Error(`Unbekannter Typ: ${a.id}`);
    if (!["unreviewed", "reviewed"].includes(a.status)) throw new Error(`Unbekannter Prüfstatus: ${a.id}`);
    if (a.type === "arrow") {
      if (!Array.isArray(a.points) || a.points.length !== 4 || !a.points.every(v => Number.isFinite(v) && v >= 0 && v <= 1)) throw new Error(`Ungültiger Pfeil: ${a.id}`);
    } else {
      if (!Array.isArray(a.rect) || a.rect.length !== 4 || !a.rect.every(Number.isFinite)) throw new Error(`Ungültiges Rechteck: ${a.id}`);
      const [x,y,w,h] = a.rect;
      if (x < 0 || y < 0 || w <= 0 || h <= 0 || x+w > 1.00001 || y+h > 1.00001) throw new Error(`Rechteck außerhalb der Seite: ${a.id}`);
    }
    if (a.animation !== undefined && !["none", "pulse"].includes(a.animation)) throw new Error(`Unbekannte Animation: ${a.id}`);
  }
  return value;
}

export function activeAt(annotations, time) {
  return annotations.filter(a => a.start <= time && time < a.end);
}

export function formatTime(seconds) {
  const n = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(n/60)}:${String(n%60).padStart(2,"0")}`;
}

export function seekTarget(time, offset, duration) {
  const end = Number.isFinite(duration) && duration >= 0 ? duration : Infinity;
  return Math.max(0,Math.min(end,time+offset));
}

export function isManualPdfNavigation(event, overScrollbar = false) {
  if (event.type === "wheel") return !event.ctrlKey && Boolean(event.deltaY || event.deltaX);
  if (event.type === "touchmove") return !event.touches || event.touches.length === 1;
  if (event.type === "pointerdown") return event.button === 1 || overScrollbar;
  if (event.type === "keydown") return !event.ctrlKey && !event.altKey && !event.metaKey &&
    ["ArrowUp","ArrowDown","PageUp","PageDown","Home","End"," "].includes(event.key);
  return false; // PDF.js scrolling to a cue is not a manual navigation gesture.
}
