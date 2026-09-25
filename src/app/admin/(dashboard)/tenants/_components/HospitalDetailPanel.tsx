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
  Shield,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { formatDate } from "@/lib/formatDate";
import type { Tenant } from "@/hooks/useTenants";
import { TIER_LABELS } from "./tenant-columns";

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

// Everything under "Primary Admin"/"Modules Enabled"/the renewal tile has no
// real backing field on the tenant SUMMARY this panel is built from (owners/
// enabled_features only exist on the single-tenant detail fetch,
// useEditTenant.ts's TenantDetail -- not loaded here to keep row selection
// instant, same master-detail convention Staff/Billing already use).
// Hardcoded to match the target design's layout, tagged Mock rather than
// left out.
const MOCK_PRIMARY_ADMIN = { name: "Dr. Priya Sharma", role: "IT Administrator", email: "admin@hospital.com" };
const MOCK_MODULES = ["Appointments", "Patients", "Doctors", "Billing", "Reports"];

type Props = {
  hospital: Tenant | null;
};

/** Right-rail "selected hospital" detail card -- same layout convention as
 * StaffDetailPanel/PaymentDetailPanel (avatar-less header + a DetailRow
 * stack + a tile grid + an extra section), for the /admin/tenants Hospital
 * Directory's default-first-row-selected master-detail view. */
export function HospitalDetailPanel({ hospital }: Props) {
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
          <p className="text-eyebrow">Hospital Profile</p>
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
          icon={CreditCard}
          label="Plan"
          value={TIER_LABELS[hospital.data_tier] || hospital.data_tier}
        />
        <DetailRow
          icon={MessageCircle}
          label="WhatsApp"
          value={hospital.whatsapp_phone_number_id ? "Enabled" : "Disabled"}
        />
        <DetailRow icon={Calendar} label="Onboarded" value={formatDate(hospital.created_at)} />
      </div>

      <div className="mt-space-3 gap-space-2 grid grid-cols-2">
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <Shield size={12} /> Subscription
          </p>
          <p className="text-ink-900 text-[13px] font-bold">
            {hospital.is_active ? "Active" : "Inactive"}
          </p>
        </div>
        <div className="border-line bg-paper p-space-3 relative rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <Calendar size={12} /> Renewal Date
          </p>
          <p className="text-ink-900 text-[13px] font-bold">30 Sep 2026</p>
          <Badge tone="clay" className="absolute -top-2 -right-2">
            Mock
          </Badge>
        </div>
      </div>

      <div className="mt-space-4 border-line pt-space-3 border-t">
        <div className="mb-space-2 flex items-center justify-between">
          <p className="text-label text-ink-900 font-bold">Primary Admin</p>
          <Badge tone="clay">Mock</Badge>
        </div>
        <div className="space-y-space-2">
          <DetailRow icon={UserRound} label="Name" value={MOCK_PRIMARY_ADMIN.name} />
          <DetailRow icon={Shield} label="Role" value={MOCK_PRIMARY_ADMIN.role} />
          <DetailRow icon={Mail} label="Email" value={MOCK_PRIMARY_ADMIN.email} />
        </div>
      </div>

      <div className="mt-space-4 border-line pt-space-3 border-t">
        <div className="mb-space-2 flex items-center justify-between">
          <p className="text-label text-ink-900 font-bold">Modules Enabled</p>
          <Badge tone="clay">Mock</Badge>
        </div>
        <div className="gap-space-2 flex flex-wrap">
          {MOCK_MODULES.map((m) => (
            <span
              key={m}
              className="bg-brand-50 text-brand-700 px-space-2 rounded-full py-1 text-[11.5px] font-semibold"
            >
              {m}
            </span>
          ))}
        </div>
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
