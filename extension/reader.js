"use strict";
// Serialized by scripting.executeScript as well as loaded into isolated page worlds.
function readPage() {
  const root = document.querySelector("main, [role='main'], article") || document.body;
  if (!root) throw new Error("This page has no readable document.");
  const tidy = (value, maximum = 300) => String(value || "").replace(/\s+/g, " ").trim().slice(0, maximum);
  const safeURL = value => {
    try {
      const url = new URL(value, location.href);
      if (!/^https?:$/.test(url.protocol)) return "";
      url.search = ""; url.hash = ""; url.username = ""; url.password = "";
      return url.href.slice(0, 2048);
    } catch { return ""; }
  };
  const excluded = element => element.closest("script,style,noscript,template,input,textarea,select,option,[contenteditable]:not([contenteditable='false']),[hidden],[aria-hidden='true']");
  const shown = element => {
    if (!element || excluded(element)) return false;
    if (typeof element.checkVisibility === "function" && !element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return false;
    const style = getComputedStyle(element);
    return style.visibility === "visible" && style.display !== "none";
  };
  const inView = rect => rect.bottom > 0 && rect.right > 0 && rect.top < innerHeight && rect.left < innerWidth;
  const visible = [], article = [];
  let visibleSize = 0, articleSize = 0, visited = 0;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode() && visited++ < 6000) {
    const node = walker.currentNode;
    const text = tidy(node.textContent, 24000);
    if (!text || !shown(node.parentElement)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const rects = [...range.getClientRects()];
    if (!rects.length) continue;
    if (articleSize < 12000) {article.push(text); articleSize += text.length+1;}
    if (visibleSize < 24000 && rects.some(inView)) {visible.push(text); visibleSize += text.length+1;}
    if (articleSize >= 12000 && visibleSize >= 24000) break;
  }
  const targets = [], headings = [], links = [];
  for (const element of root.querySelectorAll("h1,h2,h3,a,button,img,video,figcaption")) {
    if (targets.length >= 12 && headings.length >= 12 && links.length >= 20) break;
    if (!shown(element)) continue;
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height || !inView(rect)) continue;
    const label = tidy(element.getAttribute("alt") || element.getAttribute("aria-label") || element.innerText || element.getAttribute("title"), 160);
    if (!label) continue;
    const tag = element.tagName.toLowerCase();
    if (/^h[123]$/.test(tag) && headings.length < 12) headings.push(label);
    if (tag === "a" && links.length < 20) {
      const url = safeURL(element.href);
      if (url) links.push({label: label.slice(0, 100), url: url.slice(0, 512)});
    }
    if (targets.length < 12 && !targets.some(item => item.label === label.slice(0, 80))) {
      targets.push({label: label.slice(0, 80), x: (Math.max(0, rect.left)+Math.min(innerWidth, rect.right))/2/innerWidth,
                    y: (Math.max(0, rect.top)+Math.min(innerHeight, rect.bottom))/2/innerHeight});
    }
  }
  const media = [], captions = [];
  const finite = value => Number.isFinite(value) ? Math.max(0, value) : null;
  for (const element of document.querySelectorAll("video,audio")) {
    if (media.length >= 4 || !shown(element)) continue;
    const rect = element.getBoundingClientRect();
    if (!inView(rect)) continue;
    media.push({kind: element.tagName.toLowerCase(), paused: !!element.paused, ended: !!element.ended,
                current_time: finite(element.currentTime), duration: finite(element.duration),
                playback_rate: finite(element.playbackRate), muted: !!element.muted});
    // Only cues that the browser exposes and is already displaying. Never enable tracks.
    for (const track of element.textTracks || []) {
      if (track.mode !== "showing") continue;
      for (const cue of track.activeCues || []) {
        const text = tidy(cue.text, 1000);
        if (text && !captions.includes(text) && captions.join(" ").length < 2000) captions.push(text);
      }
    }
  }
  const meta = selector => tidy(document.querySelector(selector)?.getAttribute("content"), 600);
  const height = Math.max(document.documentElement.scrollHeight-innerHeight, 0);
  return {
    title: tidy(document.title), url: safeURL(location.href), text: visible.join("\n").slice(0, 24000),
    page_text: article.join("\n").slice(0, 12000), targets,
    viewport: {width: innerWidth, height: innerHeight, outerWidth: outerWidth || innerWidth, outerHeight: outerHeight || innerHeight},
    metadata: {description: meta('meta[name="description"]') || meta('meta[property="og:description"]'),
               author: meta('meta[name="author"]').slice(0, 160), site_name: meta('meta[property="og:site_name"]').slice(0, 160),
               page_type: meta('meta[property="og:type"]').slice(0, 80), language: tidy(document.documentElement.lang, 40),
               canonical_url: safeURL(document.querySelector('link[rel="canonical"]')?.href || "")},
    headings, links, media, captions: captions.join("\n").slice(0, 2000),
    reading: {scroll_y: Math.round(Math.max(0, scrollY)), progress: height ? Math.min(1, Math.max(0, scrollY/height)) : 0},
    captured_at: Date.now(), browser: "firefox"
  };
}
