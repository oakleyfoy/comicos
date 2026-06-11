import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiClient, type MidtownBrowserSessionResponse } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

type ConsumerSessionCopy = {
  status: string;
  helperText: string;
  primaryActionLabel: string;
  primaryActionKind: "continue" | "verification";
};

function detectSecurityVerification(session: MidtownBrowserSessionResponse | null): boolean {
  const message = `${session?.session.message ?? ""} ${session?.session.status ?? ""} ${session?.session.current_url ?? ""}`.toLowerCase();
  return (
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
      helperText: "Midtown requires a security verification before ComicOS can access your orders.",
      primaryActionLabel: "Open Midtown Verification",
      primaryActionKind: "verification",
    };
  }

  if (browserSession?.authenticated) {
    return {
      status: "Connected",
      helperText: "You?re signed in. ComicOS can continue to your Midtown orders.",
      primaryActionLabel: "Continue to Midtown",
      primaryActionKind: "continue",
    };
  }

  return {
    status: "Login Required",
    helperText: "Sign in to Midtown so ComicOS can load your orders.",
    primaryActionLabel: "Continue to Midtown",
    primaryActionKind: "continue",
  };
}

export function MidtownBrowserSessionPage() {
  const navigate = useNavigate();
  const [session, setSession] = useState<MidtownBrowserSessionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshSession(): Promise<void> {
    const response = await apiClient.getMidtownBrowserSessionStatus();
    setSession(response);
  }

  useEffect(() => {
    let cancelled = false;
    void refreshSession()
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
    };
  }, []);

  const browserSession = session?.session ?? null;
  const consumerCopy = useMemo(() => deriveConsumerSessionCopy(session), [session]);

  async function handlePrimaryAction(): Promise<void> {
    setIsWorking(true);
    setError(null);
    try {
      if (consumerCopy.primaryActionKind === "verification") {
        const verificationUrl = browserSession?.current_url ?? browserSession?.orders_url;
        if (verificationUrl) {
          window.open(verificationUrl, "_blank", "noreferrer");
        }
        await refreshSession();
        return;
      }

      await apiClient.startMidtownBrowserSession();
      await refreshSession();
      navigate("/connected-retailers/midtown/orders");
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Unable to continue to Midtown.");
    } finally {
      setIsWorking(false);
    }
  }

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
              onClick={() => navigate("/connected-retailers/midtown/orders")}
              disabled={isLoading || isWorking}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
            >
              View Orders
            </button>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
