import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ComicOsMark } from "./ComicOsMark";
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
  if (to === "/dashboard") {
    return pathname === "/dashboard";
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

function NavLinkRow({ link, pathname }: { link: NavLinkItem; pathname: string }) {
  const active = isLinkActive(pathname, link.to);
  return (
    <Link
      to={link.to}
      className={`block rounded-lg px-3 py-1.5 text-sm transition ${
        link.prominent && !active
          ? "font-semibold text-patriot-blue hover:bg-blue-50"
          : active
            ? "bg-patriot-blue font-semibold text-white shadow-sm"
            : "text-slate-700 hover:bg-slate-100 hover:text-patriot-navy"
      } ${link.prominent && active ? "ring-1 ring-blue-300" : ""}`}
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
            <section key={group.id} className="rounded-xl border border-blue-100 bg-white shadow-sm">
              <button
                type="button"
                onClick={() => toggleGroup(group.id)}
                disabled={isPrimary}
                aria-expanded={isExpanded}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.14em] ${
                  isPrimary ? "cursor-default text-patriot-red" : "text-slate-600 hover:text-patriot-navy"
                }`}
              >
                <span>{group.title}</span>
                {!isPrimary ? (
                  <span className="text-slate-400" aria-hidden>
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
        <section className="rounded-xl border border-blue-100 bg-white px-2 py-2 shadow-sm">
          <p className="px-1 pb-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Account</p>
          <button
            type="button"
            onClick={handleLogout}
            className="block w-full rounded-lg px-3 py-1.5 text-left text-sm text-slate-700 transition hover:bg-red-50 hover:text-patriot-red"
          >
            Logout
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="min-h-screen text-slate-900">
      <header className="sticky top-0 z-30 border-b-4 border-patriot-red bg-patriot-navy text-white shadow-md">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="rounded-lg border border-white/30 bg-white/10 px-2 py-1 text-sm text-white lg:hidden"
              onClick={() => setMobileNavOpen((open) => !open)}
              aria-expanded={mobileNavOpen}
              aria-label="Toggle navigation menu"
            >
              Menu
            </button>
            <Link
              to="/executive-dashboard"
              className="inline-flex shrink-0 items-center gap-2 rounded-full border border-white bg-white px-3 py-1 text-xs font-bold uppercase tracking-[0.22em] text-patriot-navy"
            >
              <ComicOsMark size={18} />
              ComicOS
            </Link>
            <p className="hidden truncate text-sm text-blue-100 md:block">
              Portfolio Intelligence for Comic Investors
            </p>
          </div>
          <Link
            to="/executive-dashboard"
            className="hidden rounded-lg border border-white/40 bg-patriot-red px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700 sm:inline-flex"
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
