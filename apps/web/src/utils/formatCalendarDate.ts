/** Parse API date-only strings as local calendar dates (avoid UTC midnight shift). */
export function formatCalendarDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (iso) {
    const year = Number(iso[1]);
    const month = Number(iso[2]) - 1;
    const day = Number(iso[3]);
    const d = new Date(year, month, day);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString("en-US", { month: "long", day: "numeric" });
    }
  }
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric" });
}

/** Full calendar date for compact import review display (e.g. June 17, 2026). */
export function formatCalendarDateWithYear(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (iso) {
    const year = Number(iso[1]);
    const month = Number(iso[2]) - 1;
    const day = Number(iso[3]);
    const d = new Date(year, month, day);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
    }
  }
  return trimmed || null;
}

/** US short date for form fields (e.g. 6/17/2026). */
export function formatCalendarDateUsShort(value: string | null | undefined): string {
  if (!value?.trim()) {
    return "";
  }
  const trimmed = value.trim();
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (iso) {
    const year = Number(iso[1]);
    const month = Number(iso[2]);
    const day = Number(iso[3]);
    return `${month}/${day}/${year}`;
  }
  const slash = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(trimmed);
  if (slash) {
    return `${Number(slash[1])}/${Number(slash[2])}/${slash[3]}`;
  }
  return trimmed;
}

/** Normalize typed dates to ISO yyyy-mm-dd when possible; otherwise preserve partial/year-only text. */
export function normalizeCalendarDateInput(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (iso) {
    return trimmed;
  }
  const slash = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(trimmed);
  if (slash) {
    const month = Number(slash[1]);
    const day = Number(slash[2]);
    const year = Number(slash[3]);
    if (
      Number.isInteger(month) &&
      Number.isInteger(day) &&
      Number.isInteger(year) &&
      month >= 1 &&
      month <= 12 &&
      day >= 1 &&
      day <= 31
    ) {
      return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    }
  }
  return trimmed;
}
