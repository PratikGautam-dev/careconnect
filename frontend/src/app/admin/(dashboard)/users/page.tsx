"use client";

import { useCallback, useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { adminFetch } from "@/lib/adminAuth";

type StaffRow = {
  id: number;
  name: string;
  email: string;
  role: "admin" | "receptionist" | "doctor";
  hospital_id: number;
  hospital_name: string;
  is_active: boolean;
};

const ROLE_LABELS: Record<string, string> = { admin: "Admin", receptionist: "Receptionist", doctor: "Doctor" };

function UsersList() {
  const [staff, setStaff] = useState<StaffRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<"" | "admin" | "receptionist" | "doctor">("");
  const [activeFilter, setActiveFilter] = useState<"" | "active" | "inactive">("");

  const load = useCallback(async () => {
    const query = new URLSearchParams();
    if (roleFilter) query.set("role", roleFilter);
    if (activeFilter) query.set("is_active", activeFilter === "active" ? "true" : "false");
    const result = await adminFetch(`/api/admin/staff-users?${query.toString()}`);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
      return;
    }
    setStaff((result.data as { staff: StaffRow[] }).staff);
  }, [roleFilter, activeFilter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-[1000px]">
      <div className="mb-space-5 flex items-center justify-between">
        <div>
          <p className="text-eyebrow mb-space-1">Platform admin</p>
          <h1 className="text-display">Users</h1>
          <p className="text-[13px] text-ink-600">
            Every staff account across every hospital. Read-only here — edit a person&apos;s role or
            active status from that hospital&apos;s own Staff page.
          </p>
        </div>
        <div className="flex items-center gap-space-2">
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as typeof roleFilter)}
            className="h-10 rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900"
          >
            <option value="">All roles</option>
            <option value="admin">Admin</option>
            <option value="receptionist">Receptionist</option>
            <option value="doctor">Doctor</option>
          </select>
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value as typeof activeFilter)}
            className="h-10 rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900"
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
              <li key={s.id} className="flex items-center justify-between py-space-3">
                <div>
                  <p className="text-[13.5px] font-semibold text-ink-900">{s.name}</p>
                  <p className="text-[12px] text-ink-600">
                    {s.email} · {s.hospital_name}
                  </p>
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
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export default function UsersPage() {
  return <UsersList />;
}
