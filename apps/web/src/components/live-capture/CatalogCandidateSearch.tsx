import { useState } from "react";

import { ApiError, apiClient, type RecognitionCatalogCandidateRead } from "../../api/client";
import { CandidateIssueCard } from "./CandidateIssueCard";

interface CatalogCandidateSearchProps {
  selectedCatalogIssueId?: number | null;
  onSelect: (candidate: RecognitionCatalogCandidateRead) => void;
  initialQuery?: string;
}

export function CatalogCandidateSearch({
  selectedCatalogIssueId,
  onSelect,
  initialQuery = "",
}: CatalogCandidateSearchProps): JSX.Element {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<RecognitionCatalogCandidateRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  async function runSearch(): Promise<void> {
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const cards = await apiClient.listRecognitionCatalogCandidates({ q: trimmed, limit: 24 });
      setResults(cards);
      setSearched(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Catalog search failed. Try again.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void runSearch();
        }}
      >
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search series, issue, publisher"
          aria-label="Search catalog"
          data-testid="catalog-search-input"
          className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-slate-400"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          data-testid="catalog-search-submit"
          className="rounded-xl bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      {searched && !loading && results.length === 0 && !error ? (
        <p className="text-sm text-slate-400">No catalog matches. Try a different search.</p>
      ) : null}

      <div className="grid max-h-[40vh] grid-cols-2 gap-3 overflow-y-auto sm:grid-cols-3" data-testid="catalog-search-results">
        {results.map((candidate) => (
          <CandidateIssueCard
            key={candidate.catalog_issue_id}
            candidate={candidate}
            selected={candidate.catalog_issue_id === selectedCatalogIssueId}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}
