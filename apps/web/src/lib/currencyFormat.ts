export const DEFAULT_CURRENCY_CODE = "USD";

/**
 * Normalizes API/UI currency codes for Intl.NumberFormat.
 * Invalid, missing, or sentinel values fall back to USD.
 */
export function normalizeCurrencyCode(currencyCode: string | null | undefined): string {
  const trimmed = (currencyCode ?? "").trim().toUpperCase();
  if (!trimmed || trimmed === "UNKNOWN" || trimmed === "XXX") {
    return DEFAULT_CURRENCY_CODE;
  }
  if (!/^[A-Z]{3}$/.test(trimmed)) {
    return DEFAULT_CURRENCY_CODE;
  }
  try {
    new Intl.NumberFormat("en-US", { style: "currency", currency: trimmed }).format(0);
    return trimmed;
  } catch {
    return DEFAULT_CURRENCY_CODE;
  }
}

export function formatCurrencyAmount(
  value: string | number | null | undefined,
  currencyCode?: string | null,
): string {
  const amount = Number(value ?? 0);
  const currency = normalizeCurrencyCode(currencyCode ?? DEFAULT_CURRENCY_CODE);
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
  } catch {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: DEFAULT_CURRENCY_CODE,
    }).format(amount);
  }
}

/** ComicOS cost-basis and legacy amounts without an explicit currency code. */
export function formatUsdCurrency(value: string | number | null | undefined): string {
  return formatCurrencyAmount(value, DEFAULT_CURRENCY_CODE);
}
