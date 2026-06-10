const REQUEST_EVENT = "comicos_midtown_capture_request";
const RESULT_EVENT = "comicos_midtown_capture_result";
const ERROR_EVENT = "comicos_midtown_capture_error";

function normalizeWhitespace(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
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

function buildMidtownPayload(pageHtml, pageUrl, pageTitle, pageText) {
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

function captureMidtownDetailPage() {
  const pageHtml = document.documentElement.outerHTML;
  const pageText = document.body && document.body.innerText ? document.body.innerText : "";
  return buildMidtownPayload(pageHtml, location.href, document.title, pageText);
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
  return buildMidtownPayload(pageHtml, tab.url, tab.title || "", extractPlainTextFromHtml(pageHtml));
}

async function sendCaptureResult(targetTabId, message) {
  if (typeof targetTabId !== "number") {
    return;
  }
  await chrome.tabs.sendMessage(targetTabId, message);
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== REQUEST_EVENT) {
    return;
  }

  (async () => {
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

    const results = await chrome.scripting.executeScript({
      target: { tabId: selectedTab.id },
      func: captureMidtownDetailPage,
    });
    const payload = results[0]?.result;
    if (!payload) {
      const fallbackPayload = await captureMidtownDetailPageFromTab(selectedTab);
      if (!fallbackPayload) {
        throw new Error("Midtown detail capture returned no data.");
      }
      await sendCaptureResult(sender.tab?.id ?? null, {
        type: RESULT_EVENT,
        accountId: message.payload.accountId,
        syncRunId: message.payload.syncRunId,
        captureToken: message.payload.captureToken,
        historyHtml: fallbackPayload.html,
        detailPages: [fallbackPayload],
      });
      sendResponse({ ok: true, usedFallback: true });
      return;
    }

    await sendCaptureResult(sender.tab?.id ?? null, {
      type: RESULT_EVENT,
      accountId: message.payload.accountId,
      syncRunId: message.payload.syncRunId,
      captureToken: message.payload.captureToken,
      historyHtml: payload.html,
      detailPages: [payload],
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
