// PDF.js supplies document outlines and page rendering; thumbnails load only near the viewport.
export class DocumentNavigation {
  constructor({outline,thumbnails,scrollRoot,onChapter,onDestination,onPage,onError}) {
    Object.assign(this,{outline,thumbnails,scrollRoot,onChapter,onDestination,onPage,onError});
    this.sequence = 0; this.queue = []; this.jobs = new Set(); this.renderTasks = new Set();
  }
  async setDocument(doc,chapters,current) {
    const sequence = ++this.sequence;
    this.observer?.disconnect(); this.queue = [];
    for (const task of this.renderTasks) task.cancel();
    this.outline.replaceChildren(); this.thumbnails.replaceChildren(); this.doc = doc;
    let currentItem;
    for (const c of chapters) {
      const item = document.createElement("div"), button = document.createElement("button");
      item.className = "outline-chapter"; button.className = "chapter-link";
      button.textContent = `${c.number} · ${c.title}`;
      if (c.number === current) { button.setAttribute("aria-current","page"); currentItem = item; }
      button.addEventListener("click",() => this.onChapter(c.number)); item.append(button); this.outline.append(item);
    }
    if (!doc) return;
    try {
      const outline = await doc.getOutline();
      if (sequence !== this.sequence) return;
      if (outline?.length && currentItem) currentItem.append(this.outlineList(outline));
    } catch (error) { if (sequence === this.sequence) this.onError(error); }
    if (sequence !== this.sequence) return;
    const observer = typeof IntersectionObserver !== "undefined" ? new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) {
        observer.unobserve(entry.target); this.queue.push({doc,sequence,button:entry.target});
      }
      this.pump();
    },{root:this.scrollRoot,rootMargin:"200px"}) : null;
    this.observer = observer;
    for (let page = 1; page <= doc.numPages; page++) {
      const button = document.createElement("button"), frame = document.createElement("div"), caption = document.createElement("span");
      button.className = "page-thumbnail"; button.dataset.page = page;
      button.setAttribute("aria-label",`Zu PDF-Seite ${page}`);
      frame.className = "thumbnail-frame"; caption.textContent = `Seite ${page}`;
      button.append(frame,caption); button.addEventListener("click",() => this.onPage(page)); this.thumbnails.append(button);
      if (observer) observer.observe(button); else this.queue.push({doc,sequence,button});
    }
    this.pump(); this.setCurrentPage(1);
  }
  outlineList(items) {
    const list = document.createElement("ul");
    for (const item of items) {
      const row = document.createElement("li"), label = document.createElement(item.dest ? "button" : "span");
      label.textContent = item.title;
      if (item.dest) label.addEventListener("click",() => this.onDestination(item.dest));
      row.append(label);
      if (item.items?.length) row.append(this.outlineList(item.items));
      list.append(row);
    }
    return list;
  }
  pump() {
    while (this.jobs.size < 2 && this.queue.length) {
      const job = this.queue.shift();
      if (job.sequence !== this.sequence) continue;
      const promise = this.renderThumbnail(job).catch(error => {
        if (job.sequence === this.sequence && error.name !== "RenderingCancelledException") {
          job.button.querySelector(".thumbnail-frame").textContent = "Vorschau nicht verfügbar";
        }
      }).finally(() => { this.jobs.delete(promise); this.pump(); });
      this.jobs.add(promise);
    }
  }
  async renderThumbnail({doc,sequence,button}) {
    const page = await doc.getPage(Number(button.dataset.page));
    if (sequence !== this.sequence) return;
    const viewport = page.getViewport({scale:1}), scale = 140/viewport.width;
    const small = page.getViewport({scale}), ratio = Math.min(devicePixelRatio || 1,1.5);
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(small.width*ratio); canvas.height = Math.ceil(small.height*ratio);
    const task = page.render({canvasContext:canvas.getContext("2d"),viewport:small,transform:ratio === 1 ? null : [ratio,0,0,ratio,0,0]});
    this.renderTasks.add(task);
    try { await task.promise; if (sequence === this.sequence) button.querySelector(".thumbnail-frame").replaceChildren(canvas); }
    finally { this.renderTasks.delete(task); }
  }
  setCurrentPage(page) {
    for (const button of this.thumbnails.children) {
      if (Number(button.dataset.page) === page) button.setAttribute("aria-current","page");
      else button.removeAttribute("aria-current");
    }
  }
}
