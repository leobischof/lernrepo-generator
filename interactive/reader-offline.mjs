export function rangeBounds(header,size) {
  const match = /^bytes=(\d*)-(\d*)$/.exec(header || "");
  if (!match || !match[1] && !match[2] || size <= 0) return null;
  const start = match[1] ? Number(match[1]) : Math.max(0,size-Number(match[2]));
  const end = match[1] && match[2] ? Math.min(size-1,Number(match[2])) : size-1;
  return Number.isSafeInteger(start) && Number.isSafeInteger(end) && start >= 0 && start <= end && start < size ? [start,end] : null;
}

export async function setupOffline({button,status,getChapter}) {
  if (globalThis.LEARNREPO_EMBEDDED) { button.hidden = true; status.textContent = "Diese Kapiteldatei enthält PDF und Audio bereits vollständig."; return; }
  if (!isSecureContext || !("serviceWorker" in navigator)) {
    button.disabled = true; status.textContent = "PWA-Offlinebetrieb benötigt HTTPS oder localhost. Auf iOS: in Safari zum Home-Bildschirm hinzufügen."; return;
  }
  try {
    const hadController = Boolean(navigator.serviceWorker.controller);
    navigator.serviceWorker.addEventListener("controllerchange",() => {
      if (hadController) location.reload();
    },{once:true});
    await navigator.serviceWorker.register("./reader-service-worker.mjs",{type:"module"});
    const registration = await navigator.serviceWorker.ready;
    button.disabled = false;
    status.textContent = "Für die Offline-Nutzung das gewünschte Kapitel speichern. Installation über das Browser-Menü; iOS: Zum Home-Bildschirm.";
    button.addEventListener("click",() => {
      const chapter = getChapter();
      if (!chapter) { status.textContent = "Bitte zuerst ein Kapitel laden."; return; }
      button.disabled = true;
      const channel = new MessageChannel();
      channel.port1.onmessage = ({data}) => {
        status.textContent = data.message;
        if (data.done || data.error) button.disabled = false;
      };
      registration.active.postMessage({type:"CACHE_CHAPTER",number:chapter.number},[channel.port2]);
    });
  } catch (error) { button.disabled = true; status.textContent = `Offline-Einrichtung nicht verfügbar: ${error.message}`; }
}
