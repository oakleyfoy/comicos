export type VisualMatchStrength = "exact" | "possible" | "weak" | "none";

export function recognitionSourceLabel(
  source: string | null | undefined,
  visualMatchStrength?: VisualMatchStrength | string | null,
  recognitionGuidance?: string | null,
): string | null {
  if (recognitionGuidance?.trim()) {
    return recognitionGuidance.trim();
  }
  if (!source || source === "none") {
    return null;
  }
  switch (source) {
    case "catalog_image_fingerprint":
      if (visualMatchStrength === "exact") {
        return "Matched by cover image";
      }
      if (visualMatchStrength === "possible" || visualMatchStrength === "weak") {
        return "Possible visual match — please review";
      }
      return "Possible visual match — please review";
    case "catalog_nearby":
      return "Same series";
    case "catalog_search":
      return "Catalog search";
    case "user_correction":
      return "Your correction";
    case "ExternalCatalogIssue":
    case "CatalogIssue":
      return "Matched by catalog text";
    case "ocr":
      return "Matched by reading the cover text";
    default:
      return source.replace(/_/g, " ");
  }
}

export function recognitionSourceSentence(
  source: string | null | undefined,
  visualMatchStrength?: VisualMatchStrength | string | null,
  recognitionGuidance?: string | null,
): string | null {
  const label = recognitionSourceLabel(source, visualMatchStrength, recognitionGuidance);
  if (!label) {
    return null;
  }
  if (label.endsWith(".")) {
    return label;
  }
  return `${label}.`;
}
