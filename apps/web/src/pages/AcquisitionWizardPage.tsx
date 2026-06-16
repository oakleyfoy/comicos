import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, apiClient, type AcquisitionType } from "../api/client";
import { AppShell } from "../components/AppShell";
import { ACQUISITION_SOURCE_OPTIONS } from "../config/acquisitionSources";

type WizardStep = "source" | "details";

export function AcquisitionWizardPage(): JSX.Element {
  const navigate = useNavigate();
  const [step, setStep] = useState<WizardStep>("source");
  const [sourceType, setSourceType] = useState<AcquisitionType | null>(null);
  const [purchaseDate, setPurchaseDate] = useState("");
  const [totalPaid, setTotalPaid] = useState("");
  const [shippingPaid, setShippingPaid] = useState("");
  const [taxPaid, setTaxPaid] = useState("");
  const [sellerName, setSellerName] = useState("");
  const [sellerUsername, setSellerUsername] = useState("");
  const [expectedBookCount, setExpectedBookCount] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chooseSource = (type: AcquisitionType) => {
    setSourceType(type);
    setStep("details");
  };

  const create = async () => {
    if (!sourceType) return;
    setBusy(true);
    setError(null);
    try {
      const acquisition = await apiClient.createAcquisition({
        acquisition_type: sourceType,
        purchase_date: purchaseDate || null,
        total_paid: totalPaid || "0",
        shipping_paid: shippingPaid || "0",
        tax_paid: taxPaid || "0",
        seller_name: sellerName || null,
        seller_username: sellerUsername || null,
        expected_book_count: expectedBookCount ? Number(expectedBookCount) : null,
        notes: notes || null,
      });
      navigate(`/acquisitions/${acquisition.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create acquisition.");
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto max-w-3xl px-4 py-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">P98 · New Acquisition</p>
          <h1 className="mt-2 text-2xl font-semibold text-white">
            {step === "source" ? "Where did you get these books?" : "Acquisition details"}
          </h1>

          {error ? (
            <p role="alert" className="mt-4 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">
              {error}
            </p>
          ) : null}

          {step === "source" ? (
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {ACQUISITION_SOURCE_OPTIONS.map((option) => (
                <button
                  key={option.type}
                  type="button"
                  onClick={() => chooseSource(option.type)}
                  className="rounded-xl border border-slate-700 bg-slate-900 p-4 text-left transition hover:border-sky-400 hover:shadow-lg"
                >
                  <span className="block text-base font-semibold text-white">{option.label}</span>
                  <span className="text-sm text-slate-400">{option.description}</span>
                </button>
              ))}
            </div>
          ) : null}

          {step === "details" ? (
            <form
              className="mt-6 space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                void create();
              }}
            >
              <button
                type="button"
                onClick={() => setStep("source")}
                className="text-sm text-sky-300 hover:underline"
              >
                ← Change source
              </button>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Purchase Date">
                  <input
                    type="date"
                    value={purchaseDate}
                    onChange={(e) => setPurchaseDate(e.target.value)}
                    className="input"
                  />
                </Field>
                <Field label="Total Paid">
                  <input
                    inputMode="decimal"
                    value={totalPaid}
                    onChange={(e) => setTotalPaid(e.target.value)}
                    placeholder="120.00"
                    className="input"
                  />
                </Field>
                <Field label="Shipping">
                  <input
                    inputMode="decimal"
                    value={shippingPaid}
                    onChange={(e) => setShippingPaid(e.target.value)}
                    placeholder="0.00"
                    className="input"
                  />
                </Field>
                <Field label="Tax">
                  <input
                    inputMode="decimal"
                    value={taxPaid}
                    onChange={(e) => setTaxPaid(e.target.value)}
                    placeholder="0.00"
                    className="input"
                  />
                </Field>
                <Field label="Seller Name">
                  <input value={sellerName} onChange={(e) => setSellerName(e.target.value)} className="input" />
                </Field>
                <Field label="Seller Username">
                  <input
                    value={sellerUsername}
                    onChange={(e) => setSellerUsername(e.target.value)}
                    className="input"
                  />
                </Field>
                <Field label="Expected Book Count">
                  <input
                    inputMode="numeric"
                    value={expectedBookCount}
                    onChange={(e) => setExpectedBookCount(e.target.value)}
                    placeholder="40"
                    className="input"
                  />
                </Field>
              </div>
              <Field label="Notes">
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  className="input"
                />
              </Field>
              <button
                type="submit"
                disabled={busy}
                className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {busy ? "Creating…" : "Create Acquisition"}
              </button>
            </form>
          ) : null}
        </div>
      </div>
      <style>{`.input{margin-top:0.25rem;display:block;width:100%;border-radius:0.5rem;border:1px solid rgb(51 65 85);background:rgb(15 23 42);padding:0.5rem 0.75rem;color:white;font-size:0.875rem}`}</style>
    </AppShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }): JSX.Element {
  return (
    <label className="block text-sm text-slate-300">
      {label}
      {children}
    </label>
  );
}
