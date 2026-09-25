"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { AlertTriangle, Sparkles } from "lucide-react";
import { PlanUpgradeModal } from "@/components/portal/PlanUpgradeModal";
import { hasCapability, hasPermission, useStaffSession } from "@/lib/staffAuth";

// Deliberately ONE message regardless of WHY access.reason says it's
// blocked (no_plan/expired/cancelled/trial_ended/renewal_ended) -- whether
// this hospital never had a plan, let one lapse, or had it cancelled makes
// no difference to what the viewer needs to do about it right now:
// subscribe/renew. reason still travels on the session for anything that
// wants to branch on it later, just not surfaced as five different titles.
const GATE_COPY = {
  title: "No Active Subscription",
  body:
    "This hospital doesn't have an active CareConnect subscription. Please subscribe to continue using " +
    "appointments, staff management, and every other feature.",
};

/** Wraps every /portal/* page (app/portal/layout.tsx) below
 * StaffSessionProvider. Checked exactly ONCE per session -- the moment
 * StaffSessionProvider's own /me (or a fresh login/refresh response, all
 * three embed subscription_access server-side, staff_auth.py) resolves,
 * we already know both who's logged in AND whether their hospital's
 * subscription is active, atomically, in the same response. If not: the
 * whole portal is replaced with this takeover instead of rendering.
 *
 * Deliberately NOT a live/reactive gate: no polling, no background
 * recheck, no listening for a stray 402 from some unrelated page query.
 * That reactive design used to cause real bugs -- a visible flash on every
 * page reload (state had to round-trip the network to know it was still
 * blocked), and the dialog incorrectly appearing on /portal/login itself
 * (a global store didn't know it should only apply post-login). Checking
 * once, as part of the session itself, is structurally immune to both:
 * `session` is null on /portal/login (nothing to gate), and it's known
 * synchronously the instant the session is. The tradeoff -- a hospital
 * that fixes billing mid-session won't see this lift until they log out
 * and back in -- is intentional; the note at the bottom says so.
 *
 * /portal/login is ALWAYS exempt, explicitly, regardless of session --
 * the "session is null there" assumption above only holds for a visitor
 * who's genuinely logged out. Someone still authenticated (the access
 * token lives in memory, independent of which page they're on) who lands
 * back on /portal/login for any reason would otherwise get a real,
 * resolved, blocked session there too -- and see this takeover instead of
 * the actual login form, with no way to log out and back in (the one
 * thing the takeover's own note tells them to do).
 *
 * "Upgrade Plan" opens PlanUpgradeModal (an in-portal modal, NOT a
 * navigation to /plans -- that's a separate, public, informational-only
 * page for browsing without an account) and is only shown to staff who
 * can actually act on it (settings:write + manage_settings); everyone
 * else just sees "contact your administrator," no dead-end button.
 *
 * This is a UX layer only, not the real gate -- the backend middleware (and
 * the WhatsApp bot's own equivalent check) is what actually enforces this;
 * even if this component were bypassed entirely, every API call still
 * fails closed server-side. */
export function SubscriptionGate({ children }: { children: React.ReactNode }) {
  const session = useStaffSession();
  const pathname = usePathname();
  const [upgradeOpen, setUpgradeOpen] = useState(false);

  if (pathname === "/portal/login" || !session || session.subscription_access.allowed)
    return <>{children}</>;

  const canManageBilling =
    hasPermission(session, "settings", "write") && hasCapability(session, "settings");

  return (
    <div className="bg-paper flex min-h-screen items-center justify-center p-4">
      <div className="bg-card p-space-8 w-full max-w-3xl rounded-lg text-center shadow-2xl">
        <div className="bg-error-tint text-error mb-space-4 mx-auto flex h-14 w-14 items-center justify-center rounded-full">
          <AlertTriangle size={26} />
        </div>
        <h1 className="text-ink-900 text-[20px] font-bold">{GATE_COPY.title}</h1>
        <p className="text-hint mt-space-2 mx-auto max-w-md text-[13.5px]">{GATE_COPY.body}</p>
        {canManageBilling ? (
          <button
            type="button"
            onClick={() => setUpgradeOpen(true)}
            className="bg-brand-600 hover:bg-brand-700 mt-space-6 gap-space-2 mx-auto flex h-11 w-full max-w-xs items-center justify-center rounded-md text-[14px] font-semibold text-white"
          >
            <Sparkles size={16} /> Upgrade Plan
          </button>
        ) : (
          <p className="text-hint mt-space-6 text-[12.5px]">
            Contact your hospital administrator to subscribe or renew this plan.
          </p>
        )}
        <p className="text-ink-400 mt-space-4 text-[11.5px]">
          Already completed payment? Log out and log back in to refresh your access.
        </p>
      </div>
      {canManageBilling && <PlanUpgradeModal open={upgradeOpen} onOpenChange={setUpgradeOpen} />}
    </div>
  );
}
