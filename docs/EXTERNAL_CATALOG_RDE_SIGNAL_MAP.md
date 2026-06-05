# External Catalog → Recommendation Decision Engine signal map

LoCG ingest is an **external intelligence feed** for the Recommendation Decision Engine (RDE), not a release calendar scraper. Every extracted field maps to a decision signal family.

## Architecture

```
LoCG (rate-limited ingest)
  → parse + normalize (solicitation, creators, variants, importance text)
  → external_catalog_* tables
  → decision_signals_json (RDE input bundle, built at ingest)
  → [future] merge with Lunar ReleaseIssue + inventory + spec
  → Recommendation Decision Engine (BUY / WATCH / PASS, qty, cover, why)
```

**Current phase:** persist signals and expose API preview. **Does not** change ranking weights or `compute_recommendation_decision()` yet.

## Field → decision signal

| LoCG / catalog field | Decision signal (RDE) | Used for |
|---------------------|-------------------------|----------|
| Creators (Writer, Artist, Cover, Colorist, Letterer, Editor) | `creator_significance` | Why it matters; spec/creator heat |
| Publisher | `audience_market_context` | Market fit, publisher bias |
| Imprint / universe | `audience_market_context` | Franchise/universe alignment |
| Description (solicitation) | `narrative_catalyst_detection` | FA, death, origin, event, media, homage, finale |
| Story summary | `narrative_catalyst_detection` | Same + tone/plot catalysts |
| Issue number / title | `issue_position_signals` | #1, milestone (25/50/100/…) |
| Variants (cover, ratio, artist, price, URLs) | `cover_recommendation_and_ratio_risk` | Which cover; ratio risk tier |
| Pull count | `demand_score` | Community demand prior |
| Want count | `demand_score` | Wishlist/collection demand prior |
| FOC date | `preorder_urgency` | FOC buckets (this week, missed, …) |
| Release date | `buying_window` | Immediate / near-term / forward window |
| Price | `risk_reward_and_roi` | Cover-price risk hints (RDE adds ROI rules) |
| Cover / thumb / hi-res URLs | `cover_review_and_selection` | UI review; cover plan input |

Implementation: `app/services/external_catalog/decision_signals.py` (`FIELD_TO_DECISION_SIGNAL`, `build_decision_signals_from_normalized`).

Stored column: `external_catalog_issue.decision_signals_json`.

## `decision_signals_json` shape (preview)

- `creator_significance_score`, `creator_credits`
- `audience_market_context` — publisher, imprint, universe
- `narrative_catalysts`, `narrative_matched_phrases`
- `issue_position` — first issue, milestone
- `variant_intel[]` — ratio risk, cover hints, image URLs
- `demand_score`, `demand_components`
- `foc_urgency`, `foc_days_remaining`
- `buying_window`, `release_days_until`
- `price_usd`, `risk_reward_hint`
- `cover_review_assets`
- `signal_field_map` — documents provenance

## API

- `GET /api/v1/external-catalog/issues/{id}` — includes `decision_signals_json` when present
- `GET /api/v1/external-catalog/issues/{id}/decision-signals` — signal bundle (stored or rebuilt from children)

## Related docs

- `docs/EXTERNAL_CATALOG_LOCG.md` — ingest ops, rate limits, crosswalk to Lunar
