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
    try {
      setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      // localStorage unavailable (private window, blocked site data) -- stays expanded
    }
  }, []);

  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

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
    <div className="flex h-screen overflow-hidden bg-paper">
      <AdminSidebar
        active={active}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex h-14 shrink-0 items-center gap-space-3 border-b border-line bg-card px-space-4 lg:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="-ml-space-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-ink-600 hover:bg-paper"
          >
            <Menu size={20} strokeWidth={2} />
          </button>
          <span className="truncate text-[14px] font-bold text-ink-900">Platform admin</span>
        </header>

        <main className="flex-1 overflow-y-auto p-space-3 xs:p-space-4 sm:p-space-6">{children}</main>
      </div>
    </div>
  );
}
