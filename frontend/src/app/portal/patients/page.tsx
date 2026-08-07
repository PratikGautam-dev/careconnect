"use client";

import { useCallback, useEffect, useState } from "react";
import { Search, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { PortalSidebar } from "@/components/portal/PortalSidebar";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { portalFetch } from "@/lib/portalAuth";

type Patient = { id: number; phone: string; name: string | null; last_visit: string | null; visit_count: number };

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function PortalPatientsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const [patients, setPatients] = useState<Patient[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(
    async (query: string) => {
      const result = await portalFetch(`/api/portal/patients?search=${encodeURIComponent(query)}`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        else setError(result.error);
        return;
      }
      setPatients((result.data as { patients: Patient[] }).patients);
    },
    [router],
  );

  useEffect(() => {
    if (ready) load(search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, load]);

  useEffect(() => {
    if (!ready) return;
    const t = setTimeout(() => load(search), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      <PortalSidebar hospital={hospital} active="patients" />
      <main className="flex-1 overflow-y-auto p-space-6">
        <h1 className="text-display mb-space-5">Patients</h1>
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        <div className="mb-space-4 max-w-[360px]">
          <div className="relative">
            <Search size={15} className="absolute top-1/2 left-space-3 -translate-y-1/2 text-ink-400" />
            <Input
              placeholder="Search by name or phone"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        <Card className="p-space-4">
          {!patients ? (
            <p className="text-[13px] text-ink-400">Loading…</p>
          ) : patients.length === 0 ? (
            <div className="py-space-6 text-center">
              <UserRound size={28} className="mx-auto mb-space-2 text-ink-300" />
              <p className="text-[13px] text-ink-400">
                {search ? "No patients match that search." : "No patients yet — they appear here after a first booking."}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="border-b border-line text-[11.5px] text-ink-400 uppercase">
                    <th className="pb-space-2 font-semibold">Name</th>
                    <th className="pb-space-2 font-semibold">Phone</th>
                    <th className="pb-space-2 font-semibold">Last visit</th>
                    <th className="pb-space-2 font-semibold">Visits</th>
                  </tr>
                </thead>
                <tbody>
                  {patients.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => router.push(`/portal/patients/${p.id}`)}
                      className="cursor-pointer border-b border-line last:border-0 hover:bg-black/[0.02]"
                    >
                      <td className="py-space-2 font-semibold text-ink-900">
                        <Link href={`/portal/patients/${p.id}`} className="hover:underline">
                          {p.name || "—"}
                        </Link>
                      </td>
                      <td className="py-space-2 text-ink-600">{p.phone}</td>
                      <td className="py-space-2 text-ink-600">{formatDate(p.last_visit)}</td>
                      <td className="py-space-2 tabular-nums text-ink-600">{p.visit_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
