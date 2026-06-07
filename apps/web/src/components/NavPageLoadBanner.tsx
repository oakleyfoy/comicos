import { StatusBanner } from "./StatusBanner";

export type NavPageLoadStatus = "OK" | "SKIPPED" | "ERROR" | "EMPTY" | string | undefined;

type NavPageLoadBannerProps = {
  status?: NavPageLoadStatus;
  message?: string | null;
};

/** Controlled load state from nav-safe GET APIs (never raw SQL / 500 text). */
export function NavPageLoadBanner({ status, message }: NavPageLoadBannerProps): JSX.Element | null {
  if (!status || status === "OK") {
    return null;
  }
  const text =
    message?.trim() ||
    (status === "SKIPPED"
      ? "No cached data yet. Use refresh or run the related workflow when ready."
      : status === "EMPTY"
        ? "Nothing to show yet."
        : "This section is temporarily unavailable.");
  const tone = status === "SKIPPED" || status === "EMPTY" ? "warning" : "error";
  return <StatusBanner tone={tone}>{text}</StatusBanner>;
}
