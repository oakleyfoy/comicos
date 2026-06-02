/** Matches API query validation: ge=1800, le=2999 on /inventory release_year. */
export const INVENTORY_RELEASE_YEAR_MIN = 1800;
export const INVENTORY_RELEASE_YEAR_MAX = 2999;

export function normalizeReleaseYearForQuery(value: number | undefined | null): number | undefined {
  if (value == null || !Number.isFinite(value)) {
    return undefined;
  }
  const year = Math.trunc(value);
  if (year < INVENTORY_RELEASE_YEAR_MIN || year > INVENTORY_RELEASE_YEAR_MAX) {
    return undefined;
  }
  return year;
}

export function parseReleaseYearFilterInput(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!trimmed) {
    return undefined;
  }
  const n = Number(trimmed);
  if (!Number.isInteger(n)) {
    return undefined;
  }
  return normalizeReleaseYearForQuery(n);
}

export type InventoryQueryParamsLike = Record<string, string | number | boolean | undefined>;

/** Drops invalid release_year (including 0 from empty filter input). */
export function normalizeInventoryQueryParams<P extends { release_year?: number }>(params: P): P {
  const releaseYear = normalizeReleaseYearForQuery(params.release_year);
  if (releaseYear === params.release_year) {
    return params;
  }
  const next = { ...params } as P & { release_year?: number };
  if (releaseYear === undefined) {
    delete next.release_year;
  } else {
    next.release_year = releaseYear;
  }
  return next as P;
}
