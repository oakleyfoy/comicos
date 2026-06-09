export type ImportCoverSourceKind = "RETAILER" | "LOCG" | "EXTERNAL_CATALOG" | "USER_UPLOAD";

const COVER_CONFIDENCE_EXCEPTION = 0.55;
const VARIANT_CONFIDENCE_EXCEPTION = 0.55;

export function resolveImportLineCoverUrl(input: {
  coverUrl?: string | null;
  coverThumbnailUrl?: string | null;
  coverImageUrl?: string | null;
  retailerCoverUrl?: string | null;
}): string | null {
  for (const value of [
    input.coverUrl,
    input.coverThumbnailUrl,
    input.coverImageUrl,
    input.retailerCoverUrl,
  ]) {
    const trimmed = value?.trim();
    if (trimmed) {
      return trimmed;
    }
  }
  return null;
}

export function formatImportCoverSourceLabel(
  coverSource: ImportCoverSourceKind | string | null | undefined,
  retailerName: string | null | undefined,
): string | null {
  const kind = coverSource?.trim().toUpperCase();
  if (kind === "RETAILER") {
    const retailer = retailerName?.trim();
    return retailer ? `Cover source: ${retailer}` : "Cover source: Retailer";
  }
  if (kind === "LOCG") {
    return "Cover source: LoCG";
  }
  if (kind === "EXTERNAL_CATALOG") {
    return "Cover source: Catalog";
  }
  if (kind === "USER_UPLOAD") {
    return "Cover source: Your upload";
  }
  return null;
}

export function importCoverNeedsAttention(input: {
  hasCoverImage?: boolean;
  coverConfidence?: number | null;
  variantConfidence?: number | null;
  coverVerifiedBy?: string | null;
}): boolean {
  if (input.hasCoverImage === false) {
    return true;
  }
  if (input.coverConfidence != null && input.coverConfidence < COVER_CONFIDENCE_EXCEPTION) {
    return true;
  }
  if (input.variantConfidence != null && input.variantConfidence < VARIANT_CONFIDENCE_EXCEPTION) {
    return true;
  }
  return false;
}

export function importCoverExceptionBadge(input: {
  coverConfidence?: number | null;
  variantConfidence?: number | null;
  hasCoverImage?: boolean;
}): string | null {
  if (input.hasCoverImage === false) {
    return "No cover";
  }
  if (input.variantConfidence != null && input.variantConfidence < VARIANT_CONFIDENCE_EXCEPTION) {
    return "Variant mismatch risk";
  }
  if (input.coverConfidence != null && input.coverConfidence < COVER_CONFIDENCE_EXCEPTION) {
    return "Low cover confidence";
  }
  return null;
}
