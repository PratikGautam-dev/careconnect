"use client";

import {
  ChevronsLeft,
  ChevronsRight,
  CreditCard,
  HeadphonesIcon,
  Lock,
  LayoutDashboard,
  LogOut,
  Receipt,
  Settings,
  Settings2,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { clearAdminToken, getSuperAdmin } from "@/lib/adminAuth";

const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, href: "/admin/dashboard" },
  { key: "tenants", label: "Tenants", icon: ShieldCheck, href: "/admin/tenants" },
  // Subscriptions/Plans & Billing are both fully mock pages today -- there's
  // no plan/pricing/invoice model in the backend yet (only hospitals.data_tier
  // exists), see each page's own top comment. Kept in the sidebar anyway so
  // the target design's navigation is complete; wire to a real API later.
  { key: "subscriptions", label: "Subscriptions", icon: CreditCard, href: "/admin/subscriptions" },
  { key: "plans-billing", label: "Plans & Billing", icon: Receipt, href: "/admin/plans-billing" },
  { key: "users", label: "Users", icon: Users, href: "/admin/users" },
  {
    key: "support-tickets",
    label: "Support Tickets",
    icon: HeadphonesIcon,
    href: "/admin/support-tickets",
  },
  // Access Control = admin_capabilities (staff-portal management screens);
  // Feature Toggles = enabled_features (WhatsApp bot menu) -- deliberately
  // separate real per-hospital gates, portal/capabilities.py's own module
  // docstring is the source of truth for why the two must never be conflated.
  { key: "access-control", label: "Access Control", icon: Lock, href: "/admin/access-control" },
  {
    key: "feature-toggles",
    label: "Feature Toggles",
    icon: Settings2,
    href: "/admin/feature-toggles",
  },
  {
    key: "platform-settings",
    label: "Platform Settings",
    icon: Settings,
    href: "/admin/platform-settings",
  },
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

export function AdminSidebar({
  active,
  open = false,
  onClose,
  collapsed = false,
  onToggleCollapsed,
}: Props) {
  const superAdmin = getSuperAdmin();

  function handleLogout() {
    clearAdminToken();
    // Hard navigation, not router.push: /admin/tenants stays inside the same
    // AdminSecretGate-gated layout, and that gate only checks for a token
    // once on mount -- a client-side push would leave the page rendered as
    // still logged in until something else happened to force a reload.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- intentional, see comment above
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
          "bg-brand-700 px-space-3 py-space-4 fixed inset-y-0 left-0 z-50 flex h-screen w-72 max-w-[85vw] shrink-0 -translate-x-full flex-col text-white transition-transform duration-200 ease-out",
          "lg:static lg:z-auto lg:max-w-none lg:translate-x-0 lg:transition-[width] lg:duration-200",
          collapsed ? "lg:px-space-2 lg:w-[68px]" : "lg:w-60",
          open && "translate-x-0",
        )}
      >
        <div className="mb-space-5 gap-space-2 px-space-2 flex items-center">
          <div className="font-display flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/15 text-[14px] font-extrabold">
            A
          </div>
          {!collapsed && (
            <span className="truncate text-[14px] font-bold">
              {superAdmin?.name || "Platform admin"}
            </span>
          )}
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
                  "gap-space-3 px-space-3 py-space-2 flex w-full items-center rounded-md text-left text-[13.5px] font-medium transition-colors duration-150",
                  collapsed && "lg:justify-center lg:px-0",
                  isActive && "text-brand-700 bg-white",
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
              "mb-space-1 gap-space-3 px-space-3 py-space-2 hidden w-full items-center rounded-md text-left text-[13.5px] font-medium text-white/70 transition-colors duration-150 hover:bg-white/10 hover:text-white lg:flex",
              collapsed && "justify-center px-0",
            )}
          >
            {collapsed ? (
              <ChevronsRight size={16} strokeWidth={2} className="shrink-0" />
            ) : (
              <ChevronsLeft size={16} strokeWidth={2} className="shrink-0" />
            )}
            {!collapsed && "Collapse"}
          </button>
        )}

        <button
          type="button"
          onClick={handleLogout}
          title={collapsed ? "Log out" : undefined}
          className={cn(
            "gap-space-3 px-space-3 py-space-2 flex w-full items-center rounded-md text-left text-[13.5px] font-medium text-white/70 transition-colors duration-150 hover:bg-white/10 hover:text-white",
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
