export function normalizeMoneyInput(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "0.00";
  }
  const raw = typeof value === "number" ? String(value) : value.trim();
  if (!raw) {
    return "0.00";
  }
  const parsed = Number(raw.replace(/[^0-9.-]/g, ""));
  if (!Number.isFinite(parsed)) {
    return "0.00";
  }
  return parsed.toFixed(2);
}
