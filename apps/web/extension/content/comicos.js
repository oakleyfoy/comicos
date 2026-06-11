const READY_EVENT = "comicos_midtown_extension_ready";
const PING_EVENT = "comicos_midtown_extension_ping";
const REQUEST_EVENT = "comicos_midtown_capture_request";
const RESULT_EVENT = "comicos_midtown_capture_result";
const ERROR_EVENT = "comicos_midtown_capture_error";
const STATUS_EVENT = "comicos_midtown_extension_status";

function isMidtownPage() {
  return /(^|\.)midtowncomics\.com$/i.test(location.hostname);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeWhitespace(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function countTextMatches(text, pattern) {
  const matches = String(text || "").match(pattern);
  return matches ? matches.length : 0;
}

function isVisibleElement(element) {
  if (!element || typeof element.getClientRects !== "function") {
    return false;
  }
  const rects = element.getClientRects();
  if (!rects || rects.length === 0) {
    return false;
  }
  const style = window.getComputedStyle(element);
  return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
}

function extractOrderNumberFromText(text) {
  const normalized = normalizeWhitespace(text);
  const patterns = [
    /\border\s*#\s*([0-9]{4,})\b/i,
    /\border\s+number\s*[:#]?\s*([0-9]{4,})\b/i,
    /\border\s+([0-9]{4,})\b/i,
  ];
  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    if (match && match[1]) {
      return match[1].trim();
    }
  }
  return null;
}

function extractOrderNumberFromUrl(url) {
  if (!url) {
    return null;
  }
  const match = String(url).match(/\/([0-9]{4,})(?:[/?#]|$)/);
  return match && match[1] ? match[1].trim() : null;
}

async function waitForDocumentComplete() {
  let attempts = 0;
  while (document.readyState !== "complete" && attempts < 80) {
    await sleep(100);
    attempts += 1;
  }
}

async function autoScrollMidtownPage() {
  const viewport = Math.max(window.innerHeight || 0, 1);
  const step = Math.max(Math.floor(viewport * 0.85), 240);
  let previousScrollTop = -1;
  window.scrollTo(0, 0);
  await sleep(200);

  for (let safety = 0; safety < 60; safety += 1) {
    const maxScrollTop = Math.max((document.documentElement?.scrollHeight || 0) - viewport, 0);
    const currentScrollTop = Math.max(window.scrollY || 0, 0);
    if (currentScrollTop >= maxScrollTop || currentScrollTop === previousScrollTop) {
      break;
    }
    previousScrollTop = currentScrollTop;
    window.scrollBy(0, step);
    await sleep(250);
  }

  window.scrollTo(0, 0);
  await sleep(250);
}

function countVisibleOrderItemBlocks() {
  const selectors = [
    "tr",
    "li",
    "article",
    "[data-midtown-item]",
    "[data-order-item]",
    "[data-testid*='item']",
  ];
  const seen = new Set();
  const candidates = [];
  for (const selector of selectors) {
    for (const element of document.querySelectorAll(selector)) {
      if (seen.has(element)) {
        continue;
      }
      seen.add(element);
      candidates.push(element);
    }
  }

  const hasProductLink = (element) =>
    Boolean(element.querySelector("a[href*='/product/'], a[href*='product/'], a[href*='product']"));

  let count = 0;
  for (const element of candidates) {
    if (!isVisibleElement(element)) {
      continue;
    }
    const text = normalizeWhitespace(element.innerText);
    if (!text) {
      continue;
    }
    if ((/Each:/i.test(text) || /QTY:/i.test(text) || /Status:/i.test(text)) && hasProductLink(element)) {
      count += 1;
    }
  }

  if (count > 0) {
    return count;
  }

  for (const element of document.querySelectorAll("div")) {
    if (!isVisibleElement(element)) {
      continue;
    }
    const text = normalizeWhitespace(element.innerText);
    if (!text) {
      continue;
    }
    if ((/Each:/i.test(text) || /QTY:/i.test(text) || /Status:/i.test(text)) && hasProductLink(element)) {
      count += 1;
    }
  }

  return count;
}

function collectMidtownCaptureDiagnostics() {
  const bodyText = document.body && document.body.innerText ? document.body.innerText : "";
  const bodyHtml = document.body && document.body.innerHTML ? document.body.innerHTML : "";
  const html = document.documentElement ? document.documentElement.outerHTML : "";
  const imageCount = document.images ? document.images.length : document.querySelectorAll("img").length;
  const productLinkCount = document.querySelectorAll(
    "a[href*='/product/'], a[href*='product/'], a[href*='product']",
  ).length;
  const visibleOrderItemBlockCount = countVisibleOrderItemBlocks();
  return {
    current_url: location.href,
    ready_state: document.readyState,
    html_length: html.length,
    text_length: bodyText.length,
    body_inner_html_length: bodyHtml.length,
    body_inner_text_length: bodyText.length,
    image_count: imageCount,
    product_link_count: productLinkCount,
    visible_order_item_block_count: visibleOrderItemBlockCount,
    items_detected_client_side: visibleOrderItemBlockCount || productLinkCount,
    each_match_count: countTextMatches(bodyText, /\bEach:/gi),
    qty_match_count: countTextMatches(bodyText, /\bQTY:/gi),
    status_match_count: countTextMatches(bodyText, /\bStatus:/gi),
    scroll_height: document.documentElement ? document.documentElement.scrollHeight : 0,
    scroll_position: window.scrollY || 0,
  };
}

function buildMidtownPayload(pageHtml, pageUrl, pageTitle, pageText, captureDiagnostics) {
  const bodyText = normalizeWhitespace(pageText).toLowerCase();
  const htmlText = normalizeWhitespace(pageHtml).toLowerCase();
  const titleText = normalizeWhitespace(pageTitle).toLowerCase();
  const orderNumber =
    extractOrderNumberFromText(bodyText) ||
    extractOrderNumberFromText(htmlText) ||
    extractOrderNumberFromText(titleText) ||
    extractOrderNumberFromUrl(pageUrl);
  return JSON.parse(
    JSON.stringify({
      detail_url: pageUrl || location.href,
      retailer_order_number: orderNumber,
      fallback_order_number: orderNumber,
      html: pageHtml,
      capture_diagnostics: captureDiagnostics || null,
    }),
  );
}

async function captureMidtownDetailPage() {
  await waitForDocumentComplete();
  await autoScrollMidtownPage();
  const pageHtml = document.documentElement.outerHTML;
  const pageText = document.body && document.body.innerText ? document.body.innerText : "";
  const diagnostics = collectMidtownCaptureDiagnostics();
  console.info("[Comicos Midtown Extension] content script returning diagnostics", {
    url: location.href,
    items_detected_client_side: diagnostics.items_detected_client_side,
    html_length: diagnostics.html_length,
  });
  return buildMidtownPayload(pageHtml, location.href, document.title, pageText, diagnostics);
}

function dispatchReady() {
  window.dispatchEvent(new CustomEvent(READY_EVENT, { detail: { installed: true } }));
}

function dispatchResult(message) {
  window.dispatchEvent(new CustomEvent(RESULT_EVENT, { detail: message }));
}

function dispatchError(message) {
  window.dispatchEvent(new CustomEvent(ERROR_EVENT, { detail: message }));
}

function dispatchStatus(message) {
  window.dispatchEvent(new CustomEvent(STATUS_EVENT, { detail: message }));
}

console.info("[Comicos Midtown Extension] content script loaded", {
  url: location.href,
  page: isMidtownPage() ? "midtown" : "comicos",
});
dispatchReady();

window.addEventListener(PING_EVENT, dispatchReady);

window.addEventListener(REQUEST_EVENT, (event) => {
  console.info("[Comicos Midtown Extension] content script received capture request", {
    url: location.href,
    page: isMidtownPage() ? "midtown" : "comicos",
  });
  chrome.runtime.sendMessage(
    {
      type: REQUEST_EVENT,
      payload: event.detail,
    },
    (response) => {
      if (chrome.runtime.lastError) {
        dispatchError({
          message: chrome.runtime.lastError.message || "Midtown extension is unavailable.",
        });
      }
    },
  );
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") {
    return;
  }
  if (message.type === REQUEST_EVENT && isMidtownPage()) {
    // The background asks the Midtown tab itself to capture the live DOM.
    console.info("[Comicos Midtown Extension] content script received capture request", {
      url: location.href,
      page: "midtown",
    });
    captureMidtownDetailPage()
      .then((payload) => {
        sendResponse({ ok: true, payload });
      })
      .catch((error) => {
        sendResponse({
          ok: false,
          error: error instanceof Error && error.message ? error.message : "Midtown capture failed.",
        });
      });
    return true;
  }
  if (message.type === RESULT_EVENT) {
    console.info("[Comicos Midtown Extension] content script returning diagnostics", {
      url: location.href,
      stage: "result",
    });
    dispatchResult(message);
    return;
  }
  if (message.type === ERROR_EVENT) {
    dispatchError(message);
    return;
  }
  if (message.type === STATUS_EVENT) {
    dispatchStatus(message);
  }
});
