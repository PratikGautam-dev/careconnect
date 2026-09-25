"use client";

import { Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { AdminSidebar } from "@/components/admin/AdminSidebar";

const COLLAPSE_KEY = "admin_sidebar_collapsed";

type Props = {
  active: string;
  children: React.ReactNode;
};

/** Shared shell for every /admin/* page, mirroring PortalShell's structure
 * (sidebar: static column at `lg`+, off-canvas drawer below it, mobile top
 * bar with a hamburger toggle) with one addition -- a desktop icon-rail
 * collapse, persisted to localStorage so it survives a reload/tab reopen
 * (per-viewer UI preference, not something that needs to sync across
 * devices or be readable by the backend). */
export function AdminShell({ active, children }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    // Deliberately a real effect, not restructured: `collapsed` has to
    // start `false` on both the server render and the client's first
    // (hydration) render -- reading localStorage directly during render
    // would desync those two and trigger a hydration mismatch. Correcting
    // it one tick after mount (a brief, accepted layout shift for restoring
    // a per-viewer UI preference) is the standard fix for exactly this,
    // same as any other "read a browser-only API, then setState" effect.
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      // localStorage unavailable (private window, blocked site data) -- stays expanded
    }
  }, []);

  // A nav Link tap already covers most navigations, but this also catches
  // back/forward and any other route change -- adjusted directly in the
  // render body (comparing against a tracked previous pathname) rather than
  // in an effect, per React's own "Adjusting some state when a prop
  // changes" guide: this resets local UI state in response to a changing
  // value, it doesn't synchronize with anything external.
  const [prevPathname, setPrevPathname] = useState(pathname);
  if (pathname !== prevPathname) {
    setPrevPathname(pathname);
    setSidebarOpen(false);
  }

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        // best-effort persistence only
      }
      return next;
    });
  }

  return (
    <div className="bg-paper flex h-screen overflow-hidden">
      <AdminSidebar
        active={active}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="gap-space-3 border-line bg-card px-space-4 flex h-14 shrink-0 items-center border-b lg:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="-ml-space-2 text-ink-600 hover:bg-paper flex h-9 w-9 shrink-0 items-center justify-center rounded-md"
          >
            <Menu size={20} strokeWidth={2} />
          </button>
          <span className="text-ink-900 truncate text-[14px] font-bold">Platform admin</span>
        </header>

        <main className="p-space-3 xs:p-space-4 sm:p-space-6 flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
