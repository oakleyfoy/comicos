/** Client-side barcode consensus for hands-free intake (mirrors API rules). */

const MIN_VOTES = 3;
const MAX_SAMPLES = 15;

function digitsOnly(raw: string): string {
  return raw.replace(/\D/g, "");
}

/** UPC-A / EAN-13 check digit (12-digit body). */
export function upcCheckDigitValid(raw: string): boolean {
  const digits = digitsOnly(raw);
  let body = digits;
  if (body.length === 12) {
    body = "0" + body;
  }
  if (body.length !== 13 || !/^\d+$/.test(body)) {
    return false;
  }
  let total = 0;
  for (let i = 0; i < 12; i += 1) {
    total += parseInt(body[i], 10) * (i % 2 === 0 ? 1 : 3);
  }
  const check = (10 - (total % 10)) % 10;
  return check === parseInt(body[12], 10);
}

export type BarcodeVoteState = {
  tallies: Map<string, { raw: string; count: number }>;
};

export function createBarcodeVoteState(): BarcodeVoteState {
  return { tallies: new Map() };
}

/** Record one frame read; returns accepted normalized barcode when consensus reached. */
export function recordBarcodeVote(
  state: BarcodeVoteState,
  rawValue: string,
  minVotes = MIN_VOTES,
): { accepted: string; raw: string } | null {
  const digits = digitsOnly(rawValue);
  if (digits.length < 11) {
    return null;
  }
  if (!upcCheckDigitValid(digits.length >= 12 ? digits.slice(0, 12) : digits)) {
    return null;
  }
  const key = digits.length >= 17 ? digits.slice(0, 17) : digits;
  const prev = state.tallies.get(key);
  const raw = prev ? (digits.length > prev.raw.length ? digits : prev.raw) : digits;
  const count = (prev?.count ?? 0) + 1;
  if (state.tallies.size >= MAX_SAMPLES && !prev) {
    return null;
  }
  state.tallies.set(key, { raw, count });
  if (count >= minVotes) {
    state.tallies.clear();
    return { accepted: key, raw };
  }
  return null;
}

export function resetBarcodeVotes(state: BarcodeVoteState): void {
  state.tallies.clear();
}
