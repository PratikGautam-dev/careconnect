"use client";

import type { LucideIcon } from "lucide-react";
import {
  Calendar,
  CreditCard,
  Eye,
  Hash,
  Mail,
  MapPin,
  MessageCircle,
  Receipt,
  Shield,
  UserRound,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { formatDate } from "@/lib/formatDate";
import type { Tenant, TenantProfile } from "@/hooks/useTenants";
import type { PaymentSettingsDetail } from "@/hooks/useEditTenant";
import type { SubscriptionRecord } from "@/hooks/useAdminSubscriptions";
import { STATUS_LABEL, STATUS_TONE } from "../../subscriptions/_components/subscription-columns";

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="gap-space-3 flex items-center justify-between text-[13px]">
      <span className="gap-space-2 text-ink-400 flex items-center">
        <Icon size={14} className="shrink-0" /> {label}
      </span>
      <span className="text-ink-900 truncate text-right font-medium">{value}</span>
    </div>
  );
}

type Props = {
  hospital: Tenant | null;
  // Real hospital<->plan record (admin/subscriptions_api.py) for this same
  // hospital, matched by hospital_id on the page -- null while the
  // subscriptions list is still loading, or (legitimately) for a hospital
  // that's never been assigned a plan.
  subscription: SubscriptionRecord | null;
  // On-demand single-tenant detail fetch (useTenantProfile) -- owners/
  // enabled_features only exist on that endpoint, not the list summary this
  // panel is otherwise built from, so it's null until that fetch resolves.
  profile: TenantProfile | null;
  // On-demand payment-routing fetch (useTenantPaymentSettings) -- same
  // "null until it resolves" shape as profile above.
  paymentSettings: PaymentSettingsDetail | null;
};

/** Right-rail "selected hospital" detail card -- same layout convention as
 * StaffDetailPanel/PaymentDetailPanel (avatar-less header + a DetailRow
 * stack + a tile grid + an extra section), for the /admin/tenants Hospital
 * Directory's default-first-row-selected master-detail view. */
export function HospitalDetailPanel({ hospital, subscription, profile, paymentSettings }: Props) {
  if (!hospital) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">
          Select a hospital to view its profile.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 gap-space-3 flex items-center justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="text-eyebrow">Tenant Profile</p>
          <p className="text-ink-900 truncate text-[15px] font-bold">{hospital.name}</p>
        </div>
        <Badge tone={hospital.is_active ? "success" : "neutral"}>
          {hospital.is_active ? "Active" : "Inactive"}
        </Badge>
      </div>

      <div className="space-y-space-2 border-line pt-space-3 border-t">
        <DetailRow icon={Hash} label="Hospital ID" value={`#${hospital.id}`} />
        <DetailRow icon={MapPin} label="Location" value={hospital.contact_address || "—"} />
        <DetailRow
          icon={MessageCircle}
          label="WhatsApp"
          value={hospital.whatsapp_phone_number_id ? "Enabled" : "Disabled"}
        />
        <DetailRow
          icon={Wallet}
          label="Payment configuration"
          value={
            !paymentSettings ? (
              "Loading…"
            ) : (
              <Badge tone={paymentSettings.payment_mode === "hospital_own" ? "brand" : "neutral"}>
                {paymentSettings.payment_mode === "hospital_own" ? "Own Razorpay" : "Platform"}
              </Badge>
            )
          }
        />
        <DetailRow
          icon={Receipt}
          label="GST / platform fee"
          value={
            !paymentSettings
              ? "Loading…"
              : (() => {
                  const gstOn = paymentSettings.override_fees
                    ? paymentSettings.gst_enabled
                    : paymentSettings.default_gst_enabled;
                  const feeOn = paymentSettings.override_fees
                    ? paymentSettings.platform_fee_enabled
                    : paymentSettings.default_platform_fee_enabled;
                  const source = paymentSettings.override_fees ? "own rate" : "platform default";
                  if (!gstOn && !feeOn) return `Off (${source})`;
                  return `${gstOn ? "GST" : ""}${gstOn && feeOn ? " + " : ""}${feeOn ? "Platform fee" : ""} (${source})`;
                })()
          }
        />
        <DetailRow icon={Calendar} label="Onboarded" value={formatDate(hospital.created_at)} />
      </div>

      <div className="mt-space-3 gap-space-2 grid grid-cols-2">
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <CreditCard size={12} /> Subscription
          </p>
          <div className="gap-space-2 flex items-center">
            <Badge tone={subscription ? STATUS_TONE[subscription.status] : "neutral"}>
              {subscription ? STATUS_LABEL[subscription.status] || subscription.status : "Unassigned"}
            </Badge>
            {subscription?.plan_name && (
              <span className="text-ink-900 text-[13px] font-bold">{subscription.plan_name}</span>
            )}
          </div>
        </div>
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <Calendar size={12} /> Renewal Date
          </p>
          <p className="text-ink-900 text-[13px] font-bold">
            {subscription?.renewal_date ? formatDate(subscription.renewal_date) : "—"}
          </p>
        </div>
      </div>

      <div className="mt-space-4 border-line pt-space-3 border-t">
        <p className="text-label text-ink-900 mb-space-2 font-bold">Primary Admin</p>
        {!profile ? (
          <p className="text-ink-400 text-[12.5px]">Loading…</p>
        ) : profile.owners.length === 0 ? (
          <p className="text-ink-400 text-[12.5px]">No admin assigned yet.</p>
        ) : (
          <div className="space-y-space-2">
            <DetailRow icon={UserRound} label="Name" value={profile.owners[0].name || "—"} />
            <DetailRow icon={Mail} label="Email" value={profile.owners[0].email} />
            {profile.owners.length > 1 && (
              <DetailRow
                icon={Shield}
                label="Other admins"
                value={`+${profile.owners.length - 1} more`}
              />
            )}
          </div>
        )}
      </div>

      <div className="mt-space-4 border-line pt-space-3 border-t">
        <p className="text-label text-ink-900 mb-space-2 font-bold">Modules Enabled</p>
        {!profile ? (
          <p className="text-ink-400 text-[12.5px]">Loading…</p>
        ) : profile.enabled_features.length === 0 ? (
          <p className="text-ink-400 text-[12.5px]">No modules enabled.</p>
        ) : (
          <div className="gap-space-2 flex flex-wrap">
            {profile.enabled_features.map((key) => (
              <span
                key={key}
                className="bg-brand-50 text-brand-700 px-space-2 rounded-full py-1 text-[11.5px] font-semibold"
              >
                {profile.feature_default_labels[key] || key}
              </span>
            ))}
          </div>
        )}
      </div>

      <Link
        href={`/admin/tenants/${hospital.id}`}
        className="bg-brand-600 hover:bg-brand-700 gap-space-2 px-space-3 py-space-2 mt-space-4 flex w-full items-center justify-center rounded-md text-[13px] font-semibold text-white transition-colors duration-150"
      >
        <Eye size={14} /> View full hospital profile
      </Link>
    </Card>
  );
}
