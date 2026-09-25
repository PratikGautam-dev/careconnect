"use client";

import { use, useState } from "react";
import { ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { useHospitalStaff } from "@/hooks/useHospitalStaff";

function HospitalStaffList({ hospitalId }: { hospitalId: number }) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<"" | "active" | "inactive">("");
  const { staff, hospitalName, error } = useHospitalStaff(hospitalId, search, activeFilter);

  return (
    <div>
      <Link
        href="/admin/users"
        className="mb-space-4 text-brand-600 inline-block text-[13px] font-semibold hover:underline"
      >
        ← All hospitals
      </Link>

      <div className="mb-space-5">
        <h1 className="text-display">{hospitalName || "Staff"}</h1>
        <p className="text-ink-600 text-[13px]">
          Read-only here — edit a person&apos;s role or active status from that hospital&apos;s own
          Staff page.
        </p>
      </div>

      <div className="mb-space-4 gap-space-2 sm:gap-space-3 flex flex-col sm:flex-row sm:items-center">
        <div className="relative w-full flex-1 sm:max-w-[320px]">
          <Search
            size={15}
            className="left-space-3 text-ink-400 absolute top-1/2 -translate-y-1/2"
          />
          <Input
            placeholder="Search by name or email"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="gap-space-2 flex">
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value as typeof activeFilter)}
            className="border-line bg-card px-space-3 text-ink-900 h-10 flex-1 rounded-md border text-[13.5px] sm:flex-none"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <Card className="p-space-4">
        {!staff ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
        ) : staff.length === 0 ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">
            No staff match this filter.
          </p>
        ) : (
          <ul className="divide-line divide-y">
            {staff.map((s) => (
              <li
                key={s.id}
                onClick={() => router.push(`/admin/users/${hospitalId}/${s.id}`)}
                className="gap-space-2 py-space-3 flex cursor-pointer flex-col hover:bg-black/[0.02] sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-ink-900 text-[13.5px] font-semibold">{s.name}</p>
                  <p className="text-ink-600 text-[12px]">{s.email}</p>
                </div>
                <div className="gap-space-3 flex items-center">
                  <span className="bg-brand-50 px-space-2 text-brand-700 rounded-full py-0.5 text-[11px] font-semibold">
                    {s.role_name}
                  </span>
                  <span
                    className={cn(
                      "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
                      s.is_active ? "bg-success-tint text-success" : "text-ink-400 bg-black/[0.05]",
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
