type ComicOsMarkProps = {
  className?: string;
  size?: number;
};

/** Brand mark — matches public/favicon.svg (navy, white star, red stripe). */
export function ComicOsMark({ className, size = 20 }: ComicOsMarkProps): JSX.Element {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      width={size}
      height={size}
      className={className}
      aria-hidden
    >
      <circle cx="16" cy="16" r="16" fill="#002868" />
      <path fill="#bf0a30" d="M0 14h32v4H0z" />
      <path fill="#ffffff" d="M0 10h32v4H0z" />
      <path
        fill="#ffffff"
        d="M16 7.5 18.1 13h5.4l-4.4 3.2 1.7 5.3L16 18.3l-4.8 3.2 1.7-5.3-4.4-3.2h5.4L16 7.5z"
      />
    </svg>
  );
}
