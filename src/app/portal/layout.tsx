import { StaffSessionProvider } from "@/components/portal/StaffSessionProvider";
import { SubscriptionGate } from "@/components/portal/SubscriptionGate";

/** Every /portal/* page (including login, harmlessly -- the provider's own
 * fetch just 401s there and leaves session null) renders inside this, so
 * useStaffSession() works the same whether it's called from PortalSidebar,
 * a page's own top-level guard, or a hook like usePortalGuard.
 *
 * SubscriptionGate sits INSIDE StaffSessionProvider (needs useStaffSession
 * to decide whether to show a "Reactivate Billing" button or just a
 * message) and wraps every page below it -- see its own docstring for how
 * it blurs+blocks once a hospital's subscription is inactive. */
export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <StaffSessionProvider>
      <SubscriptionGate>{children}</SubscriptionGate>
    </StaffSessionProvider>
  );
}
