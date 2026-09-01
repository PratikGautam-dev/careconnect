"use client";

import { usePathname } from "next/navigation";
import { AdminSecretGate } from "@/components/admin/AdminSecretGate";
import { AdminShell } from "@/components/admin/AdminShell";

const ACTIVE_BY_SEGMENT: Record<string, string> = {
  tenants: "tenants",
  users: "users",
  "audit-log": "audit-log",
  "platform-settings": "platform-settings",
};

/** Shared layout for the sidebar-shell pages (tenants, users, audit-log,
 * platform-settings) -- a Next.js layout persists across
 * navigations within it (only the page content below swaps), unlike each
 * page mounting its own <AdminSecretGate>/<AdminShell>, which was
 * remounting BOTH on every navigation between them. AdminSecretGate starts
 * in a "checking" state that renders nothing at all for one tick before its
 * effect resolves -- with a fresh instance on every page, that meant the
 * whole shell (sidebar included) blanked out on every click between admin
 * pages. One instance here fixes that.
 *
 * onboard-hospital is NOT in this route group -- it's a focused, full-screen
 * signup wizard, not a page someone browses to from this sidebar, so it
 * keeps its own standalone <AdminSecretGate> instead of gaining a sidebar it
 * was never designed to sit inside. */
export default function AdminDashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const segment = pathname.split("/")[2] || "";
  const active = ACTIVE_BY_SEGMENT[segment] || "";

  return (
    <AdminSecretGate title="Platform admin sign-in">
      <AdminShell active={active}>{children}</AdminShell>
    </AdminSecretGate>
  );
}
