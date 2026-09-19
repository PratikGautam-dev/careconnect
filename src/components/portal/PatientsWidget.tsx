import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { formatDate } from "@/lib/formatDate";

type Patient = {
  id: number;
  phone: string;
  name: string | null;
  last_visit: string | null;
  visit_count: number;
};

export function PatientsWidget({ patients }: { patients: Patient[] }) {
  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label text-ink-900 font-bold">Patients</h3>
        <Link
          href="/portal/patients"
          className="text-brand-600 text-[12.5px] font-semibold hover:underline"
        >
          View all patients →
        </Link>
      </div>
      {patients.length === 0 ? (
        <p className="py-space-4 text-ink-400 text-center text-[13px]">No patients yet.</p>
      ) : (
        <ul className="divide-line divide-y">
          {patients.map((p) => (
            <li key={p.id}>
              <Link
                href={`/portal/patients/${p.id}`}
                className="py-space-2 flex items-center justify-between hover:opacity-80"
              >
                <div>
                  <p className="text-ink-900 text-[13.5px] font-semibold">{p.name || p.phone}</p>
                  {p.name && <p className="text-ink-600 text-[12px]">{p.phone}</p>}
                </div>
                <span className="text-ink-400 text-[12px] whitespace-nowrap">
                  Last visit: {formatDate(p.last_visit)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
