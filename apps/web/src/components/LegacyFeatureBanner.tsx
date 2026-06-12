import { Link } from "react-router-dom";

import { StatusBanner } from "./StatusBanner";

type Props = {
  /** Short name of the deprecated feature, e.g. "Gmail receipt import". */
  feature: string;
  /** Optional extra sentence describing the recommended replacement. */
  detail?: string;
};

/**
 * Standard banner for acquisition sources that have been moved out of the
 * primary ComicOS workflow (Gmail / eBay / Whatnot / Facebook / PayPal /
 * generic email ingestion). Retailer imports provide high-confidence
 * structured data and are the recommended path.
 */
export function LegacyFeatureBanner({ feature, detail }: Props): JSX.Element {
  return (
    <div className="mt-6" data-testid="legacy-feature-banner">
      <StatusBanner tone="warning">
        <span className="font-semibold">{feature} is a legacy import method.</span>{" "}
        {detail ??
          "Marketplace and email sources create low-confidence inventory with weaker catalog matching."}{" "}
        For high-confidence imports, use{" "}
        <Link to="/connected-retailers/import" className="font-semibold underline">
          Retailer Import
        </Link>
        , scan your comics, or add them manually.
      </StatusBanner>
    </div>
  );
}
