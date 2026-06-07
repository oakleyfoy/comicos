import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P77CollectorProfileRead } from "../api/client";
import { CollectorProfileNav } from "../components/collector/p77/CollectorProfileNav";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import { patriotInputClass, patriotPrimaryButtonClass } from "../components/patriotTheme";

function parseTags(value: string): { interest_type: string; label: string; priority_rank: number }[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((label, index) => ({ interest_type: "", label, priority_rank: index + 1 }));
}

export function CollectorProfilePage(): JSX.Element {
  const [profile, setProfile] = useState<P77CollectorProfileRead | null>(null);
  const [publishers, setPublishers] = useState("");
  const [characters, setCharacters] = useState("");
  const [creators, setCreators] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const row = await apiClient.getCollectorProfile();
      setProfile(row);
      setPublishers(row.publishers.map((p) => p.label).join(", "));
      setCharacters(row.characters.map((p) => p.label).join(", "));
      setCreators(row.creators.map((p) => p.label).join(", "));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load profile.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function save(): Promise<void> {
    if (!profile) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiClient.updateCollectorProfile({
        collector_type: profile.collector_type,
        risk_profile: profile.risk_profile,
        time_horizon: profile.time_horizon,
        grading_preference: profile.grading_preference,
        hold_preference: profile.hold_preference,
        default_copy_count: profile.default_copy_count,
        key_issue_copy_count: profile.key_issue_copy_count,
        ratio_variant_copy_count: profile.ratio_variant_copy_count,
        publishers: parseTags(publishers).map((p) => ({ ...p, interest_type: "PUBLISHER" })),
        characters: parseTags(characters).map((p) => ({ ...p, interest_type: "CHARACTER" })),
        creators: parseTags(creators).map((p) => ({ ...p, interest_type: "CREATOR" })),
      });
      setProfile(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PatriotPageLayout
      eyebrow="P77-01 · Settings"
      title="Collector profile"
      subNav={<CollectorProfileNav />}
      error={error}
      onRetry={() => void load()}
      loading={!profile}
      maxWidthClass="max-w-2xl"
    >
      {profile ? (
        <>
        <PatriotPanel>
          <div className="space-y-3">
          <label className="block text-sm">
            Collector type
            <select
              className={`mt-1 w-full ${patriotInputClass}`}
              value={profile.collector_type}
              onChange={(e) => setProfile({ ...profile, collector_type: e.target.value })}
            >
              {["INVESTOR", "SPECULATOR", "COMPLETIONIST", "READER", "HYBRID"].map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            Risk profile
            <select
              className={`mt-1 w-full ${patriotInputClass}`}
              value={profile.risk_profile}
              onChange={(e) => setProfile({ ...profile, risk_profile: e.target.value })}
            >
              {["CONSERVATIVE", "MODERATE", "AGGRESSIVE"].map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            Time horizon
            <select
              className={`mt-1 w-full ${patriotInputClass}`}
              value={profile.time_horizon}
              onChange={(e) => setProfile({ ...profile, time_horizon: e.target.value })}
            >
              {["SHORT_TERM_FLIP", "MEDIUM_TERM", "LONG_TERM", "LEGACY_COLLECTION"].map((v) => (
                <option key={v} value={v}>
                  {v.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>
          </div>
        </PatriotPanel>
        <PatriotPanel title="Interests (comma-separated, priority left → right)">
          <input
            className={`w-full ${patriotInputClass}`}
            placeholder="Publishers: DC, Marvel, Image"
            value={publishers}
            onChange={(e) => setPublishers(e.target.value)}
          />
          <input
            className={`mt-2 w-full ${patriotInputClass}`}
            placeholder="Characters: Batman, Spider-Man"
            value={characters}
            onChange={(e) => setCharacters(e.target.value)}
          />
          <input
            className={`mt-2 w-full ${patriotInputClass}`}
            placeholder="Creators"
            value={creators}
            onChange={(e) => setCreators(e.target.value)}
          />
        </PatriotPanel>
        <PatriotPanel>
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
          <label className="text-sm col-span-2">
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
        </PatriotPanel>
        <button type="button" disabled={saving} onClick={() => void save()} className={`w-full ${patriotPrimaryButtonClass} py-3`}>
          {saving ? "Saving…" : "Save profile"}
        </button>
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
