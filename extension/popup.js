"use strict";
const code = document.querySelector("#code");
const share = document.querySelector("#share");
const status = document.querySelector("#status");
const follow = document.querySelector("#follow");
let following = false;

function tokenValue() {
  const token = code.value.trim();
  if (!/^[a-f0-9]{48}$/.test(token)) {
    status.textContent = "Copy the pairing code from the desktop home's Settings and paste it above.";
    code.focus();
    return null;
  }
  return token;
}

async function init() {
  try {
    const saved = await chrome.storage.local.get(["pairingCode", "following"]);
    code.value = saved.pairingCode || "";
    following = !!saved.following;
    follow.textContent = following ? "Stop following" : "Start following focused pages";
    if (chrome.storage.local.setAccessLevel) {
      await chrome.storage.local.setAccessLevel({accessLevel: "TRUSTED_CONTEXTS"});
    }
  } catch {
    status.textContent = "Couldn't load your pairing code. Paste it again to continue.";
  }
}

share.addEventListener("click", async () => {
  const token = tokenValue();
  if (!token) return;
  share.disabled = true;
  status.textContent = "Reading visible page text…";
  try {
    await chrome.storage.local.set({pairingCode: token});
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.id || !/^https?:\/\//.test(tab.url || "")) {
      throw new Error("Open a normal website first. Browser settings, new tabs and local files cannot be shared.");
    }
    let results;
    try {
      results = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: readPage});
    } catch {
      throw new Error("This browser page is protected. Try an ordinary website or article.");
    }
    const page = results[0]?.result;
    if (!page) throw new Error("No readable page was returned. Reload the page and try again.");
    let response;
    try {
      response = await fetch("http://127.0.0.1:17373/page", {
        method: "POST", headers: {"Content-Type": "application/json", "Authorization": `Bearer ${token}`},
        body: JSON.stringify({...page, automatic: false}), signal: AbortSignal.timeout(5000)
      });
    } catch {
      throw new Error("Can't reach the house. Launch Screen Squatters and try again. Allow local network access if your browser asks.");
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Couldn't share this page.");
    status.textContent = result.characters ? `Shared ${result.characters.toLocaleString()} characters with the house!` : "Shared, but no visible text was found. Try a text-based page.";
  } catch (error) {
    status.textContent = error.message || "Something went wrong. Try again.";
  } finally {
    share.disabled = false;
  }
});

follow.addEventListener("click", async () => {
  const token = tokenValue();
  if (!token) return;
  follow.disabled = true;
  try {
    if (following) {
      await chrome.storage.local.set({following: false});
      await chrome.scripting.unregisterContentScripts({ids: ["squatters-follow"]}).catch(() => {});
      following = false;
      status.textContent = "Following stopped. Previously shared snapshots remain until cleared in the home app.";
    } else {
      const granted = await chrome.permissions.request({origins: ["http://*/*", "https://*/*"]});
      if (!granted) throw new Error("Website access wasn't granted. Share this page still works without following.");
      await chrome.storage.local.set({pairingCode: token});
      await chrome.scripting.unregisterContentScripts({ids: ["squatters-follow"]}).catch(() => {});
      await chrome.scripting.registerContentScripts([{
        id: "squatters-follow", matches: ["http://*/*", "https://*/*"],
        js: ["reader.js", "watch.js"], runAt: "document_idle", allFrames: false,
        persistAcrossSessions: true
      }]);
      await chrome.storage.local.set({following: true});
      following = true;
      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      if (tab?.id && /^https?:\/\//.test(tab.url || "")) {
        await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["reader.js", "watch.js"]}).catch(() => {});
      }
      status.textContent = "Following focused pages while housemates are awake. Other existing tabs may need a reload. AI hangout turns can send this text to OpenAI.";
    }
  } catch (error) {
    status.textContent = error.message || "Couldn't change following. Try again.";
  } finally {
    follow.textContent = following ? "Stop following" : "Start following focused pages";
    follow.disabled = false;
  }
});
init();
