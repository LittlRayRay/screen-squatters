"use strict";
// Self-contained so Chrome can serialize this function into an isolated page world.
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
      if (getComputedStyle(parent).visibility !== "visible") return NodeFilter.FILTER_REJECT;
      const range = document.createRange();
      range.selectNodeContents(node);
      const visible = [...range.getClientRects()].some(rect => rect.bottom > 0 && rect.right > 0 && rect.top < innerHeight && rect.left < innerWidth);
      if (!visible) return NodeFilter.FILTER_REJECT;
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
  const targets = [];
  const viewport = {width: innerWidth, height: innerHeight, outerWidth: outerWidth || innerWidth, outerHeight: outerHeight || innerHeight};
  for (const element of root.querySelectorAll("h1,h2,h3,a,button,img,video,figcaption")) {
    if (targets.length >= 12) break;
    if (element.closest("[hidden],[aria-hidden='true'],[contenteditable]:not([contenteditable='false'])")) continue;
    if (typeof element.checkVisibility === "function" && !element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) continue;
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height || rect.bottom <= 0 || rect.right <= 0 || rect.top >= innerHeight || rect.left >= innerWidth) continue;
    const label = (element.getAttribute("alt") || element.getAttribute("aria-label") || element.innerText || "").replace(/\s+/g, " ").trim().slice(0, 80);
    if (!label || targets.some(target => target.label === label)) continue;
    targets.push({label, x: (Math.max(0, rect.left)+Math.min(innerWidth, rect.right))/2/innerWidth,
                  y: (Math.max(0, rect.top)+Math.min(innerHeight, rect.bottom))/2/innerHeight});
  }
  return {title: document.title.slice(0, 300), url: url.href, text: chunks.join("\n").slice(0, 24000), targets, viewport};
}
