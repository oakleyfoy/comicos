import { describe, expect, it } from "vitest";

import { recognitionSourceLabel, recognitionSourceSentence } from "../recognitionTrustCopy";

describe("recognitionTrustCopy", () => {
  it("uses strong copy for exact fingerprint matches", () => {
    expect(recognitionSourceSentence("catalog_image_fingerprint", "exact")).toBe("Matched by cover image.");
  });

  it("uses review copy for possible fingerprint matches", () => {
    expect(recognitionSourceLabel("catalog_image_fingerprint", "possible")).toBe(
      "Possible visual match — please review",
    );
  });

  it("prefers server guidance when provided", () => {
    expect(recognitionSourceLabel("catalog_image_fingerprint", "possible", "Custom guidance")).toBe("Custom guidance");
  });
});
