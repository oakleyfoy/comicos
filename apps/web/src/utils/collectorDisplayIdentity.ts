/** Mirror of API collector display titles for legacy rows that only expose series + issue. */

export function formatCollectorIssueDisplay(
  seriesName: string,
  issueNumber: string,
  options?: { title?: string; releaseYear?: number | null },
): string {
  const title = (options?.title ?? "").trim();
  if (title && (/\bvol\.?\s*\d/i.test(title) || /\(20\d{2}\)/.test(title))) {
    return title;
  }
  const series = (seriesName || "Unknown").trim();
  const issue = (issueNumber || "").trim().replace(/^#/, "");
  const volMatch = series.match(/^(.*?)\s+(?:vol\.?|volume|v)\s*(\d+)\s*$/i);
  if (volMatch && issue) {
    return `${volMatch[1].trim()} Vol ${volMatch[2]} #${issue}`;
  }
  const year = options?.releaseYear ?? null;
  if (year && issue) {
    return `${series} (${year}) #${issue}`;
  }
  return issue ? `${series} #${issue}` : series;
}
