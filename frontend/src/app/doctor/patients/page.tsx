"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { DoctorShell } from "@/components/doctor/DoctorShell";
import { useDoctorGuard } from "@/components/doctor/useDoctorGuard";
import { formatDate } from "@/lib/formatDate";
import { staffFetch } from "@/lib/staffAuth";

type Patient = {
  id: number;
  phone: string;
  name: string | null;
  patient_display_id: string | null;
  mrn: string | null;
  last_visit: string | null;
  visit_count: number;
  visited_count: number;
};

export default function DoctorPatientsPage() {
  const { doctor, ready } = useDoctorGuard();
  const router = useRouter();
  const [patients, setPatients] = useState<Patient[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const load = useCallback(async () => {
    const result = await staffFetch("/api/doctor/patients");
    if (!result.ok) {
      if (result.unauthorized) router.push("/doctor/login");
      else setError(result.error);
      return;
    }
    setPatients((result.data as { patients: Patient[] }).patients);
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  const filtered = useMemo(() => {
    if (!patients) return [];
    const q = searchQuery.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter(
      (p) =>
        p.phone.toLowerCase().includes(q)
        || (p.name || "").toLowerCase().includes(q)
        || (p.patient_display_id || "").toLowerCase().includes(q)
        || (p.mrn || "").toLowerCase().includes(q),
    );
  }, [patients, searchQuery]);

  if (!ready) return null;

  return (
    <DoctorShell doctor={doctor} active="patients">
      <h1 className="text-display mb-space-5">My patients</h1>
      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      <div className="relative mb-space-4 max-w-md">
        <Search size={15} className="pointer-events-none absolute left-space-3 top-1/2 -translate-y-1/2 text-ink-400" />
        <Input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search name, phone, patient ID, or MRN…"
          className="pl-9"
        />
      </div>

      {!patients ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : filtered.length === 0 ? (
        <Card className="p-space-6 text-center">
          <p className="text-body">{patients.length === 0 ? "No patients yet." : "No patients match."}</p>
        </Card>
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="border-b border-line text-left text-label text-ink-400">
                <th className="px-space-4 py-space-3 font-medium">Patient</th>
                <th className="px-space-4 py-space-3 font-medium">Phone</th>
                <th className="px-space-4 py-space-3 font-medium">Patient ID</th>
                <th className="px-space-4 py-space-3 font-medium">Last visit (with me)</th>
                <th className="px-space-4 py-space-3 font-medium">Visits</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr key={p.id} className="border-b border-line last:border-0">
                  <td className="px-space-4 py-space-3 font-semibold text-ink-900">{p.name || "—"}</td>
                  <td className="px-space-4 py-space-3 tabular-nums text-ink-600">{p.phone}</td>
                  <td className="px-space-4 py-space-3 text-ink-600">{p.patient_display_id || "—"}</td>
                  <td className="px-space-4 py-space-3 text-ink-600">{formatDate(p.last_visit)}</td>
                  <td className="px-space-4 py-space-3 tabular-nums text-ink-600">
                    {p.visited_count}/{p.visit_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </DoctorShell>
  );
}
