/** 8×8 average hash — tolerates minor webcam compression/exposure jitter between ticks. */
export const FINGERPRINT_GRID = 8;

/** Max differing bits (of 64) to treat consecutive frames as the same stable view. */
export const STABLE_FINGERPRINT_MAX_HAMMING = 6;

export function hammingDistanceHex(a: string, b: string): number {
  if (a.length !== b.length) {
    return Number.MAX_SAFE_INTEGER;
  }
  let distance = 0;
  for (let index = 0; index < a.length; index += 1) {
    const xor = Number.parseInt(a[index], 16) ^ Number.parseInt(b[index], 16);
    distance += popcount4(xor);
  }
  return distance;
}

function popcount4(n: number): number {
  let count = 0;
  let value = n & 0xf;
  while (value) {
    count += value & 1;
    value >>= 1;
  }
  return count;
}

export function fingerprintsSimilar(a: string, b: string, maxHamming = STABLE_FINGERPRINT_MAX_HAMMING): boolean {
  return hammingDistanceHex(a, b) <= maxHamming;
}

export function averageHashFromRgba(data: Uint8ClampedArray, width: number, height: number): string {
  const grays: number[] = [];
  for (let row = 0; row < height; row += 1) {
    for (let col = 0; col < width; col += 1) {
      const index = (row * width + col) * 4;
      grays.push((data[index] + data[index + 1] + data[index + 2]) / 3);
    }
  }
  const average = grays.reduce((sum, value) => sum + value, 0) / grays.length;
  let bits = "";
  for (const gray of grays) {
    bits += gray >= average ? "1" : "0";
  }
  let hex = "";
  for (let index = 0; index < bits.length; index += 4) {
    hex += Number.parseInt(bits.slice(index, index + 4), 2).toString(16);
  }
  return hex;
}

export function frameFingerprintFromVideo(video: HTMLVideoElement): string | null {
  if (!video.videoWidth || !video.videoHeight) {
    return null;
  }
  const size = FINGERPRINT_GRID;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) {
    return null;
  }
  ctx.drawImage(video, 0, 0, size, size);
  try {
    const { data } = ctx.getImageData(0, 0, size, size);
    return averageHashFromRgba(data, size, size);
  } catch {
    return null;
  }
}

export function logLiveCaptureDebug(event: string, detail?: Record<string, unknown>): void {
  if (!import.meta.env.DEV) {
    return;
  }
  console.debug(`[live-capture] ${event}`, detail ?? {});
}
