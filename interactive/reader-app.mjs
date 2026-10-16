import * as pdfjsLib from "./vendor/build/pdf.mjs";
import {PDFViewer, EventBus, PDFLinkService, PDFFindController} from "./vendor/web/pdf_viewer.mjs";
import {activeAt, validateTimeline, formatTime, seekTarget, isManualPdfNavigation} from "./reader-timeline.mjs";
import {DocumentNavigation} from "./reader-navigation.mjs";
import {setupOffline} from "./reader-offline.mjs";

const $ = id => document.getElementById(id);
const svgNS = "http://www.w3.org/2000/svg";
const eventBus = new EventBus();
const linkService = new PDFLinkService({eventBus});
const findController = new PDFFindController({eventBus, linkService});
const viewer = new PDFViewer({container:$("viewerContainer"), viewer:$("viewer"), eventBus,
  linkService, findController, annotationEditorMode:-1});
linkService.setViewer(viewer);
pdfjsLib.GlobalWorkerOptions.workerSrc = globalThis.LEARNREPO_EMBEDDED?.workerURL || "./vendor/build/pdf.worker.mjs";

let manifest, chapter, pdf, timeline, loadingTask, currentMedia = $("audio");
let selected = null, drawing = false, drag = null, activeKey = "", followKey = "", loadSequence = 0;
let cueButtons = new Map();
let timelineDuration = 0;
let navigationTab = "outline";
const navigation = new DocumentNavigation({outline:$("pdf-outline"),thumbnails:$("pdf-thumbnails"),scrollRoot:$("navigation-body"),
  onChapter:number => { if (number !== chapter?.number) loadChapter(number).catch(error => notice(error.message,true)); },
  onPage:page => { stopFollowing(); viewer.currentPageNumber = page; },
  onDestination:dest => { stopFollowing(); linkService.goToDestination(dest).catch(error => notice(error.message,true)); },
  onError:error => notice(`Inhaltsverzeichnis nicht verfügbar: ${error.message}`)});

function resizePDF() {
  requestAnimationFrame(() => { if (pdf) { viewer.currentScaleValue = $("zoom").value; viewer.update(); sync(true); } });
}
function setNavigation(open,tab = navigationTab) {
  navigationTab = tab;
  document.body.classList.toggle("navigation-open",open); $("navigation-body").inert = !open;
  $("toggle-navigation").setAttribute("aria-expanded",String(open));
  const label = open ? "PDF-Navigation einklappen" : "PDF-Navigation öffnen";
  $("toggle-navigation").setAttribute("aria-label",label); $("toggle-navigation").title = label;
  $("pdf-outline").hidden = tab !== "outline"; $("pdf-thumbnails").hidden = tab !== "thumbnails";
  $("show-outline").setAttribute("aria-pressed",String(tab === "outline"));
  $("show-thumbnails").setAttribute("aria-pressed",String(tab === "thumbnails"));
  $("navigation-title").textContent = tab === "outline" ? "Kapitel & Inhalt" : "Seitenminiaturen";
  try { localStorage.setItem(`lernrepo-${manifest?.course?.id || location.pathname}-navigation`,JSON.stringify({open,tab})); } catch {}
  resizePDF();
}
function updateZoomSelect() {
  const value = String(viewer.currentScaleValue);
  let option = [...$("zoom").options].find(item => item.value === value);
  if (!option) {
    $("zoom").querySelector("[data-custom]")?.remove(); option = document.createElement("option");
    option.value = value; option.dataset.custom = "true"; option.textContent = `${Math.round(viewer.currentScale*100)} %`; $("zoom").append(option);
  }
  $("zoom").value = value;
}

function updateMiniControls() {
  const available = Boolean(chapter?.audio) && currentMedia.readyState > 0 && !currentMedia.error;
  for (const id of ["mini-play","mini-back","mini-forward","mini-mute","mini-speed"]) $(id).disabled = !available;
  const playing = !currentMedia.paused && !currentMedia.ended;
  const label = playing ? "Audio pausieren" : "Audio abspielen";
  $("mini-play").textContent = playing ? "Ⅱ" : "▶";
  $("mini-play").setAttribute("aria-label",label); $("mini-play").title = label;
  $("mini-mute").setAttribute("aria-pressed",String(currentMedia.muted));
  $("mini-mute").textContent = currentMedia.muted ? "×♪" : "♪";
  const muteLabel = currentMedia.muted ? "Ton einschalten" : "Stummschalten";
  $("mini-mute").setAttribute("aria-label",muteLabel); $("mini-mute").title = muteLabel;
  const rate = String(currentMedia.playbackRate).replace(".",",");
  $("mini-speed").textContent = `${rate}×`;
  $("mini-speed").setAttribute("aria-label",`Wiedergabetempo ändern, aktuell ${rate}-fach`);
  $("mini-speed").title = `Wiedergabetempo ändern, aktuell ${rate}×`;
  $("mini-time").textContent = formatTime(currentMedia.currentTime);
  $("timeline-time").textContent = formatTime(currentMedia.currentTime);
  const duration = Number.isFinite(currentMedia.duration) ? currentMedia.duration : 0;
  $("media-seek").disabled = !available || duration <= 0;
  $("media-seek").max = duration;
  $("media-seek").value = currentMedia.currentTime;
  $("media-seek").setAttribute("aria-valuetext",`${formatTime(currentMedia.currentTime)} von ${formatTime(duration)}`);
  $("timeline-duration").textContent = duration > 0 ? formatTime(duration) : "–:–";
  if (duration !== timelineDuration) { timelineDuration = duration; renderTimelineCues(); }
  for (const [id,checkbox,on,off] of [
    ["mini-follow","follow","Autoscroller ausschalten","Autoscroller einschalten"],
    ["mini-marks","show-marks","Markierungen ausblenden","Markierungen anzeigen"]]) {
    const checked = $(checkbox).checked;
    $(id).setAttribute("aria-pressed",String(checked));
    $(id).setAttribute("aria-label",checked ? on : off); $(id).title = checked ? on : off;
  }
}
function renderTimelineCues() {
  $("timeline-cues").replaceChildren();
  if (!timeline || timelineDuration <= 0) return;
  for (const a of timeline.annotations) {
    if (a.scope === "topic" && !a.primary) continue;
    const tick = document.createElement("span");
    tick.className = `timeline-cue ${a.status} ${a.scope || ""}`;
    tick.style.left = `${Math.min(100,a.start/timelineDuration*100)}%`;
    tick.style.width = `${Math.max(.15,Math.min(100,(a.end-a.start)/timelineDuration*100))}%`;
    tick.title = `${formatTime(a.start)} · ${a.label || "Markierung"}`;
    $("timeline-cues").append(tick);
  }
}
function stopFollowing() {
  if (!$("follow").checked) return;
  $("follow").checked = false; followKey = ""; updateMiniControls();
  notice("Autoscroller aus, weil du selbst im PDF navigierst. Zum Weiterfolgen den Pfeilknopf einschalten.");
}
function setSidebarOpen(open) {
  document.body.classList.toggle("sidebar-collapsed",!open);
  $("sidebar-body").inert = !open;
  $("toggle-sidebar").setAttribute("aria-expanded",String(open));
  const label = open ? "Seitenleiste einklappen" : "Seitenleiste öffnen";
  $("toggle-sidebar").setAttribute("aria-label",label); $("toggle-sidebar").title = label;
  $("toggle-sidebar").textContent = open ? "›" : "☰";
  try { localStorage.setItem(`lernrepo-${manifest?.course?.id || location.pathname}-sidebar-open`,String(open)); } catch {}
  resizePDF();
}

function notice(text, error = false) {
  $("status").textContent = text; $("status").classList.toggle("error", error);
  if (error && document.body.classList.contains("sidebar-collapsed")) setSidebarOpen(true);
}
function storageKey() { return `lernrepo-timeline:${chapter.pdf_sha256}:${chapter.audio_sha256 || "no-audio"}`; }
function limits() { return {chapter:chapter.number, pages:pdf?.numPages, audioHash:chapter.audio_sha256,
  pdfHash:chapter.pdf_sha256, duration:Number.isFinite(currentMedia.duration) && currentMedia.duration > 1 ? currentMedia.duration : Infinity}; }
function makeSVG(tag, attrs = {}) {
  const node = document.createElementNS(svgNS, tag);
  for (const [key,value] of Object.entries(attrs)) node.setAttribute(key,String(value));
  return node;
}
function geometryNode(a) {
  if (a.type === "arrow") {
    const [x1,y1,x2,y2] = a.points.map(v => v*1000);
    return makeSVG("line",{x1,y1,x2,y2,"marker-end":"url(#lernrepo-arrow)"});
  }
  const [x,y,width,height] = a.rect.map(v => v*1000);
  return makeSVG("rect",{x,y,width,height,rx:a.type === "highlight" ? 0 : 3});
}
function overlayFor(pageNumber) {
  const page = viewer.getPageView(pageNumber-1)?.div;
  if (!page) return null;
  let svg = page.querySelector(":scope > .lernrepo-overlay");
  if (!svg) {
    svg = makeSVG("svg",{class:"lernrepo-overlay",viewBox:"0 0 1000 1000",preserveAspectRatio:"none","aria-label":"Zeitgesteuerte PDF-Markierungen"});
    svg.dataset.page = pageNumber;
    svg.addEventListener("pointerdown",drawStart);
    svg.addEventListener("pointermove",drawMove);
    svg.addEventListener("pointerup",drawEnd);
    svg.addEventListener("pointercancel",cancelDrawing);
    page.append(svg);
  }
  return svg;
}
function renderMarks() {
  if (!timeline || !pdf) return;
  const active = $("show-marks").checked ? activeAt(timeline.annotations,currentMedia.currentTime) : [];
  for (let n = 1; n <= pdf.numPages; n++) {
    const svg = overlayFor(n);
    if (!svg) continue;
    svg.replaceChildren();
    const markerId = `lernrepo-arrow-${n}`;
    const defs = makeSVG("defs"), marker = makeSVG("marker",{id:markerId,viewBox:"0 0 10 10",refX:9,refY:5,markerWidth:8,markerHeight:8,orient:"auto-start-reverse"});
    marker.append(makeSVG("path",{d:"M 0 0 L 10 5 L 0 10 z",fill:"#d55b39"})); defs.append(marker); svg.append(defs);
    const onPage = active.filter(a => a.page === n).sort((a,b) => Number(a.scope !== "topic")-Number(b.scope !== "topic"));
    if (selected && $("editor").open && selected.page === n && !onPage.includes(selected)) onPage.push(selected);
    for (const a of onPage) {
      const node = geometryNode(a);
      if (a.type === "arrow") node.setAttribute("marker-end",`url(#${markerId})`);
      node.setAttribute("class",`lernrepo-mark ${a.type} ${a.status} ${a.scope || ""} ${a.animation || ""}`);
      const title = makeSVG("title"); title.textContent = a.label || "Markierung"; node.append(title); svg.append(node);
      if (a.pointer && a.rect) {
        const [x,y,,h] = a.rect;
        const pointer = geometryNode({type:"arrow",points:[Math.max(.005,x-.075),Math.max(.005,y-.025),x,y+h/2]});
        pointer.setAttribute("marker-end",`url(#${markerId})`); pointer.setAttribute("class","lernrepo-mark arrow"); svg.append(pointer);
      }
      // Geometry is clickable; the rest of the transparent layer lets text selection through.
      if (!drawing) {
        const hit = geometryNode(a); hit.removeAttribute("marker-end"); hit.setAttribute("class","lernrepo-hit");
        hit.setAttribute("tabindex","0"); hit.setAttribute("role","button"); hit.setAttribute("aria-label",`Zur Audiostelle ${formatTime(a.start)}: ${a.label || "Markierung"}`);
        hit.addEventListener("click",() => selectCue(a,true));
        hit.addEventListener("keydown",e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectCue(a,true); } });
        svg.append(hit);
      }
    }
  }
}
function sync(force = false) {
  if (!timeline) return;
  const active = activeAt(timeline.annotations,currentMedia.currentTime);
  const key = active.map(a => a.id).join("|");
  if (force || key !== activeKey) {
    activeKey = key; renderMarks();
    for (const [id,button] of cueButtons) button.classList.toggle("active",active.some(a => a.id === id));
  }
  if ($("follow").checked && active.length) {
    const target = active.find(a => a.scope !== "topic") || active.find(a => a.page === viewer.currentPageNumber) || active.find(a => a.primary) || active[0];
    if (target.id !== followKey) {
      followKey = target.id;
      if (target.scope !== "topic" || target.page !== viewer.currentPageNumber) jumpTo(target);
    }
  }
}
function jumpTo(a) {
  const p = viewer.getPageView(a.page-1);
  if (!p) return;
  viewer.currentPageNumber = a.page;
  const coords = a.rect || [Math.min(a.points[0],a.points[2]),Math.min(a.points[1],a.points[3])];
  const bounds = p.div.getBoundingClientRect(), container = $("viewerContainer"), outer = container.getBoundingClientRect();
  container.scrollTop += bounds.top - outer.top + coords[1]*bounds.height - 90;
}
function renderCues() {
  $("cues").replaceChildren(); cueButtons = new Map();
  renderTimelineCues();
  const cues = timeline.annotations.filter(a => a.scope !== "topic" || a.primary).sort((a,b) => a.start-b.start);
  $("cue-count").textContent = `${cues.length} Stellen`;
  if (!cues.length) {
    const p = document.createElement("p"); p.className = "small";
    p.textContent = chapter.audio ? "Noch keine passenden Stellen vorbereitet. Im Korrekturbereich kannst du eigene Markierungen setzen." : "Für dieses Kapitel liegt noch kein Audio vor.";
    $("cues").append(p);
  }
  for (const a of cues) {
    const button = document.createElement("button"), label = document.createElement("strong"), meta = document.createElement("span");
    button.className = "cue"; button.dataset.annotationId = a.id;
    label.textContent = a.label || "Markierung";
    meta.textContent = `${formatTime(a.start)}–${formatTime(a.end)} · Seite ${a.page} · ${a.status === "reviewed" ? "geprüft" : "Vorschlag, ungeprüft"}`;
    if (a.status === "reviewed") meta.className = "checked";
    button.append(label,meta); button.addEventListener("click",() => selectCue(a,true));
    $("cues").append(button); cueButtons.set(a.id,button);
  }
  sync(true);
}
function selectCue(a, seek = false) {
  selected = a;
  if (seek && chapter.audio) currentMedia.currentTime = a.start;
  jumpTo(a);
  $("label").value = a.label || ""; $("start").value = a.start; $("end").value = a.end;
  $("annotation-page").value = a.page; $("geometry").value = (a.rect || a.points).join(", ");
  $("reviewed").checked = a.status === "reviewed"; $("animation").value = a.animation || "none";
  $("draw-type").value = a.type;
  $("excerpt").textContent = a.transcript ? `Audio-Transkript (automatisch): ${a.transcript}` : "Manuell gesetzte Markierung.";
  for (const [id,b] of cueButtons) b.classList.toggle("selected",id === a.id);
  renderMarks();
}
function persist() {
  validateTimeline(timeline,limits());
  try { localStorage.setItem(storageKey(),JSON.stringify(timeline)); notice("Änderungen in diesem Browser gespeichert. Für das Kapitelpaket bitte Timeline herunterladen."); }
  catch { notice("Browserspeicher nicht verfügbar. Bitte Timeline herunterladen.",true); }
  renderCues();
}
function cancelDrawing() {
  drawing = false; drag = null; document.body.classList.remove("drawing"); $("draw").textContent = "Auf PDF zeichnen"; renderMarks();
}
function normalizedPoint(svg,event) {
  const r = svg.getBoundingClientRect();
  return [Math.max(0,Math.min(1,(event.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(event.clientY-r.top)/r.height))];
}
function drawStart(event) {
  if (!drawing || event.button !== 0) return;
  event.preventDefault(); const svg = event.currentTarget;
  svg.setPointerCapture(event.pointerId); drag = {svg,start:normalizedPoint(svg,event),end:normalizedPoint(svg,event),page:Number(svg.dataset.page)};
}
function drawMove(event) {
  if (!drag) return;
  drag.end = normalizedPoint(drag.svg,event);
  drag.svg.querySelector(".lernrepo-draft")?.remove();
  const node = geometryNode(draftAnnotation()); node.removeAttribute("marker-end"); node.setAttribute("class","lernrepo-mark lernrepo-draft"); drag.svg.append(node);
}
function draftAnnotation() {
  const [x1,y1] = drag.start, [x2,y2] = drag.end;
  const a = {type:$("draw-type").value,page:drag.page};
  if (a.type === "arrow") a.points = [x1,y1,x2,y2];
  else a.rect = [Math.min(x1,x2),Math.min(y1,y2),Math.abs(x2-x1),Math.abs(y2-y1)];
  return a;
}
function drawEnd(event) {
  if (!drag) return;
  drag.end = normalizedPoint(drag.svg,event);
  const a = draftAnnotation();
  const distance = Math.hypot(drag.end[0]-drag.start[0],drag.end[1]-drag.start[1]);
  cancelDrawing();
  if (distance < .01 || (a.rect && (a.rect[2] < .003 || a.rect[3] < .003))) { notice("Bitte eine größere Markierung aufziehen."); return; }
  const now = Math.round(currentMedia.currentTime*10)/10;
  const end = Math.min(now+12,Number.isFinite(currentMedia.duration) && currentMedia.duration > 1 ? currentMedia.duration : now+12);
  if (end <= now) { notice("Neue Markierungen müssen vor dem Ende des Audios starten.",true); return; }
  Object.assign(a,{id:crypto.randomUUID(),start:now,end,label:"Eigene Markierung",status:"unreviewed",origin:"manual"});
  timeline.annotations.push(a); selectCue(a); persist();
}
async function getJSON(path) {
  if (globalThis.LEARNREPO_EMBEDDED?.json?.[path]) return globalThis.LEARNREPO_EMBEDDED.json[path];
  const response = await fetch(path); if (!response.ok) throw new Error(`Datei nicht verfügbar: ${path}`);
  return response.json();
}
async function loadChapter(number) {
  const sequence = ++loadSequence;
  chapter = manifest.chapters.find(c => c.number === Number(number));
  if (!chapter) throw new Error("Kapitel nicht gefunden.");
  cancelDrawing(); selected = null; activeKey = followKey = ""; timeline = null; pdf = null;
  navigation.setDocument(null,manifest.chapters,chapter.number);
  $("annotation-form").reset(); $("excerpt").textContent = "";
  for (const media of [$("audio"),$("video")]) { media.pause(); media.removeAttribute("src"); media.load(); }
  currentMedia = chapter.media_type === "video" ? $("video") : $("audio");
  $("video").hidden = currentMedia !== $("video"); $("audio").hidden = currentMedia !== $("audio");
  $("chapter-title").textContent = `Kapitel ${chapter.number} · ${chapter.title}`;
  $("pdf-download").href = chapter.pdf; $("pdf-download").target = "_blank"; $("pdf-download").rel = "noopener";
  $("chapters").value = chapter.number;
  try { history.replaceState(null,"",`?chapter=${chapter.number}`); } catch {}
  notice("PDF und Timeline werden geladen …");
  if (chapter.audio) currentMedia.src = chapter.audio;
  updateMiniControls();
  currentMedia.playbackRate = Number($("speed").value);
  $("draw").disabled = !chapter.audio;
  viewer.setDocument(null); linkService.setDocument(null);
  if (loadingTask) await loadingTask.destroy();
  if (sequence !== loadSequence) return;
  loadingTask = pdfjsLib.getDocument({url:chapter.pdf,cMapUrl:new URL("./vendor/cmaps/",document.baseURI).href,cMapPacked:true,
    standardFontDataUrl:new URL("./vendor/standard_fonts/",document.baseURI).href,wasmUrl:new URL("./vendor/wasm/",document.baseURI).href,isEvalSupported:false,
    ...(globalThis.LEARNREPO_EMBEDDED?.pdfOptions || {})});
  const [doc, data] = await Promise.all([loadingTask.promise,getJSON(chapter.timeline)]);
  if (sequence !== loadSequence) return;
  pdf = doc; timeline = validateTimeline(data,limits());
  try {
    const saved = localStorage.getItem(storageKey());
    if (saved) timeline = validateTimeline(JSON.parse(saved),limits());
  } catch { notice("Gespeicherte Timeline passt nicht mehr. Die Paketversion wird geladen.",true); }
  viewer.setDocument(pdf); linkService.setDocument(pdf);
  navigation.setDocument(pdf,manifest.chapters,chapter.number);
  $("pages").textContent = `/ ${pdf.numPages}`; $("page").max = pdf.numPages;
  renderCues();
  const unreviewed = timeline.annotations.filter(a => a.status !== "reviewed").length;
  notice(chapter.audio ? `${unreviewed} automatische oder manuelle Vorschläge sind noch ungeprüft.` : "PDF verfügbar. Für dieses Kapitel fehlt noch das Audio.");
}

eventBus.on("pagesinit",() => { viewer.currentScaleValue = $("zoom").value; sync(true); });
eventBus.on("pagerendered",() => sync(true));
eventBus.on("pagechanging",e => { $("page").value = e.pageNumber; navigation.setCurrentPage(e.pageNumber); });
eventBus.on("scalechanging",updateZoomSelect);
eventBus.on("updatefindmatchescount",e => { $("matches").textContent = e.matchesCount.total ? `${e.matchesCount.current}/${e.matchesCount.total}` : "0 Treffer"; });
for (const media of [$("audio"),$("video")]) {
  for (const event of ["timeupdate","seeking","seeked","loadedmetadata","durationchange","play","pause","ended","emptied","error","volumechange","ratechange"]) media.addEventListener(event,() => { if (media === currentMedia) { updateMiniControls(); sync(); } });
  media.addEventListener("error",() => { if (media === currentMedia && media.getAttribute("src")) notice("Audio/Video konnte nicht geladen werden. Bitte Dateipfad und Browser-Unterstützung prüfen.",true); });
}
$("toggle-sidebar").addEventListener("click",() => setSidebarOpen(document.body.classList.contains("sidebar-collapsed")));
$("toggle-navigation").addEventListener("click",() => setNavigation(!document.body.classList.contains("navigation-open")));
$("show-outline").addEventListener("click",() => setNavigation(true,"outline"));
$("show-thumbnails").addEventListener("click",() => setNavigation(true,"thumbnails"));
$("zoom-in").addEventListener("click",() => { viewer.increaseScale(); sync(true); });
$("zoom-out").addEventListener("click",() => { viewer.decreaseScale(); sync(true); });
$("mini-play").addEventListener("click",async () => {
  try { if (currentMedia.paused) await currentMedia.play(); else currentMedia.pause(); }
  catch (error) { notice(`Wiedergabe nicht möglich: ${error.message}`,true); setSidebarOpen(true); }
});
for (const [id,offset] of [["mini-back",-10],["mini-forward",10]]) $(id).addEventListener("click",() => {
  currentMedia.currentTime = seekTarget(currentMedia.currentTime,offset,currentMedia.duration); sync(true);
});
$("mini-mute").addEventListener("click",() => { currentMedia.muted = !currentMedia.muted; updateMiniControls(); });
$("mini-speed").addEventListener("click",() => {
  const choices = [...$("speed").options].map(option => Number(option.value));
  const next = choices[(choices.indexOf(currentMedia.playbackRate)+1)%choices.length];
  $("speed").value = next; currentMedia.playbackRate = next; updateMiniControls();
});
for (const [id,checkbox] of [["mini-follow","follow"],["mini-marks","show-marks"]]) $(id).addEventListener("click",() => {
  $(checkbox).checked = !$(checkbox).checked; $(checkbox).dispatchEvent(new Event("change")); updateMiniControls();
});
$("chapters").addEventListener("change",e => loadChapter(e.target.value).catch(e => notice(e.message,true)));
$("previous").addEventListener("click",() => { stopFollowing(); viewer.currentPageNumber = Math.max(1,viewer.currentPageNumber-1); });
$("next").addEventListener("click",() => { stopFollowing(); viewer.currentPageNumber = Math.min(pdf?.numPages || 1,viewer.currentPageNumber+1); });
$("page").addEventListener("change",e => { stopFollowing(); viewer.currentPageNumber = Math.max(1,Math.min(pdf?.numPages || 1,Number(e.target.value))); });
$("zoom").addEventListener("change",e => { viewer.currentScaleValue = e.target.value; sync(true); });
$("speed").addEventListener("change",e => { currentMedia.playbackRate = Number(e.target.value); updateMiniControls(); });
$("show-marks").addEventListener("change",() => { updateMiniControls(); sync(true); });
$("follow").addEventListener("change",() => { followKey = ""; updateMiniControls(); sync(); });
$("editor").addEventListener("toggle",renderMarks);
$("search-form").addEventListener("submit",e => { e.preventDefault(); stopFollowing(); eventBus.dispatch("find",{source:window,type:"again",query:$("search").value,phraseSearch:true,caseSensitive:false,entireWord:false,highlightAll:true,findPrevious:false}); });
$("media-seek").addEventListener("input",e => {
  currentMedia.currentTime = Number(e.target.value); followKey = ""; updateMiniControls(); sync(true);
});
for (const event of ["wheel","touchmove","keydown"]) $("viewerContainer").addEventListener(event,e => {
  if (isManualPdfNavigation(e)) stopFollowing();
},{passive:true});
$("viewerContainer").addEventListener("pointerdown",e => {
  const container = $("viewerContainer"), rect = container.getBoundingClientRect();
  const overScrollbar = e.target === container && (e.clientX >= rect.left+container.clientWidth || e.clientY >= rect.top+container.clientHeight);
  if (isManualPdfNavigation(e,overScrollbar)) stopFollowing();
});
// Chromium/Firefox expose a trackpad pinch as Ctrl+wheel. Keep browser chrome unchanged.
$("viewerContainer").addEventListener("wheel",e => {
  if (!e.ctrlKey || !pdf) return;
  e.preventDefault();
  const delta = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? $("viewerContainer").clientHeight : 1);
  viewer.updateScale({scaleFactor:Math.exp(-Math.max(-100,Math.min(100,delta))*.01),origin:[e.clientX,e.clientY],drawingDelay:100});
},{passive:false});
let gestureScale = 1;
$("viewerContainer").addEventListener("gesturestart",e => { if (pdf) { e.preventDefault(); gestureScale = viewer.currentScale; } },{passive:false});
$("viewerContainer").addEventListener("gesturechange",e => {
  if (!pdf || !Number.isFinite(e.scale)) return;
  e.preventDefault(); viewer.updateScale({scaleFactor:gestureScale*e.scale/viewer.currentScale,origin:[e.clientX,e.clientY],drawingDelay:100});
},{passive:false});
$("draw").addEventListener("click",() => {
  if (drawing) return cancelDrawing();
  drawing = true; document.body.classList.add("drawing"); $("draw").textContent = "Zeichnen abbrechen";
  notice("Auf der gewünschten PDF-Seite ziehen. Escape bricht den Zeichenmodus ab."); renderMarks();
});
document.addEventListener("keydown",e => { if (e.key === "Escape") cancelDrawing(); });
$("annotation-form").addEventListener("submit",e => {
  e.preventDefault(); if (!selected) return notice("Zuerst einen Vorschlag auswählen oder eine neue Markierung zeichnen.");
  const a = {...selected,label:$("label").value,start:Number($("start").value),end:Number($("end").value),page:Number($("annotation-page").value),
    type:$("draw-type").value,status:$("reviewed").checked ? "reviewed" : "unreviewed",animation:$("animation").value};
  const geometry = $("geometry").value.split(",").map(x => Number(x.trim()));
  delete a.rect; delete a.points; a[a.type === "arrow" ? "points" : "rect"] = geometry;
  try {
    const next = {...timeline,annotations:timeline.annotations.map(item => item.id === a.id ? a : item)};
    validateTimeline(next,limits()); timeline = next; selected = a; persist(); selectCue(a);
  } catch (error) { notice(error.message,true); }
});
$("delete").addEventListener("click",() => { if (!selected) return; timeline.annotations = timeline.annotations.filter(a => a.id !== selected.id); selected = null; $("annotation-form").reset(); persist(); });
$("export").addEventListener("click",() => {
  if (!timeline) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(timeline,null,2)+"\n"],{type:"application/json"}));
  const link = document.createElement("a"); link.href = url; link.download = `${manifest.course.export_prefix}-${chapter.number}-Timeline.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
});
$("import").addEventListener("change",async e => {
  try { const data = JSON.parse(await e.target.files[0].text()); validateTimeline(data,limits()); timeline = data; selected = null; persist(); }
  catch (error) { notice(error.message,true); } finally { e.target.value = ""; }
});

try {
  setupOffline({button:$("offline-save"),status:$("offline-status"),getChapter:() => chapter});
  manifest = await getJSON("reader-manifest.json");
  let open = false; try { open = localStorage.getItem(`lernrepo-${manifest?.course?.id || location.pathname}-sidebar-open`) === "true"; } catch {}
  setSidebarOpen(open);
  let savedNavigation = {}; try { savedNavigation = JSON.parse(localStorage.getItem(`lernrepo-${manifest?.course?.id || location.pathname}-navigation`) || "{}"); } catch {}
  setNavigation(savedNavigation.open === true,savedNavigation.tab === "thumbnails" ? "thumbnails" : "outline");
  document.title = `${manifest.course.title} · Skript hören & verstehen`;
  for (const c of manifest.chapters) { const option = document.createElement("option"); option.value = c.number; option.textContent = `${c.number} · ${c.title}${c.audio ? "" : " (ohne Audio)"}`; $("chapters").append(option); }
  const requested = Number(new URLSearchParams(location.search).get("chapter"));
  const first = manifest.chapters.find(c => c.number === requested) || manifest.chapters.find(c => c.audio) || manifest.chapters[0];
  if (!first) throw new Error("Das Paket enthält noch keine Kapitel.");
  await loadChapter(first.number);
} catch (error) { console.error(error); notice(`Reader konnte nicht geladen werden: ${error.message}`,true); }
