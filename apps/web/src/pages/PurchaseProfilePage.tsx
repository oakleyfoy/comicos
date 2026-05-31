import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type PurchasePreferenceRead,
  type PurchaseProfileRead,
  type PurchaseProfileType,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const PROFILE_OPTIONS: { value: PurchaseProfileType; label: string }[] = [
  { value: "INVESTOR", label: "Investor" },
  { value: "COLLECTOR", label: "Collector" },
  { value: "READER", label: "Reader" },
  { value: "VARIANT_HUNTER", label: "Variant Hunter" },
  { value: "LONG_TERM_HOLD", label: "Long-Term Hold" },
];

const SLIDER_FIELDS: { key: keyof PurchasePreferenceRead; label: string }[] = [
  { key: "risk_tolerance", label: "Risk Tolerance" },
  { key: "variant_interest", label: "Variant Interest" },
  { key: "grading_interest", label: "Grading Interest" },
  { key: "completionist_score", label: "Completionist" },
  { key: "speculation_score", label: "Speculation" },
];

export function PurchaseProfilePage(): JSX.Element {
  const [profile, setProfile] = useState<PurchaseProfileRead | null>(null);
  const [prefs, setPrefs] = useState<PurchasePreferenceRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, pr] = await Promise.all([apiClient.getPurchaseProfile(), apiClient.getPurchasePreferences()]);
      setProfile(p);
      setPrefs(pr);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load purchase profile.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onProfileChange(profileType: PurchaseProfileType) {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await apiClient.patchPurchaseProfile({ profile_type: profileType });
      setProfile(updated);
      const freshPrefs = await apiClient.getPurchasePreferences();
      setPrefs(freshPrefs);
      setMessage("Profile updated.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update profile.");
    } finally {
      setSaving(false);
    }
  }

  function onSliderChange(key: keyof PurchasePreferenceRead, value: number) {
    if (!prefs) return;
    setPrefs({ ...prefs, [key]: value });
  }

  async function savePreferences() {
    if (!prefs) return;
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await apiClient.patchPurchasePreferences({
        risk_tolerance: prefs.risk_tolerance,
        variant_interest: prefs.variant_interest,
        grading_interest: prefs.grading_interest,
        completionist_score: prefs.completionist_score,
        speculation_score: prefs.speculation_score,
      });
      setPrefs(updated);
      setMessage("Preferences saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save preferences.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P53-01"
        title="Purchase Profile"
        description="Collector goals and preference weighting for future purchase intelligence (profile only — no orders or recommendations yet)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading purchase profile…</p>
      ) : profile && prefs ? (
        <div className="mt-6 space-y-6">
          <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
            <h2 className="text-sm font-semibold text-white">Current Profile</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              {PROFILE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  disabled={saving}
                  onClick={() => void onProfileChange(opt.value)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                    profile.profile_type === opt.value
                      ? "border-cyan-400/40 bg-cyan-400/15 text-cyan-100"
                      : "border-white/10 bg-white/5 text-slate-300 hover:border-white/20"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="mt-4 text-lg font-medium text-white">{profile.display_name || profile.profile_type}</p>
            <p className="mt-2 text-sm text-slate-400">{profile.description || "—"}</p>
          </section>
          <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
            <h2 className="text-sm font-semibold text-white">Preferences</h2>
            <div className="mt-4 space-y-5">
              {SLIDER_FIELDS.map(({ key, label }) => (
                <label key={key} className="block">
                  <div className="mb-2 flex justify-between text-xs text-slate-400">
                    <span>{label}</span>
                    <span>{Number(prefs[key]).toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.01}
                    value={Number(prefs[key])}
                    onChange={(e) => onSliderChange(key, Number(e.target.value))}
                    className="w-full accent-cyan-400"
                  />
                </label>
              ))}
            </div>
            <button
              type="button"
              disabled={saving}
              onClick={() => void savePreferences()}
              className="mt-6 rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 disabled:opacity-50"
            >
              Save preferences
            </button>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
