"use client";

import { use } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import { useStaffDetail } from "@/hooks/useStaffDetail";

const ROLE_LABELS: Record<string, string> = { admin: "Admin", receptionist: "Receptionist", doctor: "Doctor" };

function StaffDetailView({ hospitalId, staffId }: { hospitalId: number; staffId: number }) {
  const { staff, error } = useStaffDetail(staffId);

  return (
    <div>
      <Link
        href={`/admin/users/${hospitalId}`}
        className="mb-space-4 inline-block text-[13px] font-semibold text-brand-600 hover:underline"
      >
        ← Back to staff list
      </Link>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!staff ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
      ) : (
        <>
          <div className="mb-space-5 flex flex-col gap-space-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-eyebrow mb-space-1">{staff.hospital_name}</p>
              <h1 className="text-display">{staff.name}</h1>
            </div>
            <div className="flex items-center gap-space-2">
              <span className="rounded-full bg-brand-50 px-space-2 py-0.5 text-[11px] font-semibold text-brand-700">
                {ROLE_LABELS[staff.role] || staff.role}
              </span>
              <span
                className={cn(
                  "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                  staff.is_active ? "bg-success-tint text-success" : "bg-black/[0.05] text-ink-400",
                )}
              >
                {staff.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          </div>

          <Card className="mb-space-4 p-space-5">
            <div className="grid grid-cols-1 gap-space-4 sm:grid-cols-2">
              <Field label="Email">
                <p className="text-[13.5px] text-ink-900">{staff.email}</p>
              </Field>
              <Field label="Member since">
                <p className="text-[13.5px] text-ink-900">{formatDate(staff.created_at)}</p>
              </Field>
            </div>
          </Card>

          {staff.role === "doctor" && (
            <Card className="p-space-5">
              <p className="text-eyebrow mb-space-3">Doctor details</p>
              {!staff.doctor_name ? (
                <p className="text-[13px] text-ink-400">Not linked to a doctor record.</p>
              ) : (
                <div className="grid grid-cols-1 gap-space-4 sm:grid-cols-2">
                  <Field label="Department">
                    <p className="text-[13.5px] text-ink-900">{staff.department_name || "—"}</p>
                  </Field>
                  <Field label="Specialization">
                    <p className="text-[13.5px] text-ink-900">{staff.specialization || "—"}</p>
                  </Field>
                  <Field label="Qualification">
                    <p className="text-[13.5px] text-ink-900">{staff.qualification || "—"}</p>
                  </Field>
                  <Field label="Experience">
                    <p className="text-[13.5px] text-ink-900">
                      {staff.years_experience != null ? `${staff.years_experience} years` : "—"}
                    </p>
                  </Field>
                </div>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export default function StaffDetailPage({
  params,
}: {
  params: Promise<{ hospitalId: string; staffId: string }>;
}) {
  const { hospitalId, staffId } = use(params);
  return <StaffDetailView hospitalId={Number(hospitalId)} staffId={Number(staffId)} />;
}
