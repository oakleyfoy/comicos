type FavoriteStarRatingProps = {
  value: number | null;
  onChange: (value: number | null) => void;
  disabled?: boolean;
  size?: "sm" | "md";
  /** Shown for screen readers only */
  label?: string;
};

function StarIcon({ filled, className }: { filled: boolean; className?: string }): JSX.Element {
  const path =
    "M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z";
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={className}>
      <path
        d={path}
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={filled ? 0 : 1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function FavoriteStarRating({
  value,
  onChange,
  disabled = false,
  size = "md",
  label = "Favorite rating",
}: FavoriteStarRatingProps): JSX.Element {
  const dim = size === "sm" ? "h-3.5 w-3.5" : "h-5 w-5";
  const gap = size === "sm" ? "gap-0.5" : "gap-1";

  return (
    <div
      role="group"
      aria-label={label}
      className={`inline-flex items-center ${gap}`}
      onMouseLeave={() => {
        /* keep selection on mouse leave */
      }}
    >
      {[1, 2, 3, 4, 5].map((star) => {
        const active = value != null && star <= value;
        return (
          <button
            key={star}
            type="button"
            disabled={disabled}
            title={value === star ? "Clear favorite" : `Favorite ${star} of 5`}
            aria-label={active ? `${star} of 5 stars selected` : `Set favorite to ${star} of 5`}
            aria-pressed={active}
            onClick={() => {
              if (disabled) return;
              onChange(value === star ? null : star);
            }}
            className={`rounded p-0.5 transition disabled:cursor-not-allowed disabled:opacity-40 ${
              active
                ? "text-patriot-red hover:text-red-700"
                : "text-blue-300 hover:text-patriot-blue"
            }`}
          >
            <StarIcon filled={active} className={dim} />
          </button>
        );
      })}
    </div>
  );
}
