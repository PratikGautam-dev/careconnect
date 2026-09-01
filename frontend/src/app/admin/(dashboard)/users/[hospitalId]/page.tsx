"use client";

import { use, useState } from "react";
import { ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { useHospitalStaff } from "@/hooks/useHospitalStaff";

const ROLE_LABELS: Record<string, string> = { admin: "Admin", receptionist: "Receptionist", doctor: "Doctor" };

function HospitalStaffList({ hospitalId }: { hospitalId: number }) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<"" | "admin" | "receptionist" | "doctor">("");
  const [activeFilter, setActiveFilter] = useState<"" | "active" | "inactive">("");
  const { staff, hospitalName, error } = useHospitalStaff(hospitalId, search, roleFilter, activeFilter);

  return (
    <div>
      <Link href="/admin/users" className="mb-space-4 inline-block text-[13px] font-semibold text-brand-600 hover:underline">
        ← All hospitals
      </Link>

      <div className="mb-space-5">
        <p className="text-eyebrow mb-space-1">Platform admin</p>
        <h1 className="text-display">{hospitalName || "Staff"}</h1>
        <p className="text-[13px] text-ink-600">
          Read-only here — edit a person&apos;s role or active status from that hospital&apos;s own Staff page.
        </p>
      </div>

      <div className="mb-space-4 flex flex-col gap-space-2 sm:flex-row sm:items-center sm:gap-space-3">
        <div className="relative w-full flex-1 sm:max-w-[320px]">
          <Search size={15} className="absolute top-1/2 left-space-3 -translate-y-1/2 text-ink-400" />
          <Input
            placeholder="Search by name or email"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-space-2">
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as typeof roleFilter)}
            className="h-10 flex-1 rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900 sm:flex-none"
          >
            <option value="">All roles</option>
            <option value="admin">Admin</option>
            <option value="receptionist">Receptionist</option>
            <option value="doctor">Doctor</option>
          </select>
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value as typeof activeFilter)}
            className="h-10 flex-1 rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900 sm:flex-none"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      <Card className="p-space-4">
        {!staff ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
        ) : staff.length === 0 ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">No staff match this filter.</p>
        ) : (
          <ul className="divide-y divide-line">
            {staff.map((s) => (
              <li
                key={s.id}
                onClick={() => router.push(`/admin/users/${hospitalId}/${s.id}`)}
                className="flex cursor-pointer flex-col gap-space-2 py-space-3 hover:bg-black/[0.02] sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-[13.5px] font-semibold text-ink-900">{s.name}</p>
                  <p className="text-[12px] text-ink-600">{s.email}</p>
                </div>
                <div className="flex items-center gap-space-3">
                  <span className="rounded-full bg-brand-50 px-space-2 py-0.5 text-[11px] font-semibold text-brand-700">
                    {ROLE_LABELS[s.role] || s.role}
                  </span>
                  <span
                    className={cn(
                      "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                      s.is_active ? "bg-success-tint text-success" : "bg-black/[0.05] text-ink-400",
                    )}
                  >
                    {s.is_active ? "Active" : "Inactive"}
                  </span>
                  <ChevronRight size={15} className="text-ink-300" />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export default function HospitalUsersPage({ params }: { params: Promise<{ hospitalId: string }> }) {
  const { hospitalId } = use(params);
  return <HospitalStaffList hospitalId={Number(hospitalId)} />;
}
