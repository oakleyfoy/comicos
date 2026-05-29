import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ApiError, apiClient, type OrganizationCreateRequest, type OrganizationResponse, type UserAuthSessionRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { AuthSessionListPanel } from "../components/auth/AuthSessionListPanel";
import { SecurityContextPanel } from "../components/auth/SecurityContextPanel";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationCreateForm } from "../components/organizations/OrganizationCreateForm";
import { OrganizationListPanel } from "../components/organizations/OrganizationListPanel";
import { listActiveSessions, revokeAllSessions, revokeSession } from "../lib/sessionManager";

export function OrganizationsPage(): JSX.Element {
  const navigate = useNavigate();
  const { securityContext, switchOrganization, refreshSecurityContext } = useAuth();
  const [organizations, setOrganizations] = useState<OrganizationResponse[]>([]);
  const [sessions, setSessions] = useState<UserAuthSessionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [switchingOrg, setSwitchingOrg] = useState(false);
  const [revokingKey, setRevokingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshOrganizations();
  }, []);

  async function refreshOrganizations(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [response, sessionRows] = await Promise.all([
        apiClient.listOrganizations({ limit: 50, offset: 0 }),
        listActiveSessions(),
      ]);
      setOrganizations(response.items);
      setSessions(sessionRows);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load organizations.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(payload: OrganizationCreateRequest): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      const created = await apiClient.createOrganization(payload);
      await refreshOrganizations();
      navigate(`/organizations/${created.id}`);
    } catch (createErr) {
      setError(createErr instanceof ApiError ? createErr.message : "Unable to create organization.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSwitchOrganization(organizationId: number): Promise<void> {
    setSwitchingOrg(true);
    setError(null);
    try {
      await switchOrganization(organizationId);
      await refreshSecurityContext();
      await refreshOrganizations();
    } catch (switchErr) {
      setError(switchErr instanceof ApiError ? switchErr.message : "Unable to switch active organization.");
    } finally {
      setSwitchingOrg(false);
    }
  }

  async function handleRevokeSession(sessionId: number): Promise<void> {
    setRevokingKey(String(sessionId));
    setError(null);
    try {
      await revokeSession(sessionId);
      await refreshOrganizations();
    } catch (revokeErr) {
      setError(revokeErr instanceof ApiError ? revokeErr.message : "Unable to revoke authentication session.");
    } finally {
      setRevokingKey(null);
    }
  }

  async function handleRevokeAllSessions(): Promise<void> {
    setRevokingKey("all");
    setError(null);
    try {
      await revokeAllSessions();
      await refreshOrganizations();
    } catch (revokeErr) {
      setError(revokeErr instanceof ApiError ? revokeErr.message : "Unable to revoke authentication sessions.");
    } finally {
      setRevokingKey(null);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P42-01"
        title="Organizations"
        description="Multi-tenant dealer identity foundation with deterministic slugs, membership lineage, invitation tokens, and append-only organization audit history."
        actions={
          <Link to="/dashboard" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
            Dashboard
          </Link>
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      <div className="mt-6 grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
        <OrganizationCreateForm submitting={submitting} onSubmit={handleCreate} />
        {loading ? (
          <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-300">Loading organizations...</section>
        ) : (
          <OrganizationListPanel organizations={organizations} />
        )}
      </div>
      {!loading ? (
        <div className="mt-4 grid gap-4 xl:grid-cols-[0.95fr,1.05fr]">
          <SecurityContextPanel
            organizations={organizations}
            securityContext={securityContext}
            switching={switchingOrg}
            onSwitch={handleSwitchOrganization}
          />
          <AuthSessionListPanel
            sessions={sessions}
            revoking={revokingKey}
            onRevoke={handleRevokeSession}
            onRevokeAll={handleRevokeAllSessions}
          />
        </div>
      ) : null}
    </AppShell>
  );
}
