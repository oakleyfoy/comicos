import { describe, expect, it } from "vitest";

import {
  formatImportCoverSourceLabel,
  importCoverExceptionBadge,
  importCoverNeedsAttention,
  resolveImportLineCoverUrl,
} from "../importCoverPresentation";

describe("importCoverPresentation", () => {
  it("formats retailer cover source with retailer name", () => {
    expect(formatImportCoverSourceLabel("RETAILER", "Midtown Comics")).toBe(
      "Cover source: Midtown Comics",
    );
    expect(formatImportCoverSourceLabel("LOCG", null)).toBe("Cover source: LoCG");
  });

  it("flags low variant confidence", () => {
    expect(
      importCoverExceptionBadge({
        hasCoverImage: true,
        coverConfidence: 0.9,
        variantConfidence: 0.3,
      }),
    ).toBe("Variant mismatch risk");
    expect(importCoverNeedsAttention({ hasCoverImage: true, variantConfidence: 0.3 })).toBe(true);
  });

  it("falls back through cover_url, thumbnail, image, and retailer", () => {
    expect(
      resolveImportLineCoverUrl({
        coverUrl: null,
        coverThumbnailUrl: null,
        coverImageUrl: null,
        retailerCoverUrl: "https://example.com/r.jpg",
      }),
    ).toBe("https://example.com/r.jpg");
  });
});
