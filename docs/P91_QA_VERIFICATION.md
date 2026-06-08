# P91-02 / P91-03 QA notes

## Automated coverage

- Backend: `tests/test_p91_collector_onboarding.py`, `tests/test_p91_collector_home_setup.py`, `tests/test_p77_collector_profile.py`
- Frontend: `FirstTimeSetupChecklist.test.tsx`, `CollectorOnboardingGate.test.tsx`; `CollectorHomePage.test.tsx` mocks setup status

## Manual verification (recommended)

| Scenario | How to verify |
|----------|----------------|
| New user onboarding gate | Register → should land on `/collector-onboarding`; direct `/collector-home` redirects back until complete |
| Existing user | Pre-migration profiles have `onboarding_completed_at` set; no forced wizard |
| Draft resume | Step through wizard, refresh mid-flow; step + selections reload from `GET /collector-profile/onboarding` |
| Interest search | Steps 4–6: only pick from list (no free text) |
| Settings regression | `/collector-profile`: wizard save vs buying defaults save independently |
| Mobile layout | 390 / 768 / 1024 px: wizard cards stack; checklist CTAs remain tappable |
| Home checklist | After onboarding, `/collector-home` shows checklist until 6/6 or dismiss (4/6+ only) |

## Known limitations

- **Recommendations** setup task uses existence of `recommendation_score_v2` or advisor snapshot rows, not “has opened recommendations page”.
- **Review imports** task is complete when no `draft` status import rows exist (vacuously true before first import).
- Invalid enum values on draft PUT return **422** (Pydantic); client wizard only sends valid enums.
