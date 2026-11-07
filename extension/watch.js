"use strict";
if (!globalThis.__screenSquattersWatching) {
  globalThis.__screenSquattersWatching = true;
  const ext = browser;
  let pending = false, rerun = false, timer = null, lastRead = 0, dirty = true, snapshot = null;
  let lastURL = "";
  const observe = async () => {
    if (document.visibilityState !== "visible" || !document.hasFocus()) return;
    if (pending) {rerun = true; return;}
    if (Date.now()-lastRead < 600) {schedule(); return;}
    pending = true;
    try {
      const state = await ext.runtime.sendMessage({type: "may-observe"});
      if (!state?.following || document.visibilityState !== "visible" || !document.hasFocus()) return;
      lastRead = Date.now();
      // pushState/replaceState need not mutate the DOM or dispatch popstate.
      if (lastURL !== location.href) {dirty = true; lastURL = location.href;}
      if (dirty || !snapshot) {snapshot = readPage(); dirty = false;}
      await ext.runtime.sendMessage({type: "focused-page", page: {...snapshot, captured_at: Date.now(), automatic: true}});
    } catch {
      // Restarted extension, restricted page, or disconnected local app: next heartbeat retries.
    } finally {
      pending = false;
      if (rerun) {rerun = false; schedule();}
    }
  };
  function schedule() {
    dirty = true;
    if (timer) return;
    timer = setTimeout(() => {timer = null; observe();}, 350);
  }
  for (const event of ["scroll", "resize", "focus", "popstate", "hashchange", "pageshow"]) {
    window.addEventListener(event, schedule, {passive: true});
  }
  document.addEventListener("visibilitychange", schedule);
  for (const event of ["play", "pause", "seeked", "timeupdate", "loadedmetadata"]) document.addEventListener(event, schedule, true);
  new MutationObserver(schedule).observe(document.documentElement, {childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: ["title", "aria-hidden", "aria-label", "aria-expanded", "hidden", "src", "href", "content", "lang", "class", "style"]});
  ext.runtime.onMessage.addListener(message => {
    if (message?.type === "sample-now") {schedule(); return Promise.resolve({ok: true});}
    return undefined;
  });
  setInterval(observe, 1000);
  observe();
}
