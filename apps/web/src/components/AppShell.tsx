import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import {
  DEFAULT_EXPANDED_GROUP_IDS,
  NAV_EXPANDED_STORAGE_KEY,
  findGroupIdForPath,
  visibleNavGroups,
  type NavLinkItem,
} from "../config/appNavigation";

function loadExpandedGroupIds(): Set<string> {
  try {
    const raw = localStorage.getItem(NAV_EXPANDED_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as unknown;
      if (Array.isArray(parsed) && parsed.every((item) => typeof item === "string")) {
        return new Set(parsed);
      }
    }
  } catch {
    // ignore
  }
  return new Set(DEFAULT_EXPANDED_GROUP_IDS);
}

function saveExpandedGroupIds(ids: Set<string>): void {
  localStorage.setItem(NAV_EXPANDED_STORAGE_KEY, JSON.stringify([...ids]));
}

function isLinkActive(pathname: string, to: string): boolean {
  return pathname === to || (to !== "/dashboard" && pathname.startsWith(`${to}/`));
}

function NavLinkRow({ link, pathname }: { link: NavLinkItem; pathname: string }) {
  const active = isLinkActive(pathname, link.to);
  return (
    <Link
      to={link.to}
      className={`block rounded-lg px-3 py-1.5 text-sm transition ${
        link.prominent && !active
          ? "font-semibold text-cyan-200 hover:bg-cyan-400/10"
          : active
            ? "bg-cyan-400 font-semibold text-slate-950"
            : "text-slate-300 hover:bg-white/5 hover:text-white"
      } ${link.prominent && active ? "ring-1 ring-cyan-300/50" : ""}`}
    >
      {link.label}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { isOpsAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [expandedGroupIds, setExpandedGroupIds] = useState<Set<string>>(() => loadExpandedGroupIds());
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const groups = useMemo(() => visibleNavGroups(isOpsAdmin), [isOpsAdmin]);

  const ensureActiveGroupExpanded = useCallback(
    (pathname: string) => {
      const groupId = findGroupIdForPath(pathname);
      if (!groupId) {
        return;
      }
      setExpandedGroupIds((prev) => {
        if (prev.has(groupId)) {
          return prev;
        }
        const next = new Set(prev);
        next.add(groupId);
        saveExpandedGroupIds(next);
        return next;
      });
    },
    [],
  );

  useEffect(() => {
    ensureActiveGroupExpanded(location.pathname);
  }, [ensureActiveGroupExpanded, location.pathname]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  function toggleGroup(groupId: string) {
    if (groupId === "primary") {
      return;
    }
    setExpandedGroupIds((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      saveExpandedGroupIds(next);
      return next;
    });
  }

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  function renderNavGroups() {
    return (
      <div className="space-y-1">
        {groups.map((group) => {
          const isPrimary = group.id === "primary";
          const isExpanded = isPrimary || expandedGroupIds.has(group.id);
          return (
            <section key={group.id} className="rounded-xl border border-white/5 bg-slate-900/40">
              <button
                type="button"
                onClick={() => toggleGroup(group.id)}
                disabled={isPrimary}
                aria-expanded={isExpanded}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.14em] ${
                  isPrimary ? "cursor-default text-cyan-200/90" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <span>{group.title}</span>
                {!isPrimary ? (
                  <span className="text-slate-500" aria-hidden>
                    {isExpanded ? "−" : "+"}
                  </span>
                ) : null}
              </button>
              {isExpanded ? (
                <div className="space-y-0.5 px-2 pb-2">
                  {group.links.map((link) => (
                    <NavLinkRow key={link.to} link={link} pathname={location.pathname} />
                  ))}
                </div>
              ) : null}
            </section>
          );
        })}
        <section className="rounded-xl border border-white/5 bg-slate-900/40 px-2 py-2">
          <p className="px-1 pb-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Account</p>
          <button
            type="button"
            onClick={handleLogout}
            className="block w-full rounded-lg px-3 py-1.5 text-left text-sm text-slate-300 transition hover:bg-white/5 hover:text-white"
          >
            Logout
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="rounded-lg border border-white/10 px-2 py-1 text-sm text-slate-200 lg:hidden"
              onClick={() => setMobileNavOpen((open) => !open)}
              aria-expanded={mobileNavOpen}
              aria-label="Toggle navigation menu"
            >
              Menu
            </button>
            <Link
              to="/executive-dashboard"
              className="inline-flex shrink-0 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200"
            >
              ComicOS
            </Link>
            <p className="hidden truncate text-sm text-slate-500 md:block">
              Portfolio Intelligence for Comic Investors
            </p>
          </div>
          <Link
            to="/executive-dashboard"
            className="hidden rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-1.5 text-sm font-semibold text-cyan-100 sm:inline-flex"
          >
            Executive Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px] gap-6 px-4 py-4 sm:px-6 lg:px-8">
        <aside
          className={`${
            mobileNavOpen ? "block" : "hidden"
          } w-full shrink-0 lg:block lg:w-72 xl:w-80`}
        >
          <nav
            aria-label="Main navigation"
            className="max-h-[calc(100vh-5.5rem)] overflow-y-auto pr-1 lg:sticky lg:top-[4.25rem]"
          >
            {renderNavGroups()}
          </nav>
        </aside>

        <main className="min-w-0 flex-1 pb-8">{children}</main>
      </div>
    </div>
  );
}
