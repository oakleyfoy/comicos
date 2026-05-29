import type { OrganizationResponse, OrganizationSecurityContextRead } from "../api/client";

const ACTIVE_ORGANIZATION_STORAGE_KEY = "comic-os.active-organization-id";

export function getPersistedActiveOrganizationId(): number | null {
  const raw = localStorage.getItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

export function persistActiveOrganizationId(organizationId: number | null): void {
  if (organizationId === null) {
    localStorage.removeItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
    return;
  }
  localStorage.setItem(ACTIVE_ORGANIZATION_STORAGE_KEY, String(organizationId));
}

export function clearPersistedActiveOrganizationId(): void {
  localStorage.removeItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
}

export function syncPersistedSecurityContext(context: OrganizationSecurityContextRead | null): void {
  persistActiveOrganizationId(context?.active_organization_id ?? null);
}

export function resolveSecurityContextOrganization(
  organizations: OrganizationResponse[],
  context: OrganizationSecurityContextRead | null,
): OrganizationResponse | null {
  const activeOrganizationId = context?.active_organization_id ?? getPersistedActiveOrganizationId();
  if (activeOrganizationId == null) return null;
  return organizations.find((organization) => organization.id === activeOrganizationId) ?? null;
}
