import { apiClient, type OrganizationSecurityContextRead, type UserAuthSessionRead } from "../api/client";
import { syncPersistedSecurityContext } from "./securityContext";

export async function listActiveSessions(): Promise<UserAuthSessionRead[]> {
  const response = await apiClient.listAuthSessions({ limit: 100, offset: 0 });
  return response.items;
}

export async function revokeSession(sessionId: number): Promise<UserAuthSessionRead> {
  return apiClient.revokeAuthSession({ session_id: sessionId });
}

export async function revokeAllSessions(): Promise<UserAuthSessionRead[]> {
  const response = await apiClient.revokeAllAuthSessions();
  return response.items;
}

export async function hydrateSecurityContext(): Promise<OrganizationSecurityContextRead> {
  const context = await apiClient.getSecurityContext();
  syncPersistedSecurityContext(context);
  return context;
}

export async function switchOrganizationContext(organizationId: number): Promise<OrganizationSecurityContextRead> {
  const context = await apiClient.switchActiveOrganization({ organization_id: organizationId });
  syncPersistedSecurityContext(context);
  return context;
}
