export function normalizeMetadataCompareValue(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

export function metadataValuesMatch(a: string, b: string): boolean {
  const left = normalizeMetadataCompareValue(a);
  const right = normalizeMetadataCompareValue(b);
  if (!left && !right) {
    return true;
  }
  return left === right && left.length > 0;
}

function wordTokens(value: string): string[] {
  return value.trim().split(/\s+/).filter(Boolean);
}

export function metadataValuesSameWordsDifferentOrder(a: string, b: string): boolean {
  if (metadataValuesMatch(a, b)) {
    return false;
  }
  const left = wordTokens(a).map((w) => w.toLowerCase()).sort();
  const right = wordTokens(b).map((w) => w.toLowerCase()).sort();
  if (left.length !== right.length) {
    return false;
  }
  return left.every((word, index) => word === right[index]);
}

export type MetadataDiffSegment = {
  text: string;
  changed: boolean;
};

export function buildMetadataWordDiff(
  before: string,
  after: string,
): { before: MetadataDiffSegment[]; after: MetadataDiffSegment[] } {
  const beforeWords = wordTokens(before);
  const afterWords = wordTokens(after);
  let start = 0;
  while (
    start < beforeWords.length &&
    start < afterWords.length &&
    beforeWords[start].toLowerCase() === afterWords[start].toLowerCase()
  ) {
    start += 1;
  }
  let endBefore = beforeWords.length - 1;
  let endAfter = afterWords.length - 1;
  while (
    endBefore >= start &&
    endAfter >= start &&
    beforeWords[endBefore].toLowerCase() === afterWords[endAfter].toLowerCase()
  ) {
    endBefore -= 1;
    endAfter -= 1;
  }

  const toSegments = (words: string[], changeStart: number, changeEnd: number): MetadataDiffSegment[] => {
    if (!words.length) {
      return [];
    }
    const segments: MetadataDiffSegment[] = [];
    const pushRange = (from: number, to: number, changed: boolean) => {
      if (from > to) {
        return;
      }
      segments.push({ text: words.slice(from, to + 1).join(" "), changed });
    };
    pushRange(0, changeStart - 1, false);
    pushRange(changeStart, changeEnd, true);
    pushRange(changeEnd + 1, words.length - 1, false);
    return segments.filter((segment) => segment.text.length > 0);
  };

  return {
    before: toSegments(beforeWords, start, endBefore),
    after: toSegments(afterWords, start, endAfter),
  };
}

export function formatMetadataDiffSnippet(before: string, after: string): string | null {
  const { before: beforeSegments, after: afterSegments } = buildMetadataWordDiff(before, after);
  const changedBefore = beforeSegments.filter((s) => s.changed).map((s) => s.text).join(" ");
  const changedAfter = afterSegments.filter((s) => s.changed).map((s) => s.text).join(" ");
  if (!changedBefore && !changedAfter) {
    return null;
  }
  if (!changedBefore || !changedAfter) {
    return changedAfter || changedBefore;
  }
  return `${changedBefore} → ${changedAfter}`;
}

export function metadataValuesCosmeticallyEquivalent(a: string, b: string): boolean {
  return metadataValuesMatch(a, b) || metadataValuesSameWordsDifferentOrder(a, b);
}
