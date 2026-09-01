"use client";

import {
  ChevronsLeft,
  ChevronsRight,
  ClipboardList,
  LogOut,
  Settings,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { clearAdminToken, getSuperAdmin } from "@/lib/adminAuth";

const NAV_ITEMS = [
  { key: "tenants", label: "Tenants", icon: ShieldCheck, href: "/admin/tenants" },
  { key: "users", label: "Users", icon: Users, href: "/admin/users" },
  { key: "audit-log", label: "Audit Log", icon: ClipboardList, href: "/admin/audit-log" },
  { key: "platform-settings", label: "Platform Settings", icon: Settings, href: "/admin/platform-settings" },
];

type Props = {
  active: string;
  /** Mobile drawer state -- undefined/false renders the sidebar off-canvas
   * below the `lg` breakpoint (AdminShell owns the toggle); at `lg` and up
   * the sidebar is always statically visible regardless of this prop. */
  open?: boolean;
  onClose?: () => void;
  /** Desktop-only icon-rail collapse, owned by AdminShell (persisted to
   * localStorage there) -- has no effect below `lg`, where the sidebar is
   * already an off-canvas drawer and collapsing it would be meaningless. */
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
};

export function AdminSidebar({ active, open = false, onClose, collapsed = false, onToggleCollapsed }: Props) {
  const superAdmin = getSuperAdmin();

  function handleLogout() {
    clearAdminToken();
    // Hard navigation, not router.push: /admin/tenants stays inside the same
    // AdminSecretGate-gated layout, and that gate only checks for a token
    // once on mount -- a client-side push would leave the page rendered as
    // still logged in until something else happened to force a reload.
    window.location.href = "/admin/tenants";
  }

  return (
    <>
      {/* Backdrop, mobile drawer only */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-40 bg-black/40 transition-opacity duration-200 lg:hidden",
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex h-screen w-72 max-w-[85vw] shrink-0 -translate-x-full flex-col bg-brand-700 px-space-3 py-space-4 text-white transition-transform duration-200 ease-out",
          "lg:static lg:z-auto lg:max-w-none lg:translate-x-0 lg:transition-[width] lg:duration-200",
          collapsed ? "lg:w-[68px] lg:px-space-2" : "lg:w-60",
          open && "translate-x-0",
        )}
      >
        <div className="mb-space-5 flex items-center gap-space-2 px-space-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/15 font-display text-[14px] font-extrabold">
            A
          </div>
          {!collapsed && <span className="truncate text-[14px] font-bold">{superAdmin?.name || "Platform admin"}</span>}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="ml-auto flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-white/70 hover:bg-white/10 hover:text-white lg:hidden"
          >
            <X size={18} strokeWidth={2} />
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(({ key, label, icon: Icon, href }) => {
            const isActive = key === active;
            return (
              <Link
                key={key}
                href={href}
                onClick={onClose}
                title={collapsed ? label : undefined}
                className={cn(
                  "flex w-full items-center gap-space-3 rounded-md px-space-3 py-space-2 text-left text-[13.5px] font-medium transition-colors duration-150",
                  collapsed && "lg:justify-center lg:px-0",
                  isActive && "bg-white text-brand-700",
                  !isActive && "text-white/85 hover:bg-white/10 hover:text-white",
                )}
              >
                <Icon size={16} strokeWidth={2} className="shrink-0" />
                {!collapsed && label}
              </Link>
            );
          })}
        </nav>

        {onToggleCollapsed && (
          <button
            type="button"
            onClick={onToggleCollapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "mb-space-1 hidden w-full items-center gap-space-3 rounded-md px-space-3 py-space-2 text-left text-[13.5px] font-medium text-white/70 transition-colors duration-150 hover:bg-white/10 hover:text-white lg:flex",
              collapsed && "justify-center px-0",
            )}
          >
            {collapsed ? <ChevronsRight size={16} strokeWidth={2} className="shrink-0" /> : <ChevronsLeft size={16} strokeWidth={2} className="shrink-0" />}
            {!collapsed && "Collapse"}
          </button>
        )}

        <button
          type="button"
          onClick={handleLogout}
          title={collapsed ? "Log out" : undefined}
          className={cn(
            "flex w-full items-center gap-space-3 rounded-md px-space-3 py-space-2 text-left text-[13.5px] font-medium text-white/70 transition-colors duration-150 hover:bg-white/10 hover:text-white",
            collapsed && "lg:justify-center lg:px-0",
          )}
        >
          <LogOut size={16} strokeWidth={2} className="shrink-0" />
          {!collapsed && "Log out"}
        </button>
      </aside>
    </>
  );
}
