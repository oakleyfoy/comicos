import type { AcquisitionType } from "../api/client";

export type AcquisitionSourceOption = {
  type: AcquisitionType;
  label: string;
  description: string;
};

/** P98-03 tap-first acquisition source buttons. */
export const ACQUISITION_SOURCE_OPTIONS: AcquisitionSourceOption[] = [
  { type: "FACEBOOK", label: "Facebook Marketplace", description: "Group, Marketplace, or DM deal" },
  { type: "EBAY", label: "eBay", description: "Auction or Buy It Now" },
  { type: "WHATNOT", label: "Whatnot", description: "Live show win or buy" },
  { type: "LCS", label: "Local Comic Shop", description: "Brick-and-mortar shop" },
  { type: "CONVENTION", label: "Convention", description: "Show floor or dealer" },
  { type: "FRIEND", label: "Friend", description: "Bought from a friend" },
  { type: "GIFT", label: "Gift", description: "Received as a gift" },
  { type: "INHERITED", label: "Inherited Collection", description: "Passed down to you" },
  { type: "UNKNOWN", label: "Unknown Source", description: "Not sure where these came from" },
  { type: "OTHER", label: "Other", description: "Anything else" },
];

export function acquisitionSourceLabel(type: string | null | undefined): string {
  if (!type) return "Unknown Source";
  const match = ACQUISITION_SOURCE_OPTIONS.find((option) => option.type === type);
  return match ? match.label : type;
}
