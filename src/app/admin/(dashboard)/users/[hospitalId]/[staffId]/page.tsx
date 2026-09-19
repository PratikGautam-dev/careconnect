"use client";

import { use } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import { useStaffDetail } from "@/hooks/useStaffDetail";

function StaffDetailView({ hospitalId, staffId }: { hospitalId: number; staffId: number }) {
  const { staff, error } = useStaffDetail(staffId);

  return (
    <div>
      <Link
        href={`/admin/users/${hospitalId}`}
        className="mb-space-4 text-brand-600 inline-block text-[13px] font-semibold hover:underline"
      >
        ← Back to staff list
      </Link>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      {!staff ? (
        <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
      ) : (
        <>
          <div className="mb-space-5 gap-space-3 flex flex-col sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-eyebrow mb-space-1">{staff.hospital_name}</p>
              <h1 className="text-display">{staff.name}</h1>
            </div>
            <div className="gap-space-2 flex items-center">
              <span className="bg-brand-50 px-space-2 text-brand-700 rounded-full py-0.5 text-[11px] font-semibold">
                {staff.role_name}
              </span>
              <span
                className={cn(
                  "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
                  staff.is_active ? "bg-success-tint text-success" : "text-ink-400 bg-black/[0.05]",
                )}
              >
                {staff.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          </div>

          <Card className="mb-space-4 p-space-5">
            <div className="gap-space-4 grid grid-cols-1 sm:grid-cols-2">
              <Field label="Email">
                <p className="text-ink-900 text-[13.5px]">{staff.email}</p>
              </Field>
              <Field label="Member since">
                <p className="text-ink-900 text-[13.5px]">{formatDate(staff.created_at)}</p>
              </Field>
            </div>
          </Card>

          {staff.is_doctor_role && (
            <Card className="p-space-5">
              <p className="text-eyebrow mb-space-3">Doctor details</p>
              {!staff.doctor_name ? (
                <p className="text-ink-400 text-[13px]">Not linked to a doctor record.</p>
              ) : (
                <div className="gap-space-4 grid grid-cols-1 sm:grid-cols-2">
                  <Field label="Department">
                    <p className="text-ink-900 text-[13.5px]">{staff.department_name || "—"}</p>
                  </Field>
                  <Field label="Specialization">
                    <p className="text-ink-900 text-[13.5px]">{staff.specialization || "—"}</p>
                  </Field>
                  <Field label="Qualification">
                    <p className="text-ink-900 text-[13.5px]">{staff.qualification || "—"}</p>
                  </Field>
                  <Field label="Experience">
                    <p className="text-ink-900 text-[13.5px]">
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
