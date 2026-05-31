from __future__ import annotations

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("top100_120d_scores.json").read_text(encoding="utf-8"))
items = data["items"]
rows_js = json.dumps(items, separators=(",", ":"))
path = Path(r"C:\Users\shell\.cursor\projects\c-comic-os-p41-feed\canvases\top-100-120d-opportunity-scores.canvas.tsx")
path.parent.mkdir(parents=True, exist_ok=True)
tsx = f"""import {{ H1, H2, Stack, Text, Table, useHostTheme }} from "cursor/canvas";

type Row = {{
  rank: number;
  publisher: string;
  series: string;
  issue: string;
  title: string;
  release_date: string;
  publisher_score: number;
  character_score: number;
  variant_score: number;
  milestone_score: number;
  first_appearance_score: number;
  creator_score: number;
  user_preference_score: number;
  total_score: number;
}};

const ITEMS: Row[] = {rows_js};

export default function Top100OpportunityScoresCanvas(): JSX.Element {{
  const theme = useHostTheme();
  const headers = ["#", "Release", "Book", "Pub", "Char", "Var", "Mile", "1st App", "Creator", "User Pref", "Total"];
  const rows = ITEMS.map((r) => [
    String(r.rank),
    r.release_date,
    `${{r.publisher}} | ${{r.series}} #${{r.issue}}`,
    r.publisher_score.toFixed(1),
    r.character_score.toFixed(1),
    r.variant_score.toFixed(1),
    r.milestone_score.toFixed(1),
    r.first_appearance_score.toFixed(1),
    r.creator_score.toFixed(1),
    r.user_preference_score.toFixed(1),
    r.total_score.toFixed(1),
  ]);
  return (
    <Stack gap={{16}} style={{{{ padding: 24, color: theme.fg.primary, background: theme.bg.primary }}}}>
      <H1>Top 100 releases — next 120 days</H1>
      <Text tone="secondary" size="small">
        Source: ComicOS opportunity ranking (Lunar owner {data["owner_user_id"]}). As of {data["as_of"]}. Window: release
        dates from today through +120 days. Character = NEW_CHARACTER signal score. Total includes additional components
        (New #1, horizon planning, continuity, anniversary, major development) beyond the columns shown.
      </Text>
      <H2>Ranked list</H2>
      <Table
        headers={{headers}}
        rows={{rows}}
        striped
        stickyHeader
        columnAlign={{[undefined, undefined, undefined, "right", "right", "right", "right", "right", "right", "right", "right"]}}
      />
    </Stack>
  );
}}
"""
path.write_text(tsx, encoding="utf-8")
print(path)
