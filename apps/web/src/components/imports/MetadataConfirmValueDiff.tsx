import {
  buildMetadataWordDiff,
  type MetadataDiffSegment,
} from "../../utils/metadataValueDiff";

function DiffText({ segments }: { segments: MetadataDiffSegment[] }): JSX.Element {
  return (
    <span>
      {segments.map((segment, index) => (
        <span
          key={`${segment.text}-${index}`}
          className={
            segment.changed
              ? "rounded bg-amber-400/25 px-1 text-amber-50 ring-1 ring-amber-300/40"
              : undefined
          }
        >
          {index > 0 ? " " : null}
          {segment.text}
        </span>
      ))}
    </span>
  );
}

type MetadataConfirmValueDiffProps = {
  fromOrder: string;
  comicOsValue: string;
};

export function MetadataConfirmValueDiff({
  fromOrder,
  comicOsValue,
}: MetadataConfirmValueDiffProps): JSX.Element {
  const diff = buildMetadataWordDiff(fromOrder, comicOsValue);

  return (
    <dl className="mt-3 space-y-3 text-sm">
      <div>
        <dt className="font-medium text-slate-400">From your order</dt>
        <dd className="mt-1 text-base font-semibold text-white">
          <DiffText segments={diff.before} />
        </dd>
      </div>
      <div>
        <dt className="font-medium text-slate-400">ComicOS will use</dt>
        <dd className="mt-1 text-base font-semibold text-emerald-100">
          <DiffText segments={diff.after} />
        </dd>
      </div>
    </dl>
  );
}
