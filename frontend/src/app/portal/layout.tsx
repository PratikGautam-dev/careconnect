import { StaffSessionProvider } from "@/components/portal/StaffSessionProvider";

/** Every /portal/* page (including login, harmlessly -- the provider's own
 * fetch just 401s there and leaves session null) renders inside this, so
 * useStaffSession() works the same whether it's called from PortalSidebar,
 * a page's own top-level guard, or a hook like usePortalGuard. */
export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return <StaffSessionProvider>{children}</StaffSessionProvider>;
}
