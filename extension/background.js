"use strict";
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message?.type === "may-observe" && sender.tab && sender.frameId === 0) {
    chrome.storage.local.get("following").then(saved => respond({following: !!saved.following}));
    return true;
  }
  if (message?.type !== "focused-page" || !sender.tab || sender.frameId !== 0) return false;
  (async () => {
    const saved = await chrome.storage.local.get(["following", "pairingCode"]);
    if (!saved.following || !/^[a-f0-9]{48}$/.test(saved.pairingCode || "")) return;
    const [active] = await chrome.tabs.query({active: true, windowId: sender.tab.windowId});
    const window = await chrome.windows.get(sender.tab.windowId);
    if (!window.focused || active?.id !== sender.tab.id) return;
    const page = message.page;
    if (!page || typeof page.text !== "string" || page.text.length > 24000 || typeof page.title !== "string") return;
    const url = new URL(page.url);
    const source = new URL(sender.url);
    if (!/^https?:$/.test(url.protocol) || url.origin !== source.origin || url.pathname !== source.pathname) return;
    url.search = ""; url.hash = ""; url.username = ""; url.password = "";
    const headers = {"Authorization": `Bearer ${saved.pairingCode}`, "Content-Type": "application/json"};
    const status = await fetch("http://127.0.0.1:17373/status", {headers, signal: AbortSignal.timeout(2500)});
    if (!status.ok || !(await status.json()).awake) return;
    await fetch("http://127.0.0.1:17373/page", {
      method: "POST", headers, signal: AbortSignal.timeout(3000),
      body: JSON.stringify({title: page.title.slice(0, 300), text: page.text, url: url.href, automatic: true,
                            targets: Array.isArray(page.targets) ? page.targets.slice(0, 12) : [], viewport: page.viewport || {}})
    });
  })().then(() => respond({ok: true})).catch(() => respond({ok: false}));
  return true;
});
