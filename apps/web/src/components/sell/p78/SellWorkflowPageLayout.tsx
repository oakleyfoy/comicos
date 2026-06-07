import type { ReactNode } from "react";

import { PatriotPageLayout, PatriotPanel } from "../../PatriotPageLayout";
import { SellWorkflowNav } from "./SellWorkflowNav";

type Props = {
  title: string;
  eyebrow?: string;
  error?: string | null;
  onRetry?: () => void;
  loading?: boolean;
  headerActions?: ReactNode;
  children: ReactNode;
};

export function SellWorkflowPageLayout({
  title,
  eyebrow = "P78 · Sell",
  error,
  onRetry,
  loading,
  headerActions,
  children,
}: Props): JSX.Element {
  return (
    <PatriotPageLayout
      eyebrow={eyebrow}
      title={title}
      error={error}
      onRetry={onRetry}
      loading={loading}
      subNav={<SellWorkflowNav variant="patriot" />}
      headerActions={headerActions}
    >
      {children}
    </PatriotPageLayout>
  );
}

export { PatriotPanel };
