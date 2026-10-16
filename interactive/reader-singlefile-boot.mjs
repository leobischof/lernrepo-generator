const element = document.getElementById("lernrepo-payload");
const pack = JSON.parse(element.textContent); element.remove();
function decode64(text) {
  const padding = text.endsWith("==") ? 2 : text.endsWith("=") ? 1 : 0;
  const bytes = new Uint8Array(text.length*3/4-padding);
  let offset = 0;
  for (let i = 0; i < text.length; i += 65536) {
    const chunk = atob(text.slice(i,i+65536));
    for (let j = 0; j < chunk.length; j++) bytes[offset++] = chunk.charCodeAt(j);
  }
  return bytes;
}
const text = encoded => new TextDecoder().decode(decode64(encoded));
const moduleURL = source => URL.createObjectURL(new Blob([source],{type:"text/javascript"}));
const core = moduleURL(text(pack.modules.core));
const viewer = moduleURL(`import ${JSON.stringify(core)};\n${text(pack.modules.viewer)}`);
const timeline = moduleURL(text(pack.modules.timeline));
const navigation = moduleURL(text(pack.modules.navigation));
const offline = moduleURL(text(pack.modules.offline));
const workerURL = moduleURL(text(pack.modules.worker));
const chapter = pack.manifest.chapters[0];
chapter.pdf = URL.createObjectURL(new Blob([decode64(pack.pdf)],{type:"application/pdf"}));
chapter.audio = pack.audio ? URL.createObjectURL(new Blob([decode64(pack.audio)],{type:pack.audio_mime})) : null;
class EmbeddedBinaryDataFactory {
  async fetch({kind,filename}) {
    const encoded = pack.binary[kind]?.[filename];
    if (!encoded) throw new Error(`Eingebettete PDF-Ressource fehlt: ${kind}/${filename}`);
    return decode64(encoded);
  }
}
globalThis.LEARNREPO_EMBEDDED = {workerURL,json:{"reader-manifest.json":pack.manifest,[chapter.timeline]:pack.timeline},
  pdfOptions:{BinaryDataFactory:EmbeddedBinaryDataFactory,useWorkerFetch:false}};
const app = text(pack.modules.app)
  .replaceAll('"./vendor/build/pdf.mjs"',JSON.stringify(core))
  .replaceAll('"./vendor/web/pdf_viewer.mjs"',JSON.stringify(viewer))
  .replaceAll('"./reader-timeline.mjs"',JSON.stringify(timeline))
  .replaceAll('"./reader-navigation.mjs"',JSON.stringify(navigation))
  .replaceAll('"./reader-offline.mjs"',JSON.stringify(offline));
delete pack.modules; delete pack.pdf; delete pack.audio;
await import(moduleURL(app));
