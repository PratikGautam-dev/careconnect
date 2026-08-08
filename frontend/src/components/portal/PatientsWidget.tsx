import Link from "next/link";
import { Card } from "@/components/ui/Card";

type Patient = { id: number; phone: string; name: string | null; last_visit: string | null; visit_count: number };

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function PatientsWidget({ patients }: { patients: Patient[] }) {
  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label font-bold text-ink-900">Patients</h3>
        <Link href="/portal/patients" className="text-[12.5px] font-semibold text-brand-600 hover:underline">
          View all patients →
        </Link>
      </div>
      {patients.length === 0 ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">No patients yet.</p>
      ) : (
        <ul className="divide-y divide-line">
          {patients.map((p) => (
            <li key={p.id}>
              <Link
                href={`/portal/patients/${p.id}`}
                className="flex items-center justify-between py-space-2 hover:opacity-80"
              >
                <div>
                  <p className="text-[13.5px] font-semibold text-ink-900">{p.name || p.phone}</p>
                  {p.name && <p className="text-[12px] text-ink-600">{p.phone}</p>}
                </div>
                <span className="text-[12px] whitespace-nowrap text-ink-400">Last visit: {formatDate(p.last_visit)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
