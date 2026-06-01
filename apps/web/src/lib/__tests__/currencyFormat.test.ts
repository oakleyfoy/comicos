import { describe, expect, it } from "vitest";

import {
  DEFAULT_CURRENCY_CODE,
  formatCurrencyAmount,
  formatUsdCurrency,
  normalizeCurrencyCode,
} from "../currencyFormat";

describe("normalizeCurrencyCode", () => {
  it("returns USD for undefined, empty, and UNKNOWN", () => {
    expect(normalizeCurrencyCode(undefined)).toBe("USD");
    expect(normalizeCurrencyCode(null)).toBe("USD");
    expect(normalizeCurrencyCode("")).toBe("USD");
    expect(normalizeCurrencyCode("UNKNOWN")).toBe("USD");
    expect(normalizeCurrencyCode("unknown")).toBe("USD");
  });

  it("preserves valid ISO codes", () => {
    expect(normalizeCurrencyCode("USD")).toBe("USD");
    expect(normalizeCurrencyCode("eur")).toBe("EUR");
  });

  it("falls back for invalid codes", () => {
    expect(normalizeCurrencyCode("US")).toBe("USD");
    expect(normalizeCurrencyCode("USDD")).toBe("USD");
    expect(normalizeCurrencyCode("XXX")).toBe("USD");
  });
});

describe("formatCurrencyAmount", () => {
  it("formats USD amounts", () => {
    expect(formatCurrencyAmount("105.13", "USD")).toBe("$105.13");
  });

  it("falls back to USD when currency is undefined", () => {
    expect(formatCurrencyAmount("10", undefined)).toBe("$10.00");
  });

  it("falls back to USD for UNKNOWN without throwing", () => {
    expect(() => formatCurrencyAmount("10", "UNKNOWN")).not.toThrow();
    expect(formatCurrencyAmount("10", "UNKNOWN")).toBe("$10.00");
  });

  it("does not throw for invalid currency codes", () => {
    expect(() => formatCurrencyAmount("5", "NOT_A_CODE")).not.toThrow();
    expect(formatCurrencyAmount("5", "NOT_A_CODE")).toBe("$5.00");
  });
});

describe("formatUsdCurrency", () => {
  it("uses default currency", () => {
    expect(formatUsdCurrency("0")).toBe("$0.00");
    expect(DEFAULT_CURRENCY_CODE).toBe("USD");
  });
});
