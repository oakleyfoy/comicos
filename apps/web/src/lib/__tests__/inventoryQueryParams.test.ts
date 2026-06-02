import { describe, expect, it } from "vitest";

import {
  normalizeInventoryQueryParams,
  normalizeReleaseYearForQuery,
  parseReleaseYearFilterInput,
} from "../inventoryQueryParams";

describe("normalizeReleaseYearForQuery", () => {
  it("rejects zero and out-of-range years", () => {
    expect(normalizeReleaseYearForQuery(0)).toBeUndefined();
    expect(normalizeReleaseYearForQuery(1799)).toBeUndefined();
    expect(normalizeReleaseYearForQuery(3000)).toBeUndefined();
  });

  it("accepts valid calendar years", () => {
    expect(normalizeReleaseYearForQuery(2024)).toBe(2024);
  });
});

describe("parseReleaseYearFilterInput", () => {
  it("returns undefined for empty input (avoids Number('') === 0)", () => {
    expect(parseReleaseYearFilterInput("")).toBeUndefined();
    expect(parseReleaseYearFilterInput("   ")).toBeUndefined();
  });
});

describe("normalizeInventoryQueryParams", () => {
  it("removes release_year when zero", () => {
    const normalized = normalizeInventoryQueryParams({
      page: 1,
      page_size: 25,
      release_year: 0,
      sort_by: "purchase_date",
      sort_dir: "asc",
    });
    expect(normalized.release_year).toBeUndefined();
    expect("release_year" in normalized).toBe(false);
  });
});

describe("client inventory list params", () => {
  it("omits release_year=0 before query string encoding", () => {
    const normalized = normalizeInventoryQueryParams({
      page: 1,
      page_size: 25,
      release_year: 0,
      sort_by: "purchase_date",
      sort_dir: "asc",
    });
    expect(normalized).not.toHaveProperty("release_year");
    expect(normalized.page).toBe(1);
  });
});
