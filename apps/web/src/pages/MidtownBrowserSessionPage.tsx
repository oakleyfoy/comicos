import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import { useNavigate } from "react-router-dom";

import {
  apiClient,
  type MidtownBrowserFrameResponse,
  type MidtownBrowserSessionResponse,
} from "../api/client";
import { ApiError } from "../api/apiError";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

type ConsumerSessionCopy = {
  status: string;
  helperText: string;
  primaryActionLabel: string;
  primaryActionKind: "continue" | "verification";
  secondaryActionLabel: string | null;
  secondaryActionKind: "retry" | null;
};

const FRAME_POLL_INTERVAL_MS = 3000;
const FRAME_REQUEST_TIMEOUT_MS = 12000;
const FRAME_BUSY_BACKOFF_MS = 9000;

function detectSecurityVerification(session: MidtownBrowserSessionResponse | null): boolean {
  const browserSession = session?.session ?? null;
  const message = `${browserSession?.message ?? ""} ${browserSession?.status ?? ""} ${browserSession?.current_url ?? ""}`.toLowerCase();
  return (
    browserSession?.status === "needs_attention" ||
    browserSession?.status === "security_verification_required" ||
    message.includes("needs_attention") ||
    message.includes("captcha") ||
    message.includes("verification") ||
    message.includes("challenge") ||
    message.includes("verify")
  );
}

function deriveConsumerSessionCopy(session: MidtownBrowserSessionResponse | null): ConsumerSessionCopy {
  const browserSession = session?.session ?? null;
  if (detectSecurityVerification(session)) {
    return {
      status: "Security Verification Required",
      helperText: "Midtown requires security verification before ComicOS can load your orders.",
      primaryActionLabel: "Continue to Midtown Verification",
      primaryActionKind: "verification",
      secondaryActionLabel: "I Completed Verification - Retry",
      secondaryActionKind: "retry",
    };
  }

  if (browserSession?.authenticated) {
    return {
      status: "Connected",
      helperText: "You are signed in. ComicOS can continue to your Midtown orders.",
      primaryActionLabel: "Continue to Midtown",
      primaryActionKind: "continue",
      secondaryActionLabel: null,
      secondaryActionKind: null,
    };
  }

  return {
    status: "Login Required",
    helperText: "Sign in to Midtown so ComicOS can load your orders.",
    primaryActionLabel: "Continue to Midtown",
    primaryActionKind: "continue",
    secondaryActionLabel: null,
    secondaryActionKind: null,
  };
}

function getInputTextFromKey(key: string): string | null {
  if (key.length !== 1) {
    return null;
  }
  if (key === "\n" || key === "\r") {
    return null;
  }
  return key;
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      reject(new Error("Timed out while loading the Midtown browser view."));
    }, timeoutMs);

    promise
      .then((value) => {
        window.clearTimeout(timeoutId);
        resolve(value);
      })
      .catch((error) => {
        window.clearTimeout(timeoutId);
        reject(error);
      });
  });
}

function isMidtownBrowserBusy(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status === 429;
  }
  return error instanceof Error && error.message.toLowerCase().includes("busy");
}

export function MidtownBrowserSessionPage() {
  const navigate = useNavigate();
  const [session, setSession] = useState<MidtownBrowserSessionResponse | null>(null);
  const [frame, setFrame] = useState<MidtownBrowserFrameResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [isPollingFrame, setIsPollingFrame] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [frameError, setFrameError] = useState<string | null>(null);
  const shouldNavigateOnReadyRef = useRef(false);
  const isMountedRef = useRef(true);
  const browserPanelRef = useRef<HTMLDivElement | null>(null);
  const frameRequestInFlightRef = useRef(false);
  const frameBackoffUntilRef = useRef(0);

  const consumerCopy = useMemo(() => deriveConsumerSessionCopy(session), [session]);
  const browserSession = session?.session ?? null;
  const frameSession = frame?.session ?? browserSession;
  const shouldPollFrame = useMemo(() => {
    if (!browserSession) {
      return false;
    }
    if (browserSession.live_session_active) {
      return true;
    }
    return ["login_required", "security_verification_required", "ready", "connected", "initializing"].includes(
      browserSession.status,
    );
  }, [browserSession]);

  const refreshSessionStatus = useCallback(async (): Promise<MidtownBrowserSessionResponse> => {
    const response = await apiClient.getMidtownBrowserSessionStatus();
    if (!isMountedRef.current) {
      return response;
    }
    setSession(response);
    return response;
  }, []);

  const refreshFrame = useCallback(async (): Promise<MidtownBrowserFrameResponse | null> => {
    if (frameRequestInFlightRef.current) {
      return null;
    }
    if (Date.now() < frameBackoffUntilRef.current) {
      return null;
    }
    frameRequestInFlightRef.current = true;
    try {
      const response = await withTimeout(apiClient.getMidtownBrowserLiveFrame(), FRAME_REQUEST_TIMEOUT_MS);
      if (!isMountedRef.current) {
        return response;
      }
      setFrame(response);
      setSession({ session: response.session });
      setFrameError(null);
      return response;
    } catch (loadError) {
      if (!isMountedRef.current) {
        return null;
      }
      if (isMidtownBrowserBusy(loadError)) {
        frameBackoffUntilRef.current = Date.now() + FRAME_BUSY_BACKOFF_MS;
        setFrameError("Midtown browser is busy. Retrying shortly.");
      } else if (loadError instanceof Error && loadError.message === "Timed out while loading the Midtown browser view.") {
        frameBackoffUntilRef.current = Date.now() + FRAME_BUSY_BACKOFF_MS;
        setFrameError("Midtown browser is taking longer than expected. Retrying shortly.");
      } else {
        setFrameError(loadError instanceof Error ? loadError.message : "Unable to load the Midtown browser view.");
      }
      return null;
    } finally {
      frameRequestInFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    let cancelled = false;
    void refreshSessionStatus()
      .then((response) => {
        if (!cancelled && response.session.live_session_active) {
          setIsPollingFrame(true);
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load Midtown.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
      isMountedRef.current = false;
    };
  }, [refreshSessionStatus]);

  useEffect(() => {
    if (!shouldPollFrame) {
      setIsPollingFrame(false);
      return;
    }
    let cancelled = false;
    setIsPollingFrame(true);

    const poll = async () => {
      if (frameRequestInFlightRef.current || Date.now() < frameBackoffUntilRef.current) {
        return;
      }
      const response = await refreshFrame();
      if (cancelled || !response) {
        return;
      }
      if (shouldNavigateOnReadyRef.current && response.session.status === "ready") {
        shouldNavigateOnReadyRef.current = false;
        navigate("/connected-retailers/midtown/orders");
      }
    };

    void poll();
    const intervalId = window.setInterval(() => {
      void poll();
    }, FRAME_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      setIsPollingFrame(false);
    };
  }, [navigate, refreshFrame, shouldPollFrame]);

  async function startLiveSession(shouldNavigateWhenReady: boolean): Promise<void> {
    setIsWorking(true);
    setError(null);
    shouldNavigateOnReadyRef.current = shouldNavigateWhenReady;
    try {
      const response = await apiClient.startMidtownBrowserSession();
      if (!isMountedRef.current) {
        return;
      }
      setSession(response);
      setFrame(null);
      if (
        response.session.live_session_active ||
        ["login_required", "security_verification_required", "ready", "connected", "initializing"].includes(
          response.session.status,
        )
      ) {
        await refreshFrame();
      }
      if (shouldNavigateWhenReady && response.session.status === "ready") {
        shouldNavigateOnReadyRef.current = false;
        navigate("/connected-retailers/midtown/orders");
      }
    } catch (startError) {
      if (isMountedRef.current) {
        setError(startError instanceof Error ? startError.message : "Unable to continue to Midtown.");
      }
    } finally {
      if (isMountedRef.current) {
        setIsWorking(false);
      }
    }
  }

  async function handlePrimaryAction(): Promise<void> {
    if (consumerCopy.primaryActionKind === "verification") {
      await startLiveSession(false);
      return;
    }
    await startLiveSession(false);
  }

  async function handleRetryVerification(): Promise<void> {
    setIsWorking(true);
    setError(null);
    shouldNavigateOnReadyRef.current = true;
    try {
      const response = await apiClient.retryMidtownBrowserSession();
      if (!isMountedRef.current) {
        return;
      }
      setSession(response);
      setFrame(null);
      if (
        response.session.live_session_active ||
        ["login_required", "security_verification_required", "ready", "connected", "initializing"].includes(
          response.session.status,
        )
      ) {
        await refreshFrame();
      }
      if (response.session.status === "ready") {
        shouldNavigateOnReadyRef.current = false;
        navigate("/connected-retailers/midtown/orders");
      }
    } catch (retryError) {
      if (isMountedRef.current) {
        setError(retryError instanceof Error ? retryError.message : "Unable to retry Midtown verification.");
      }
    } finally {
      if (isMountedRef.current) {
        setIsWorking(false);
      }
    }
  }

  async function handleViewOrders(): Promise<void> {
    navigate("/connected-retailers/midtown/orders");
  }

  async function handleBrowserClick(event: MouseEvent<HTMLImageElement>): Promise<void> {
    if (!frame || !frameSession?.live_session_active) {
      return;
    }
    const image = event.currentTarget;
    const rect = image.getBoundingClientRect();
    const x =
      rect.width > 0
        ? Math.max(0, Math.min(frame.image_width, ((event.clientX - rect.left) / rect.width) * frame.image_width))
        : frame.image_width / 2;
    const y =
      rect.height > 0
        ? Math.max(0, Math.min(frame.image_height, ((event.clientY - rect.top) / rect.height) * frame.image_height))
        : frame.image_height / 2;

    setIsWorking(true);
    setError(null);
    try {
      const response = await apiClient.clickMidtownBrowserSession({
        x,
        y,
        displayed_image_width: frame.image_width,
        displayed_image_height: frame.image_height,
        viewport_width: frame.viewport_width ?? frame.image_width,
        viewport_height: frame.viewport_height ?? frame.image_height,
      });
      if (!isMountedRef.current) {
        return;
      }
      setSession(response);
      await refreshFrame();
    } catch (clickError) {
      if (isMountedRef.current) {
        setError(clickError instanceof Error ? clickError.message : "Unable to click the Midtown browser.");
      }
    } finally {
      if (isMountedRef.current) {
        setIsWorking(false);
      }
    }
  }

  async function forwardText(text: string): Promise<void> {
    if (!text) {
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      const response = await apiClient.typeMidtownBrowserSession({ text });
      if (!isMountedRef.current) {
        return;
      }
      setSession(response);
      await refreshFrame();
    } catch (typeError) {
      if (isMountedRef.current) {
        setError(typeError instanceof Error ? typeError.message : "Unable to type into the Midtown browser.");
      }
    } finally {
      if (isMountedRef.current) {
        setIsWorking(false);
      }
    }
  }

  async function handleBrowserKeyDown(event: KeyboardEvent<HTMLDivElement>): Promise<void> {
    if (!frameSession?.live_session_active) {
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey) {
      if (event.key === "Tab" || event.key === "Enter" || event.key === "Backspace" || event.key.startsWith("Arrow")) {
        event.preventDefault();
        setIsWorking(true);
        setError(null);
        try {
          const response = await apiClient.keyMidtownBrowserSession({ key: event.key });
          if (!isMountedRef.current) {
            return;
          }
          setSession(response);
          await refreshFrame();
        } catch (keyError) {
          if (isMountedRef.current) {
            setError(keyError instanceof Error ? keyError.message : "Unable to send a key to the Midtown browser.");
          }
        } finally {
          if (isMountedRef.current) {
            setIsWorking(false);
          }
        }
      }
      return;
    }

    const text = getInputTextFromKey(event.key);
    if (text === null) {
      if (event.key === "Enter" || event.key === "Tab" || event.key === "Backspace" || event.key.startsWith("Arrow")) {
        event.preventDefault();
        setIsWorking(true);
        setError(null);
        try {
          const response = await apiClient.keyMidtownBrowserSession({ key: event.key });
          if (!isMountedRef.current) {
            return;
          }
          setSession(response);
          await refreshFrame();
        } catch (keyError) {
          if (isMountedRef.current) {
            setError(keyError instanceof Error ? keyError.message : "Unable to send a key to the Midtown browser.");
          }
        } finally {
          if (isMountedRef.current) {
            setIsWorking(false);
          }
        }
      }
      return;
    }

    event.preventDefault();
    await forwardText(text);
  }

  const displaySource = frame?.image_data_url ?? null;
  const browserStatusText = consumerCopy.status;
  const browserInstructions = detectSecurityVerification(session)
    ? "Complete Midtown security verification inside the live panel."
    : frameSession?.authenticated
      ? "Click the live browser image to interact with Midtown."
      : "Open Midtown, then click and type directly in the live panel.";
  const liveDiagnostics = frame ?? null;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Connected Retailers"
        title="Midtown Comics"
        description="Continue your Midtown session and choose an order to add to your inventory."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      {frameError ? (
        <div className="mt-6">
          <StatusBanner tone="warning">{frameError}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Midtown Comics</p>
            <h2 className="text-2xl font-semibold text-white">{consumerCopy.status}</h2>
            <p className="max-w-2xl text-sm text-slate-300">{consumerCopy.helperText}</p>
            {consumerCopy.primaryActionKind === "verification" ? (
              <p className="max-w-2xl rounded-2xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
                Midtown requires a security verification before ComicOS can access your orders.
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void handlePrimaryAction()}
              disabled={isLoading || isWorking}
              className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isWorking ? "Working..." : consumerCopy.primaryActionLabel}
            </button>
            <button
              type="button"
              onClick={() => void handleViewOrders()}
              disabled={isLoading || isWorking || !browserSession?.authenticated}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
            >
              View Orders
            </button>
            {consumerCopy.secondaryActionLabel ? (
              <button
                type="button"
                onClick={() => void handleRetryVerification()}
                disabled={isLoading || isWorking}
                className="rounded-2xl border border-amber-300/20 bg-amber-400/10 px-5 py-3 text-sm font-semibold text-amber-100 transition hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {consumerCopy.secondaryActionLabel}
              </button>
            ) : null}
          </div>
        </div>
      </section>

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-4 shadow-xl shadow-black/20">
        <div className="flex flex-wrap items-center justify-between gap-3 px-2 py-2">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Midtown Browser</p>
            <p className="text-sm text-slate-300">{browserInstructions}</p>
            <p className="text-xs text-slate-500">Status: {browserStatusText}</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-slate-400">
            {frameSession?.current_url ? <span className="rounded-full border border-white/10 px-3 py-1">{frameSession.current_url}</span> : null}
            {frameSession?.order_count != null ? (
              <span className="rounded-full border border-white/10 px-3 py-1">{frameSession.order_count} orders</span>
            ) : null}
            {isPollingFrame ? <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-cyan-100">Live</span> : null}
          </div>
        </div>

        <div className="mt-4 min-h-[720px] overflow-hidden rounded-2xl border border-white/10 bg-slate-950/90 p-3">
          {displaySource ? (
            <div className="space-y-3">
              <div
                ref={browserPanelRef}
                role="application"
                tabIndex={0}
                onPaste={(event) => {
                  event.preventDefault();
                  const text = event.clipboardData.getData("text");
                  if (text) {
                    void forwardText(text);
                  }
                }}
                onClick={() => browserPanelRef.current?.focus()}
                onKeyDown={(event) => void handleBrowserKeyDown(event)}
                className="outline-none focus:ring-2 focus:ring-cyan-400/60 focus:ring-offset-0"
              >
                <img
                  title="Midtown browser workspace"
                  src={displaySource}
                  alt="Midtown browser workspace"
                  onClick={(event) => void handleBrowserClick(event)}
                  className="w-full select-none rounded-xl border border-white/10 bg-slate-950"
                  draggable={false}
                />
              </div>
              <p className="px-1 text-xs text-slate-500">Click the image to interact. Type while the browser panel is focused.</p>
            </div>
          ) : (
            <div className="flex min-h-[680px] items-center justify-center p-8 text-center">
              <div className="max-w-lg space-y-3">
                <p className="text-lg font-semibold text-white">Midtown browser workspace</p>
                <p className="text-sm text-slate-300">
                  Click Continue to Midtown to open the login and order history view here.
                </p>
                <p className="text-xs text-slate-500">ComicOS keeps the live page inside the app and updates the image automatically.</p>
              </div>
            </div>
          )}
        </div>

        <details className="mt-4 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
          <summary className="cursor-pointer select-none text-slate-100">Temporary live-view diagnostics</summary>
          <div className="mt-3 grid gap-2 text-xs text-slate-400 md:grid-cols-2">
            <p>Screenshot endpoint status: {liveDiagnostics?.endpoint_status ?? "unknown"}</p>
            <p>Image bytes size: {liveDiagnostics?.image_bytes_size ?? "unknown"}</p>
            <p>Last screenshot timestamp: {liveDiagnostics?.captured_at ?? "unknown"}</p>
            <p>Current page title: {liveDiagnostics?.page_title ?? "unknown"}</p>
            <p>Current page URL: {liveDiagnostics?.page_url ?? frameSession?.current_url ?? "unknown"}</p>
            <p>Process ID: {liveDiagnostics?.process_id ?? frameSession?.process_id ?? "unknown"}</p>
            <p>Live session active: {frameSession?.live_session_active === true ? "true" : String(frameSession?.live_session_active ?? "null")}</p>
            <p>Viewport: {frameSession?.viewport_width ?? "unknown"} x {frameSession?.viewport_height ?? "unknown"}</p>
            <p>Registry has account: {frameSession?.registry_contains_account === true ? "true" : String(frameSession?.registry_contains_account ?? "null")}</p>
            <p>Registry session count: {frameSession?.registry_session_count ?? "unknown"}</p>
            <p>Browser exists: {liveDiagnostics?.browser_exists === true ? "true" : String(liveDiagnostics?.browser_exists ?? "null")}</p>
            <p>Context exists: {liveDiagnostics?.context_exists === true ? "true" : String(liveDiagnostics?.context_exists ?? "null")}</p>
            <p>Page exists: {liveDiagnostics?.page_exists === true ? "true" : String(liveDiagnostics?.page_exists ?? "null")}</p>
            <p>Active element tag: {liveDiagnostics?.active_element_tag ?? "unknown"}</p>
            <p>Active element name: {liveDiagnostics?.active_element_name ?? "unknown"}</p>
            <p>Active element type: {liveDiagnostics?.active_element_type ?? "unknown"}</p>
            <p>Active element placeholder: {liveDiagnostics?.active_element_placeholder ?? "unknown"}</p>
          </div>
        </details>
      </section>
    </AppShell>
  );
}
