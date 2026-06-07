import { useLocation } from "react-router-dom";

import { PatriotMobileNav, PatriotMobileShell } from "./PatriotMobileShell";

const MOBILE_OPS_LINKS = [
  { to: "/mobile-scan", label: "Scan" },
  { to: "/mobile-intake", label: "Intake" },
  { to: "/mobile-storage", label: "Storage" },
  { to: "/mobile-audit", label: "Audit" },
  { to: "/mobile-operations", label: "Ops" },
];

export function MobileOpsShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}): JSX.Element {
  const { pathname } = useLocation();
  return (
    <PatriotMobileShell
      eyebrow="P80-02 · Mobile"
      title={title}
      subNav={<PatriotMobileNav links={MOBILE_OPS_LINKS} pathname={pathname} />}
    >
      {children}
    </PatriotMobileShell>
  );
}
