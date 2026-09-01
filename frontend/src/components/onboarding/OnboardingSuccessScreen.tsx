import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { OnboardingSuccess } from "@/lib/api";

const TIER_NOTES: Record<string, string> = {
  tier1: "Using this platform's own database to manage appointments (Tier 1).",
  tier2: "Connected to the hospital's existing API (Tier 2) — the base URL/key were stored for our team to wire up next.",
  tier3: "Flagged for direct database connection (Tier 3) — a manually-assisted engagement; we'll be in touch to arrange secure access.",
};

export function OnboardingSuccessScreen({ result }: { result: OnboardingSuccess }) {
  return (
    <div className="px-space-4 py-space-9">
      <Card className="p-space-7 text-center">
        <div className="mx-auto mb-space-4 flex h-14 w-14 items-center justify-center rounded-full bg-success-tint text-success">
          <CheckCircle2 size={28} strokeWidth={2} />
        </div>
        <h1 className="text-display mb-space-2">Hospital created</h1>
        <p className="text-body mb-space-5">
          <strong className="text-ink-900">{result.hospital_name}</strong> was created with hospital ID{" "}
          <strong className="text-ink-900">{result.hospital_id}</strong> (phone_number_id:{" "}
          {result.whatsapp_phone_number_id}).
        </p>

        <p className="mb-space-5 text-[13.5px] text-ink-600">{TIER_NOTES[result.data_tier]}</p>

        {result.portal_password_set ? (
          <Button href="/portal/login" size="lg" className="mb-space-3">
            Log into bookings dashboard
          </Button>
        ) : (
          <div className="mb-space-5 rounded-lg border border-clay-300 bg-clay-100/40 p-space-4 text-left text-[13.5px] text-ink-600">
            No bookings portal password was set, so there&apos;s no way to log in yet — edit this tenant later to
            add one.
          </div>
        )}

        <p className="text-hint mb-space-5">
          Reminder: this only recorded the credentials you entered — the hospital&apos;s own Meta Business/WhatsApp
          number verification and System User access token must already have been set up on Meta&apos;s side
          beforehand. If that wasn&apos;t done first, outbound messages and webhook signature validation for this
          hospital will fail until it is.
        </p>

        <a href="/admin/onboard-hospital" className="text-[13.5px] font-semibold text-brand-600 hover:underline">
          Onboard another hospital
        </a>
      </Card>
    </div>
  );
}
