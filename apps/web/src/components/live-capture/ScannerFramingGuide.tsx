import type { FramingGuideStatus, GuideOverlayStyle } from "../../pages/liveCaptureFraming";
import { framingGuideBorderClass } from "../../pages/liveCaptureFraming";

interface ScannerFramingGuideProps {
  overlayStyle: GuideOverlayStyle | null;
  status: FramingGuideStatus;
  hidden?: boolean;
}

function parsePercent(value: string): number {
  return Number.parseFloat(value.replace("%", "")) / 100;
}

export function ScannerFramingGuide({
  overlayStyle,
  status,
  hidden = false,
}: ScannerFramingGuideProps): JSX.Element | null {
  if (hidden || !overlayStyle) {
    return null;
  }

  const borderClass = framingGuideBorderClass(status);
  const left = parsePercent(overlayStyle.left);
  const top = parsePercent(overlayStyle.top);
  const width = parsePercent(overlayStyle.width);
  const height = parsePercent(overlayStyle.height);
  const right = left + width;
  const bottom = top + height;

  const shade = "absolute bg-slate-950/60";

  return (
    <div className="pointer-events-none absolute inset-0 rounded-3xl" data-testid="scanner-framing-guide">
      <div className={`${shade} inset-x-0 top-0`} style={{ height: `${top * 100}%` }} />
      <div className={`${shade} inset-x-0 bottom-0`} style={{ height: `${(1 - bottom) * 100}%` }} />
      <div className={`${shade} left-0`} style={{ top: `${top * 100}%`, width: `${left * 100}%`, height: `${height * 100}%` }} />
      <div
        className={`${shade} right-0`}
        style={{ top: `${top * 100}%`, width: `${(1 - right) * 100}%`, height: `${height * 100}%` }}
      />
      <div
        className={`absolute rounded-md border-2 ${borderClass}`}
        style={{
          left: overlayStyle.left,
          top: overlayStyle.top,
          width: overlayStyle.width,
          height: overlayStyle.height,
        }}
        data-testid="scanner-framing-guide-box"
        data-framing-status={status}
      />
    </div>
  );
}
