const REQUEST_EVENT = "comicos_midtown_capture_request";
const RESULT_EVENT = "comicos_midtown_capture_result";
const ERROR_EVENT = "comicos_midtown_capture_error";

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
  const pageText = (document.body && document.body.innerText ? document.body.innerText : "").toLowerCase();
  const orderNumberMatch = pageText.match(/order\s*#\s*([a-z0-9-]+)/i) || pageHtml.match(/order\s*#\s*([a-z0-9-]+)/i);
  const orderNumber = orderNumberMatch && orderNumberMatch[1] ? orderNumberMatch[1].trim() : null;
  const looksLikeDetailPage =
    pageText.includes("order #") &&
    (pageText.includes("tracking info") ||
      pageText.includes("item status") ||
      pageText.includes("order item details") ||
      pageText.includes("status:"));

  if (!looksLikeDetailPage) {
    throw new Error("Open the Midtown order detail page before capturing.");
  }

  return {
    detail_url: location.href,
    retailer_order_number: orderNumber,
    fallback_order_number: orderNumber,
    html: pageHtml,
  };
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
      throw new Error("Midtown detail capture returned no data.");
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
