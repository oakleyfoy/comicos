import type { ReactNode } from "react";

import { PatriotPageLayout, PatriotPanel } from "../../PatriotPageLayout";
import { DiscoveryNav } from "./DiscoveryNav";

type Props = {
  title: string;
  eyebrow?: string;
  error?: string | null;
  onRetry?: () => void;
  loading?: boolean;
  children: ReactNode;
};

export function DiscoveryPageLayout({
  title,
  eyebrow = "P81 · Discovery",
  error,
  onRetry,
  loading,
  children,
}: Props): JSX.Element {
  return (
    <PatriotPageLayout
      eyebrow={eyebrow}
      title={title}
      error={error}
      onRetry={onRetry}
      loading={loading}
      subNav={<DiscoveryNav variant="patriot" />}
    >
      {children}
    </PatriotPageLayout>
  );
}

export { PatriotPanel };
