import { Link } from "react-router-dom";

import type { GuidedImportExceptionItemRead } from "../../../api/client";
import { resolveImportLineCoverUrl } from "../../../utils/importCoverPresentation";

type Props = {
  item: GuidedImportExceptionItemRead;
  importId: number;
  onUpdated: () => void;
};

export function GuidedImportExceptionCard({ item, importId, onUpdated }: Props): JSX.Element {
  const coverSrc = resolveImportLineCoverUrl({
    coverUrl: item.cover_url,
    coverImageUrl: item.cover_image_url,
    retailerCoverUrl: item.retailer_cover_url,
  });
  return (
    <li className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
      <div className="flex gap-4">
        {coverSrc ? (
          <img src={coverSrc} alt="" className="h-24 w-16 rounded object-cover bg-slate-800" />
        ) : (
          <div className="flex h-24 w-16 items-center justify-center rounded bg-slate-800 text-[10px] text-slate-500">
            NO COVER
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-white">
            {item.title}
            {item.issue_number ? ` #${item.issue_number}` : ""}
          </p>
          <p className="text-xs text-slate-400">
            {item.publisher}
            {item.variant_label ? ` · ${item.variant_label}` : ""}
            {item.release_date ? ` · ${item.release_date}` : ""}
          </p>
          <ul className="mt-2 space-y-1 text-sm text-amber-100/90">
            {item.problems.map((p) => (
              <li key={p}>• {p}</li>
            ))}
          </ul>
          {item.cover_source ? (
            <p className="mt-1 text-[11px] text-slate-500">
              Cover source: {item.cover_source}
              {item.cover_confidence != null
                ? ` · ${Math.round(item.cover_confidence * 100)}% cover`
                : ""}
              {item.variant_confidence != null
                ? ` · ${Math.round(item.variant_confidence * 100)}% variant`
                : ""}
            </p>
          ) : null}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to={`/orders/import?importId=${importId}&item=${item.item_index}`}
          className="rounded-md border border-slate-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800"
          onClick={() => onUpdated()}
        >
          Search catalog
        </Link>
        <Link
          to={`/orders/import?importId=${importId}&item=${item.item_index}`}
          className="rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-slate-950"
        >
          Use suggested match
        </Link>
      </div>
    </li>
  );
}
