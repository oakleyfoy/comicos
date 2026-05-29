import type { OrganizationResponse } from "../api/client";

export const ORGANIZATION_PERMISSION_ORDER = [
  "organization:view",
  "organization:update",
  "organization:archive",
  "members:view",
  "members:invite",
  "members:remove",
  "members:roles:update",
  "inventory:view",
  "inventory:create",
  "inventory:update",
  "inventory:delete",
  "operations:view",
  "operations:manage",
  "audit:view",
] as const;

export const ORGANIZATION_ROLE_ORDER = ["owner", "admin", "manager", "staff", "viewer"] as const;

export function hasOrganizationPermission(
  organization: Pick<OrganizationResponse, "current_user_permission_keys"> | null | undefined,
  permissionKey: string,
): boolean {
  return Boolean(organization?.current_user_permission_keys.includes(permissionKey));
}

export function sortRoleKeys(roleKeys: string[]): string[] {
  return [...roleKeys].sort((left, right) => {
    const leftIndex = ORGANIZATION_ROLE_ORDER.indexOf(left as (typeof ORGANIZATION_ROLE_ORDER)[number]);
    const rightIndex = ORGANIZATION_ROLE_ORDER.indexOf(right as (typeof ORGANIZATION_ROLE_ORDER)[number]);
    return (leftIndex === -1 ? 999 : leftIndex) - (rightIndex === -1 ? 999 : rightIndex) || left.localeCompare(right);
  });
}

export function roleTone(roleKey: string): string {
  switch (roleKey) {
    case "owner":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "admin":
      return "border-fuchsia-400/35 bg-fuchsia-400/10 text-fuchsia-100";
    case "manager":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "staff":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    default:
      return "border-slate-400/35 bg-slate-400/10 text-slate-200";
  }
}
