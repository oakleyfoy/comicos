import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P77CollectorProfileRead, type P91OnboardingDraft } from "../api/client";
import { CollectorProfileWizard } from "../components/collector/onboarding/CollectorProfileWizard";
import { CollectorProfileNav } from "../components/collector/p77/CollectorProfileNav";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import { patriotInputClass, patriotPrimaryButtonClass } from "../components/patriotTheme";

function profileToDraft(profile: P77CollectorProfileRead): P91OnboardingDraft {
  return {
    step: 1,
    collector_type: profile.collector_type,
    risk_profile: profile.risk_profile,
    time_horizon: profile.time_horizon,
    publisher_labels: profile.publishers.map((p) => p.label),
    character_labels: profile.characters.map((p) => p.label),
    creator_labels: profile.creators.map((p) => p.label),
  };
}

export function CollectorProfilePage(): JSX.Element {
  const [profile, setProfile] = useState<P77CollectorProfileRead | null>(null);
  const [draft, setDraft] = useState<P91OnboardingDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const row = await apiClient.getCollectorProfile();
      setProfile(row);
      setDraft(profileToDraft(row));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load profile.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveAdvanced(): Promise<void> {
    if (!profile) return;
    setSaving(true);
    setError(null);
    setSavedMessage(null);
    try {
      const updated = await apiClient.updateCollectorProfile({
        default_copy_count: profile.default_copy_count,
        key_issue_copy_count: profile.key_issue_copy_count,
        ratio_variant_copy_count: profile.ratio_variant_copy_count,
        grading_preference: profile.grading_preference,
        hold_preference: profile.hold_preference,
      });
      setProfile(updated);
      setSavedMessage("Advanced preferences saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PatriotPageLayout
      eyebrow="P91-01 · Settings"
      title="Collector profile"
      description="Update how ComicOS personalizes recommendations. Core preferences use the same guided steps as onboarding."
      subNav={<CollectorProfileNav />}
      error={error}
      onRetry={() => void load()}
      loading={!profile || !draft}
      maxWidthClass="max-w-3xl"
    >
      {profile && draft ? (
        <>
          {savedMessage ? (
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{savedMessage}</p>
          ) : null}
          <PatriotPanel>
            <CollectorProfileWizard
              key={profile.updated_at}
              mode="settings"
              initialDraft={draft}
              onFinished={() => {
                setSavedMessage("Collector profile updated.");
                void load();
              }}
            />
          </PatriotPanel>
          <PatriotPanel title="Buying defaults">
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">
                Default copies
                <input
                  type="number"
                  className={`mt-1 w-full ${patriotInputClass}`}
                  value={profile.default_copy_count}
                  onChange={(e) => setProfile({ ...profile, default_copy_count: Number(e.target.value) })}
                />
              </label>
              <label className="text-sm">
                Key issue copies
                <input
                  type="number"
                  className={`mt-1 w-full ${patriotInputClass}`}
                  value={profile.key_issue_copy_count}
                  onChange={(e) => setProfile({ ...profile, key_issue_copy_count: Number(e.target.value) })}
                />
              </label>
              <label className="text-sm">
                Ratio variants
                <input
                  type="number"
                  className={`mt-1 w-full ${patriotInputClass}`}
                  value={profile.ratio_variant_copy_count}
                  onChange={(e) => setProfile({ ...profile, ratio_variant_copy_count: Number(e.target.value) })}
                />
              </label>
              <label className="text-sm">
                Grading
                <select
                  className={`mt-1 w-full ${patriotInputClass}`}
                  value={profile.grading_preference}
                  onChange={(e) => setProfile({ ...profile, grading_preference: e.target.value })}
                >
                  {["NEVER_GRADE", "OPPORTUNISTIC", "AGGRESSIVE"].map((v) => (
                    <option key={v} value={v}>
                      {v.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </label>
              <label className="col-span-2 text-sm">
                Hold preference
                <select
                  className={`mt-1 w-full ${patriotInputClass}`}
                  value={profile.hold_preference}
                  onChange={(e) => setProfile({ ...profile, hold_preference: e.target.value })}
                >
                  {["FLIP", "MIXED", "LONG_TERM"].map((v) => (
                    <option key={v} value={v}>
                      {v.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button
              type="button"
              disabled={saving}
              onClick={() => void saveAdvanced()}
              className={`mt-4 w-full ${patriotPrimaryButtonClass} py-3`}
            >
              {saving ? "Saving…" : "Save buying defaults"}
            </button>
          </PatriotPanel>
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
