import { describe, expect, it } from "vitest";

import {
  buildMetadataWordDiff,
  formatMetadataDiffSnippet,
  metadataValuesMatch,
} from "../metadataValueDiff";

describe("metadataValueDiff", () => {
  it("highlights only the changed word run", () => {
    const before =
      "Cover B / Variant / Stefano Caselli First Appearance A Wonder Man Cover";
    const after =
      "Cover B / Variant / Stefano Caselli First Appearance A Wonder Cover Man";
    const snippet = formatMetadataDiffSnippet(before, after);
    expect(snippet).toBe("Man Cover → Cover Man");

    const diff = buildMetadataWordDiff(before, after);
    expect(diff.before.filter((s) => s.changed).map((s) => s.text).join(" ")).toBe(
      "Man Cover",
    );
  });

  it("treats case and spacing as a match", () => {
    expect(metadataValuesMatch("  John Romita Jr. ", "john romita jr.")).toBe(true);
  });
});
