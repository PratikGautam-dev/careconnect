import {
  Calendar,
  CalendarClock,
  CalendarX,
  FlaskConical,
  HelpCircle,
  IdCard,
  Info,
  Languages,
  ListChecks,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { FEATURE_LABELS, FeatureKey, WizardState } from "../types";
import type { WizardDispatch } from "../useWizardState";

const FEATURE_ICONS: Record<FeatureKey, typeof Calendar> = {
  book_doctor_appointment: Calendar,
  tests_diagnostics: FlaskConical,
  reschedule: CalendarClock,
  cancel: CalendarX,
  view_appointments: ListChecks,
  reports_prescriptions: IdCard,
  manage_patients: Users,
  consent_privacy: ShieldCheck,
  manage_language: Languages,
  hospital_info: Info,
  reception_handoff: UserRound,
  faq: HelpCircle,
};

const FEATURE_DESCRIPTIONS: Record<FeatureKey, string> = {
  book_doctor_appointment: "Patients pick a department, doctor, and time slot for a doctor consultation.",
  tests_diagnostics: "Patients book a diagnostic test, lab test, or daycare/procedure -- instantly or by request, depending on how you configure it.",
  reschedule: "Move an existing booking to a new time.",
  cancel: "Cancel an existing booking.",
  view_appointments: "See a list of upcoming bookings.",
  reports_prescriptions: "Patients view their prescriptions, lab reports, and diagnostic reports, or book a report review.",
  manage_patients: "One phone can link up to 5 family members, each with their own profile.",
  consent_privacy: "Privacy notice, consent status, and a marketing-messages opt-in/out.",
  manage_language: "Patients can switch their conversation language at any time from the main menu.",
  hospital_info: "Hours, location, and general info.",
  reception_handoff: "Hand off to a human -- queues into the staff portal's Messages inbox.",
  faq: "Patients pick a topic (hours, pricing...) and get an instant configured answer.",
};

const FEATURE_ORDER = Object.keys(FEATURE_LABELS) as FeatureKey[];

type Props = { state: WizardState; dispatch: WizardDispatch; error?: string };

export function Step6PatientExperience({ state, dispatch, error }: Props) {
  return (
    <div>
      <p className="text-eyebrow mb-space-2">Step 6 of 9</p>
      <h2 className="text-display mb-space-2">What should patients be able to do on WhatsApp?</h2>
      <p className="text-body mb-space-4">
        Select every capability this hospital wants to offer — patients only ever see the ones you turn on here.
        You can change this later.
      </p>

      <div className="grid grid-cols-1 gap-space-3 md:grid-cols-2 lg:grid-cols-3">
        {FEATURE_ORDER.map((key) => {
          const Icon = FEATURE_ICONS[key];
          const selected = state.enabledFeatures.includes(key);
          return (
            <label
              key={key}
              className={cn(
                "flex cursor-pointer flex-col rounded-lg border bg-card p-space-4 shadow-[var(--shadow-sm)] transition-all duration-150 ease-(--ease-standard)",
                "hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]",
                selected ? "border-brand-400 ring-2 ring-brand-100" : "border-line",
              )}
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={selected}
                onChange={() => dispatch({ type: "toggleFeature", key })}
              />
              <div className="mb-space-2 flex items-start justify-between">
                <div
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-[10px]",
                    selected ? "bg-brand-600 text-white" : "bg-brand-50 text-brand-600",
                  )}
                >
                  <Icon size={16} strokeWidth={2} />
                </div>
              </div>
              <h3 className="mb-space-1 text-[14.5px] font-bold text-ink-900">{FEATURE_LABELS[key]}</h3>
              <p className="text-[12.5px] leading-relaxed text-ink-600">{FEATURE_DESCRIPTIONS[key]}</p>
            </label>
          );
        })}
      </div>
      {error && <p className="mt-space-3 text-[12.5px] font-medium text-error">{error}</p>}
    </div>
  );
}

export function validateStep6(state: WizardState): string | null {
  if (state.enabledFeatures.length === 0) return "Select at least one capability for patients to use.";
  return null;
}
