"use strict";
const code = document.querySelector("#code");
const share = document.querySelector("#share");
const status = document.querySelector("#status");

// Runs in the page's isolated extension world. No page-supplied code is evaluated.
function readPage() {
  const root = document.querySelector("main, [role='main'], article") || document.body;
  if (!root) throw new Error("This page has no readable document.");
  const chunks = [];
  let size = 0;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent || !node.textContent.trim()) return NodeFilter.FILTER_REJECT;
      if (parent.closest("script,style,noscript,template,input,textarea,select,option,[contenteditable]:not([contenteditable='false']),[hidden],[aria-hidden='true']")) return NodeFilter.FILTER_REJECT;
      if (typeof parent.checkVisibility === "function" && !parent.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return NodeFilter.FILTER_REJECT;
      if (getComputedStyle(parent).visibility === "hidden" || !parent.getClientRects().length) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  while (walker.nextNode() && size < 24000) {
    const chunk = walker.currentNode.textContent.replace(/\s+/g, " ").trim();
    chunks.push(chunk);
    size += chunk.length + 1;
  }
  const url = new URL(location.href);
  url.search = "";
  url.hash = "";
  url.username = "";
  url.password = "";
  return {title: document.title.slice(0, 300), url: url.href, text: chunks.join("\n").slice(0, 24000)};
}

async function init() {
  try {
    const saved = await chrome.storage.local.get("pairingCode");
    code.value = saved.pairingCode || "";
    if (chrome.storage.local.setAccessLevel) {
      await chrome.storage.local.setAccessLevel({accessLevel: "TRUSTED_CONTEXTS"});
    }
  } catch {
    status.textContent = "Couldn't load your pairing code. Paste it again to continue.";
  }
}

share.addEventListener("click", async () => {
  const token = code.value.trim();
  if (!/^[a-f0-9]{48}$/.test(token)) {
    status.textContent = "Copy the pairing code from Pip's Settings and paste it above.";
    code.focus();
    return;
  }
  share.disabled = true;
  status.textContent = "Reading this page…";
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
        method: "POST",
        headers: {"Content-Type": "application/json", "Authorization": `Bearer ${token}`},
        body: JSON.stringify(page),
        signal: AbortSignal.timeout(5000)
      });
    } catch {
      throw new Error("Can't reach Pip. Launch the desktop app, then try again. Allow local network access if your browser asks.");
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Pip couldn't receive this page.");
    status.textContent = result.characters ? `Shared ${result.characters.toLocaleString()} characters. Ask Pip about it on your desktop!` : "Shared, but no readable text was found. Try a text-based page.";
  } catch (error) {
    status.textContent = error.message || "Something went wrong. Try again.";
  } finally {
    share.disabled = false;
  }
});
init();
