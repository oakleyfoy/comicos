import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { ApiError, apiClient } from "../api/client";

const BYPASS_PREFIXES = ["/collector-onboarding", "/login", "/register", "/storefront"];

export function CollectorOnboardingGate(): JSX.Element {
  const location = useLocation();
  const [pending, setPending] = useState<boolean | null>(null);

  useEffect(() => {
    const path = location.pathname;
    if (BYPASS_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`))) {
      setPending(false);
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const status = await apiClient.getCollectorOnboardingStatus();
        if (!cancelled) setPending(!status.onboarding_completed);
      } catch (err) {
        if (!cancelled) {
          // Do not block the app if onboarding status fails.
          setPending(false);
          if (import.meta.env.DEV) {
            console.warn("Onboarding status unavailable", err instanceof ApiError ? err.message : err);
          }
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  if (pending === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-200">
        Loading collector workspace…
      </div>
    );
  }

  if (pending && location.pathname !== "/collector-onboarding") {
    return <Navigate to="/collector-onboarding" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
