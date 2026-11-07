"use strict";
const BRIDGE = "http://127.0.0.1:17373";
const HOSTS = ["http://*/*", "https://*/*"];
const READER = "squatters-follow";
let feed = {state: "off", last_sent: 0, title: "", message: "Live updates are off."};
let inFlight = false;
let epoch = 0;
let lastBadge = "";
const sessionID = crypto.randomUUID();
let sequence = 0;

async function setFeed(state, message, extra = {}) {
  feed = {...feed, ...extra, state, message};
  const badge = state === "live" ? "LIVE" : state === "off" ? "" : state === "error" ? "!" : "…";
  if (badge === lastBadge) return;
  lastBadge = badge;
  await browser.action.setBadgeText({text: badge});
  await browser.action.setBadgeBackgroundColor({color: state === "live" ? "#428d79" : "#665283"});
}

async function bridge(path, token, body) {
  let response;
  try {
    response = await fetch(BRIDGE+path, {method: "POST",
      headers: {"Authorization": `Bearer ${token}`, "Content-Type": "application/json"},
      body: JSON.stringify({...body, session_id: sessionID, sequence: ++sequence}), signal: AbortSignal.timeout(3000)});
  } catch {throw new Error("Can't reach the house. Open the desktop app; live updates will reconnect automatically.");}
  if (!response.ok) throw new Error(response.status === 403 ? "Pairing code rejected. Copy it again from the house's Settings." : `Desktop bridge error (${response.status}).`);
  return response.json();
}

async function focusedTab(tabId) {
  const [tab] = await browser.tabs.query({active: true, lastFocusedWindow: true});
  if (!tab || (tabId !== undefined && tab.id !== tabId)) return null;
  const window = await browser.windows.get(tab.windowId);
  return window.focused ? tab : null;
}

async function inactive(state) {
  const saved = await browser.storage.local.get(["following", "pairingCode"]);
  if (!saved.following) return;
  epoch++;
  try {
    await bridge("/browser-state", saved.pairingCode, {state});
    await setFeed("waiting", state === "blocked" ? "This page is protected by Firefox." : "Waiting for a focused webpage.");
  } catch (error) {await setFeed("error", error.message || "Open the desktop house to reconnect.");}
}

async function sampleActive() {
  const saved = await browser.storage.local.get("following");
  if (!saved.following) return;
  const tab = await focusedTab();
  if (!tab) return inactive("inactive");
  if (!/^https?:\/\//.test(tab.url || "")) return inactive("blocked");
  try {
    await browser.scripting.executeScript({target: {tabId: tab.id}, files: ["reader.js", "watch.js"]});
    await browser.tabs.sendMessage(tab.id, {type: "sample-now"});
  } catch {await inactive("blocked");}
}

async function configure(enabled) {
  const saved = await browser.storage.local.get("pairingCode");
  if (!/^[a-f0-9]{48}$/.test(saved.pairingCode || "")) throw new Error("Paste the desktop pairing code first.");
  if (enabled && !await browser.permissions.contains({origins: HOSTS})) throw new Error("Website access is required to keep the current page updated.");
  epoch++;
  await browser.storage.local.set({following: !!enabled});
  await browser.scripting.unregisterContentScripts({ids: [READER]}).catch(() => {});
  if (enabled) {
    await browser.scripting.registerContentScripts([{id: READER, matches: HOSTS,
      js: ["reader.js", "watch.js"], runAt: "document_idle", allFrames: false, persistAcrossSessions: true}]);
    await setFeed("waiting", "Live updates enabled. Focus a webpage to start.");
    // Install into existing tabs too. Hidden tabs don't read until focused.
    const tabs = await browser.tabs.query({url: HOSTS});
    await Promise.allSettled(tabs.filter(tab => !tab.incognito).map(tab => browser.scripting.executeScript({target: {tabId: tab.id}, files: ["reader.js", "watch.js"]})));
    await sampleActive();
  } else {
    await bridge("/browser-state", saved.pairingCode, {state: "paused"}).catch(() => {});
    await setFeed("off", "Live updates paused. The desktop browser snapshot was cleared.");
  }
  return {ok: true, enabled: !!enabled};
}

async function deliver(page, sender) {
  const saved = await browser.storage.local.get(["following", "pairingCode"]);
  if (!saved.following || inFlight || sender.frameId !== 0 || sender.tab?.incognito) return {ok: false};
  const tab = await focusedTab(sender.tab.id);
  if (!tab) return {ok: false};
  // Firefox may retain the original document URL in MessageSender after pushState.
  // Verify origin against the sender, and route against the current queried tab.
  const url = new URL(page?.url), source = new URL(sender.url), current = new URL(tab.url);
  if (!/^https?:$/.test(url.protocol) || url.origin !== source.origin || url.origin !== current.origin || url.pathname !== current.pathname ||
      typeof page.text !== "string" || page.text.length > 24000 || typeof page.title !== "string") return {ok: false};
  url.search = ""; url.hash = ""; url.username = ""; url.password = "";
  inFlight = true;
  const generation = epoch;
  try {
    // Recheck after async work: never forward an old tab after the user switches tabs.
    if (generation !== epoch || !await focusedTab(sender.tab.id)) return {ok: false};
    const result = await bridge("/page", saved.pairingCode, {...page, title: page.title.slice(0, 300), url: url.href,
      automatic: true, browser: "firefox", targets: Array.isArray(page.targets) ? page.targets.slice(0,12) : []});
    if (generation === epoch) await setFeed("live", "Updating the house continuously, including while companions sleep.", {title: page.title.slice(0, 120), last_sent: Date.now()});
    return {ok: true, characters: result.characters};
  } catch (error) {
    await setFeed("error", error.message || "Can't reach the house. Open the desktop app; the feed will retry automatically.");
    return {ok: false};
  } finally {inFlight = false;}
}

browser.runtime.onMessage.addListener((message, sender) => {
  if (message?.type === "may-observe" && sender.tab && sender.frameId === 0) {
    return browser.storage.local.get("following").then(saved => ({following: !!saved.following && !sender.tab.incognito}));
  }
  if (message?.type === "focused-page" && sender.tab && sender.frameId === 0) return deliver(message.page, sender).catch(() => ({ok: false}));
  const popup = !sender.tab && sender.url === browser.runtime.getURL("popup.html");
  if (!popup) return undefined;
  if (message?.type === "get-feed-status") return browser.storage.local.get("following").then(saved => ({...feed, enabled: !!saved.following}));
  if (message?.type === "configure-stream") return configure(!!message.enabled).catch(error => ({ok: false, error: error.message}));
  return undefined;
});

browser.tabs.onActivated.addListener(() => {epoch++; inactive("loading").then(sampleActive).catch(() => {});});
browser.tabs.onUpdated.addListener((id, changes, tab) => {
  if (!tab.active) return;
  if (changes.status === "loading" || changes.url) {epoch++; inactive("loading").catch(() => {});}
  if (changes.status === "complete") sampleActive().catch(() => {});
});
browser.windows.onFocusChanged.addListener(() => {epoch++; sampleActive().catch(() => {});});
browser.permissions.onRemoved.addListener(() => {
  browser.permissions.contains({origins: HOSTS}).then(granted => granted ? undefined : configure(false)).catch(() => {});
});
browser.runtime.onStartup.addListener(() => browser.storage.local.get("following").then(saved => saved.following ? configure(true) : undefined).catch(() => {}));
browser.storage.local.get("following").then(saved => saved.following ? configure(true) : setFeed("off", "Live updates are off.")).catch(() => {});
