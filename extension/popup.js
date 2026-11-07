"use strict";
const code = document.querySelector("#code");
const share = document.querySelector("#share");
const status = document.querySelector("#status");
const follow = document.querySelector("#follow");
const feed = document.querySelector("#feed");
let following = false;

function tokenValue() {
  const token = code.value.trim();
  if (!/^[a-f0-9]{48}$/.test(token)) {
    status.textContent = "Copy the pairing code from the house's Settings first.";
    code.focus(); return null;
  }
  return token;
}
async function refresh() {
  try {
    const state = await browser.runtime.sendMessage({type: "get-feed-status"});
    following = !!state.enabled;
    follow.textContent = following ? "Pause live updates" : "Enable live updates";
    const age = state.last_sent ? Math.round((Date.now()-state.last_sent)/1000) : null;
    feed.textContent = !following ? "OFF · single-page sharing is still available" : state.state === "live"
      ? age < 6 ? `LIVE · updated ${age}s ago\n${state.title}` : `Waiting for the focused page · last update ${age}s ago`
      : state.message;
  } catch {feed.textContent = "Open the extension again to reconnect.";}
}
share.addEventListener("click", async () => {
  const token = tokenValue(); if (!token) return;
  share.disabled = true;
  try {
    await browser.storage.local.set({pairingCode: token});
    const [tab] = await browser.tabs.query({active: true, currentWindow: true});
    if (!tab?.id || tab.incognito || !/^https?:\/\//.test(tab.url || "")) throw new Error("Open an ordinary, non-private webpage first.");
    const results = await browser.scripting.executeScript({target: {tabId: tab.id}, func: readPage});
    const page = results[0]?.result;
    if (!page) throw new Error("This page couldn't be read. Firefox protects some internal and add-on pages.");
    const response = await fetch("http://127.0.0.1:17373/page", {method: "POST",
      headers: {"Content-Type": "application/json", "Authorization": `Bearer ${token}`},
      body: JSON.stringify({...page, automatic: false}), signal: AbortSignal.timeout(3000)});
    if (!response.ok) throw new Error(response.status === 403 ? "Pairing code rejected. Copy it again from the house." : "Couldn't share this page.");
    status.textContent = "Shared this page, its metadata and available captions.";
  } catch (error) {status.textContent = error.message === "NetworkError when attempting to fetch resource." ? "Open the desktop house, then try again." : error.message || "Open the desktop house, then try again.";}
  finally {share.disabled = false;}
});
follow.addEventListener("click", async () => {
  const token = tokenValue(); if (!token) return;
  follow.disabled = true;
  try {
    if (!following && !await browser.permissions.request({origins: ["http://*/*", "https://*/*"]})) throw new Error("Website access wasn't granted. Single-page sharing still works.");
    await browser.storage.local.set({pairingCode: token});
    const result = await browser.runtime.sendMessage({type: "configure-stream", enabled: !following});
    if (!result?.ok) throw new Error(result?.error || "Couldn't change live updates.");
    status.textContent = result.enabled ? "Live feed enabled. Focus a webpage; changes and metadata refresh automatically." : "Live feed paused and the desktop browser snapshot cleared.";
    await refresh();
  } catch (error) {status.textContent = error.message || "Couldn't change live updates.";}
  finally {follow.disabled = false;}
});
browser.storage.local.get("pairingCode").then(saved => {code.value = saved.pairingCode || "";}).catch(() => {});
refresh();
setInterval(refresh, 1000);
