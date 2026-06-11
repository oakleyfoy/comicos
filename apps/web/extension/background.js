const REQUEST_EVENT = "comicos_midtown_capture_request";
const RESULT_EVENT = "comicos_midtown_capture_result";
const ERROR_EVENT = "comicos_midtown_capture_error";
const STATUS_EVENT = "comicos_midtown_extension_status";

function normalizeWhitespace(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

function logCapture(step, detail) {
  console.info("[Comicos Midtown Extension]", step, detail || {});
}

function extractPlainTextFromHtml(html) {
  return normalizeWhitespace(
    String(html || "")
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
      .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " "),
  );
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

function countTextMatches(text, pattern) {
  const matches = String(text || "").match(pattern);
  return matches ? matches.length : 0;
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

function buildMidtownPayload(pageHtml, pageUrl, pageTitle, pageText, captureDiagnostics) {
  const bodyText = normalizeWhitespace(pageText).toLowerCase();
  const htmlText = extractPlainTextFromHtml(pageHtml).toLowerCase();
  const titleText = normalizeWhitespace(pageTitle).toLowerCase();
  const orderNumber =
    extractOrderNumberFromText(bodyText) ||
    extractOrderNumberFromText(htmlText) ||
    extractOrderNumberFromText(titleText) ||
    extractOrderNumberFromUrl(pageUrl);
  const looksLikeDetailPage =
    /order\s*#?/i.test(bodyText) ||
    /tracking info/i.test(bodyText) ||
    /item status/i.test(bodyText) ||
    /order item details/i.test(bodyText) ||
    /approved/i.test(bodyText) ||
    /qty\s*:\s*\d+/i.test(bodyText) ||
    /each\s*:\s*\$?\d+/i.test(bodyText) ||
    /back-ordered|returned|not available/i.test(bodyText) ||
    /order\s*#?/i.test(titleText) ||
    /order\s*#?/i.test(htmlText);

  if (!looksLikeDetailPage) {
    throw new Error("Open the Midtown order detail page before capturing.");
  }

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

function describeError(error) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (typeof error === "string" && error) {
    return error;
  }
  if (error && typeof error === "object" && typeof error.message === "string" && error.message) {
    return error.message;
  }
  try {
    const text = JSON.stringify(error);
    if (text && text !== "{}") {
      return text;
    }
  } catch (_jsonError) {
    // ignore
  }
  return "Midtown capture failed.";
}

async function captureMidtownDetailPage() {
  await waitForDocumentComplete();
  await autoScrollMidtownPage();
  const pageHtml = document.documentElement.outerHTML;
  const pageText = document.body && document.body.innerText ? document.body.innerText : "";
  return buildMidtownPayload(
    pageHtml,
    location.href,
    document.title,
    pageText,
    collectMidtownCaptureDiagnostics(),
  );
}

async function captureMidtownDetailPageFromTab(tab) {
  if (!tab || typeof tab.url !== "string" || !tab.url) {
    throw new Error("Midtown order tab was not found.");
  }
  const response = await fetch(tab.url, {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Midtown detail page request failed (${response.status}).`);
  }
  const pageHtml = await response.text();
  const parser = new DOMParser();
  const parsedDocument = parser.parseFromString(pageHtml, "text/html");
  const parsedText = parsedDocument.body && parsedDocument.body.innerText ? parsedDocument.body.innerText : "";
  const parsedDiagnostics = {
    current_url: tab.url,
    ready_state: "complete",
    html_length: pageHtml.length,
    text_length: parsedText.length,
    body_inner_html_length: parsedDocument.body && parsedDocument.body.innerHTML ? parsedDocument.body.innerHTML.length : 0,
    body_inner_text_length: parsedText.length,
    image_count: parsedDocument.images ? parsedDocument.images.length : parsedDocument.querySelectorAll("img").length,
    product_link_count: parsedDocument.querySelectorAll("a[href*='/product/'], a[href*='product/'], a[href*='product']").length,
    visible_order_item_block_count: parsedDocument.querySelectorAll("tr, li, article").length,
    items_detected_client_side: parsedDocument.querySelectorAll("tr, li, article").length,
    each_match_count: countTextMatches(parsedText, /\bEach:/gi),
    qty_match_count: countTextMatches(parsedText, /\bQTY:/gi),
    status_match_count: countTextMatches(parsedText, /\bStatus:/gi),
    scroll_height: 0,
    scroll_position: 0,
  };
  return buildMidtownPayload(pageHtml, tab.url, tab.title || "", parsedText, parsedDiagnostics);
}

async function sendCaptureResult(targetTabId, message) {
  if (typeof targetTabId !== "number") {
    return;
  }
  await chrome.tabs.sendMessage(targetTabId, message);
}

async function sendStatus(targetTabId, stage, message, extra = {}) {
  await sendCaptureResult(targetTabId, {
    type: STATUS_EVENT,
    stage,
    message,
    ...extra,
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== REQUEST_EVENT) {
    return;
  }

  (async () => {
    logCapture("capture request received", {
      senderTabUrl: sender.tab?.url || null,
      senderTabId: sender.tab?.id ?? null,
    });
    const tabs = await chrome.tabs.query({
      url: ["https://www.midtowncomics.com/*", "https://midtowncomics.com/*"],
    });
    if (!tabs.length) {
      throw new Error("Open a Midtown order detail page before capturing.");
    }

    const selectedTab = [...tabs].sort((left, right) => (right.lastAccessed ?? 0) - (left.lastAccessed ?? 0))[0];
    if (!selectedTab || typeof selectedTab.id !== "number") {
      throw new Error("Midtown order tab was not found.");
    }

    logCapture("midtown tab selected", {
      selectedTabId: selectedTab.id,
      selectedTabUrl: selectedTab.url || null,
      contentScriptInjected: true,
    });

    await sendStatus(
      sender.tab?.id ?? null,
      "midtown_page_detected",
      `Midtown Page Detected: ${selectedTab.url || "unknown"}`,
      {
        accountId: message.payload.accountId,
        syncRunId: message.payload.syncRunId,
      },
    );

    let payload = null;
    try {
      const contentScriptResponse = await chrome.tabs.sendMessage(selectedTab.id, {
        type: REQUEST_EVENT,
        payload: {
          accountId: message.payload.accountId,
          syncRunId: message.payload.syncRunId,
          captureToken: message.payload.captureToken,
          appOrigin: message.payload.appOrigin,
        },
      });
      logCapture("message sent to Midtown tab", {
        selectedTabId: selectedTab.id,
        messageReceived: Boolean(contentScriptResponse),
      });
      if (contentScriptResponse && contentScriptResponse.ok && contentScriptResponse.payload) {
        payload = contentScriptResponse.payload;
      }
    } catch (contentScriptError) {
      logCapture("Midtown content script unavailable, falling back to executeScript", {
        error: contentScriptError instanceof Error ? contentScriptError.message : String(contentScriptError),
      });
    }

    if (!payload) {
      const results = await chrome.scripting.executeScript({
        target: { tabId: selectedTab.id },
        func: captureMidtownDetailPage,
      });
      payload = results[0]?.result;
    }
    if (!payload) {
      const fallbackPayload = await captureMidtownDetailPageFromTab(selectedTab);
      if (!fallbackPayload) {
        throw new Error("Midtown detail capture returned no data.");
      }
      payload = fallbackPayload;
    }

    logCapture("diagnostics returned", {
      current_url: payload.capture_diagnostics?.current_url || "unknown",
      html_length: payload.capture_diagnostics?.html_length || 0,
      items_detected_client_side: payload.capture_diagnostics?.items_detected_client_side || 0,
    });

    await sendStatus(
      sender.tab?.id ?? null,
      "dom_read_success",
      `DOM Read Success: ${payload.capture_diagnostics?.html_length || 0} chars`,
      {
        accountId: message.payload.accountId,
        syncRunId: message.payload.syncRunId,
        captureToken: message.payload.captureToken,
      },
    );

    await sendCaptureResult(sender.tab?.id ?? null, {
      type: RESULT_EVENT,
      accountId: message.payload.accountId,
      syncRunId: message.payload.syncRunId,
      captureToken: message.payload.captureToken,
      historyHtml: payload.html,
      detailPages: [payload],
    });

    logCapture("capture result returned to ComicOS tab", {
      targetTabId: sender.tab?.id ?? null,
      historyHtmlLength: payload.html ? payload.html.length : 0,
    });
    sendResponse({ ok: true });
  })().catch(async (error) => {
    await sendCaptureResult(sender.tab?.id ?? null, {
      type: ERROR_EVENT,
      message: describeError(error),
      accountId: message?.payload?.accountId,
      syncRunId: message?.payload?.syncRunId,
    });
    sendResponse({ ok: false, error: describeError(error) });
  });

  return true;
});
