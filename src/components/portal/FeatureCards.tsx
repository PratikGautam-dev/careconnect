import {
  Calendar,
  CalendarClock,
  CalendarX,
  FlaskConical,
  HelpCircle,
  Info,
  Languages,
  ListChecks,
  UserRound,
} from "lucide-react";
import { Card } from "@/components/ui/Card";

const FEATURE_META: Record<string, { label: string; Icon: typeof Calendar }> = {
  book_doctor_appointment: { label: "Book Doctor Appointment", Icon: Calendar },
  tests_diagnostics: { label: "Tests & Diagnostics", Icon: FlaskConical },
  reschedule: { label: "Reschedule Appointment", Icon: CalendarClock },
  cancel: { label: "Cancel Appointment", Icon: CalendarX },
  view_appointments: { label: "View Appointments", Icon: ListChecks },
  manage_language: { label: "Manage Language", Icon: Languages },
  hospital_info: { label: "Hospital Information", Icon: Info },
  reception_handoff: { label: "Talk to Reception", Icon: UserRound },
  faq: { label: "FAQ / Information", Icon: HelpCircle },
};

/** Display-only -- shows which patient-facing WhatsApp capabilities are
 * currently on for this hospital. Not clickable; enabling/disabling features
 * happens at onboarding/edit-tenant time, not from the dashboard. */
export function FeatureCards({ enabledFeatures }: { enabledFeatures: string[] }) {
  const known = enabledFeatures.filter((f) => FEATURE_META[f]);
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-3 text-ink-900 font-bold">What we provide</h3>
      {known.length === 0 ? (
        <p className="py-space-2 text-ink-400 text-center text-[13px]">
          No patient-facing features enabled yet.
        </p>
      ) : (
        <div className="gap-space-2 flex flex-wrap">
          {known.map((key) => {
            const { label, Icon } = FEATURE_META[key];
            return (
              <span
                key={key}
                className="gap-space-2 border-line bg-paper px-space-3 py-space-2 text-ink-700 flex items-center rounded-md border text-[12.5px] font-semibold"
              >
                <Icon size={14} strokeWidth={2} className="text-brand-600" />
                {label}
              </span>
            );
          })}
        </div>
      )}
    </Card>
  );
}
