"use strict";
if (!globalThis.__screenSquattersWatching) {
  globalThis.__screenSquattersWatching = true;
  const observe = async () => {
    if (document.visibilityState !== "visible" || !document.hasFocus()) return;
    try {
      // Pairing credentials stay in trusted extension contexts, never the page script.
      const state = await chrome.runtime.sendMessage({type: "may-observe"});
      if (!state?.following) return;
      await chrome.runtime.sendMessage({type: "focused-page", page: {...readPage(), automatic: true}});
    } catch {
      // A closed/reloaded extension or desktop app shouldn't interrupt a webpage.
    }
  };
  setInterval(observe, 5000);
  observe();
}
