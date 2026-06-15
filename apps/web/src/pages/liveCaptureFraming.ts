/** Standard US comic book width ÷ height (portrait). */
export const COMIC_BOOK_WIDTH_TO_HEIGHT = 6.625 / 10.125;

export type FramingGuideStatus = "none" | "unstable" | "ready";

export interface GuideRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface GuideOverlayStyle {
  left: string;
  top: string;
  width: string;
  height: string;
}

export interface ComicPresenceAnalysis {
  detected: boolean;
  luminanceStdDev: number;
}

export interface FramedCaptureFiles {
  recognition: File;
  diagnostic: File;
  guideRect: GuideRect;
}

const PRESENCE_SAMPLE_SIZE = 32;
/** Minimum luminance spread to treat the guide region as containing a comic (not empty desk). */
export const COMIC_PRESENCE_MIN_STD_DEV = 12;
export const COMIC_PRESENCE_MIN_MEAN = 8;

export function computeGuideRect(
  videoWidth: number,
  videoHeight: number,
  marginFraction = 0.08,
): GuideRect {
  const maxW = videoWidth * (1 - 2 * marginFraction);
  const maxH = videoHeight * (1 - 2 * marginFraction);
  let height = maxH;
  let width = height * COMIC_BOOK_WIDTH_TO_HEIGHT;
  if (width > maxW) {
    width = maxW;
    height = width / COMIC_BOOK_WIDTH_TO_HEIGHT;
  }
  return {
    x: Math.round((videoWidth - width) / 2),
    y: Math.round((videoHeight - height) / 2),
    width: Math.round(width),
    height: Math.round(height),
  };
}

/** Map intrinsic video coordinates to overlay percentages for object-cover display. */
export function mapGuideRectToOverlayStyle(
  videoWidth: number,
  videoHeight: number,
  containerWidth: number,
  containerHeight: number,
  rect: GuideRect,
  mirrored: boolean,
): GuideOverlayStyle {
  const scale = Math.max(containerWidth / videoWidth, containerHeight / videoHeight);
  const displayedW = videoWidth * scale;
  const displayedH = videoHeight * scale;
  const offsetX = (containerWidth - displayedW) / 2;
  const offsetY = (containerHeight - displayedH) / 2;
  let left = offsetX + rect.x * scale;
  const top = offsetY + rect.y * scale;
  const width = rect.width * scale;
  const height = rect.height * scale;
  if (mirrored) {
    left = containerWidth - left - width;
  }
  return {
    left: `${(left / containerWidth) * 100}%`,
    top: `${(top / containerHeight) * 100}%`,
    width: `${(width / containerWidth) * 100}%`,
    height: `${(height / containerHeight) * 100}%`,
  };
}

function luminanceStats(data: Uint8ClampedArray): { mean: number; stdDev: number } {
  const samples: number[] = [];
  for (let index = 0; index < data.length; index += 4) {
    samples.push((data[index] + data[index + 1] + data[index + 2]) / 3);
  }
  if (samples.length === 0) {
    return { mean: 0, stdDev: 0 };
  }
  const mean = samples.reduce((sum, value) => sum + value, 0) / samples.length;
  const variance =
    samples.reduce((sum, value) => sum + (value - mean) ** 2, 0) / samples.length;
  return { mean, stdDev: Math.sqrt(variance) };
}

export function analyzeComicPresenceFromRgba(data: Uint8ClampedArray): ComicPresenceAnalysis {
  const { mean, stdDev } = luminanceStats(data);
  const detected = stdDev >= COMIC_PRESENCE_MIN_STD_DEV && mean >= COMIC_PRESENCE_MIN_MEAN;
  return { detected, luminanceStdDev: stdDev };
}

export function analyzeComicPresenceInGuide(
  video: HTMLVideoElement,
  rect: GuideRect,
): ComicPresenceAnalysis | null {
  if (!video.videoWidth || !video.videoHeight || rect.width < 8 || rect.height < 8) {
    return null;
  }
  const canvas = document.createElement("canvas");
  canvas.width = PRESENCE_SAMPLE_SIZE;
  canvas.height = PRESENCE_SAMPLE_SIZE;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) {
    return null;
  }
  ctx.drawImage(
    video,
    rect.x,
    rect.y,
    rect.width,
    rect.height,
    0,
    0,
    PRESENCE_SAMPLE_SIZE,
    PRESENCE_SAMPLE_SIZE,
  );
  try {
    const { data } = ctx.getImageData(0, 0, PRESENCE_SAMPLE_SIZE, PRESENCE_SAMPLE_SIZE);
    return analyzeComicPresenceFromRgba(data);
  } catch {
    return null;
  }
}

export function resolveFramingGuideStatus(
  comicDetected: boolean,
  stableCount: number,
  stableThreshold: number,
): FramingGuideStatus {
  if (!comicDetected) {
    return "none";
  }
  if (stableCount >= stableThreshold) {
    return "ready";
  }
  return "unstable";
}

export function framingGuideBorderClass(status: FramingGuideStatus): string {
  switch (status) {
    case "ready":
      return "border-emerald-400 shadow-[0_0_0_1px_rgba(52,211,153,0.6)]";
    case "unstable":
      return "border-amber-400 shadow-[0_0_0_1px_rgba(251,191,36,0.6)]";
    default:
      return "border-red-500 shadow-[0_0_0_1px_rgba(239,68,68,0.6)]";
  }
}

async function canvasToJpegFile(canvas: HTMLCanvasElement, name: string): Promise<File | null> {
  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob((value) => resolve(value), "image/jpeg", 0.92);
  });
  if (!blob) {
    return null;
  }
  return new File([blob], name, { type: "image/jpeg" });
}

export async function captureFramedVideoFrames(
  video: HTMLVideoElement,
  captureSource: string,
  fingerprint: string,
  guideRect: GuideRect,
): Promise<FramedCaptureFiles | null> {
  if (!video.videoWidth || !video.videoHeight) {
    return null;
  }

  const fullCanvas = document.createElement("canvas");
  fullCanvas.width = video.videoWidth;
  fullCanvas.height = video.videoHeight;
  const fullCtx = fullCanvas.getContext("2d");
  if (!fullCtx) {
    return null;
  }
  fullCtx.drawImage(video, 0, 0, fullCanvas.width, fullCanvas.height);

  const cropCanvas = document.createElement("canvas");
  cropCanvas.width = guideRect.width;
  cropCanvas.height = guideRect.height;
  const cropCtx = cropCanvas.getContext("2d");
  if (!cropCtx) {
    return null;
  }
  cropCtx.drawImage(
    fullCanvas,
    guideRect.x,
    guideRect.y,
    guideRect.width,
    guideRect.height,
    0,
    0,
    guideRect.width,
    guideRect.height,
  );

  const baseName = captureSource.toLowerCase();
  const [recognition, diagnostic] = await Promise.all([
    canvasToJpegFile(cropCanvas, `${baseName}-guide-${fingerprint}.jpg`),
    canvasToJpegFile(fullCanvas, `${baseName}-full-${fingerprint}.jpg`),
  ]);
  if (!recognition || !diagnostic) {
    return null;
  }
  return { recognition, diagnostic, guideRect };
}
