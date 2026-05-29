import { EmptyState } from "../../EmptyState";

export function OrganizationAccessDeniedState({
  title,
  description,
}: {
  title: string;
  description: string;
}): JSX.Element {
  return <EmptyState title={title} description={description} />;
}
