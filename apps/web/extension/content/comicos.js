const READY_EVENT = "comicos_midtown_extension_ready";
const PING_EVENT = "comicos_midtown_extension_ping";
const REQUEST_EVENT = "comicos_midtown_capture_request";
const RESULT_EVENT = "comicos_midtown_capture_result";
const ERROR_EVENT = "comicos_midtown_capture_error";

function dispatchReady() {
  window.dispatchEvent(new CustomEvent(READY_EVENT, { detail: { installed: true } }));
}

function dispatchResult(message) {
  window.dispatchEvent(new CustomEvent(RESULT_EVENT, { detail: message }));
}

function dispatchError(message) {
  window.dispatchEvent(new CustomEvent(ERROR_EVENT, { detail: message }));
}

dispatchReady();

window.addEventListener(PING_EVENT, dispatchReady);

window.addEventListener(REQUEST_EVENT, (event) => {
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

chrome.runtime.onMessage.addListener((message) => {
  if (!message || typeof message !== "object") {
    return;
  }
  if (message.type === RESULT_EVENT) {
    dispatchResult(message);
    return;
  }
  if (message.type === ERROR_EVENT) {
    dispatchError(message);
  }
});
