import { Building2, Plus, Stethoscope } from "lucide-react";
import { cn } from "@/lib/cn";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { TenantType, WizardState } from "../types";
import type { WizardDispatch } from "../useWizardState";
import { DepartmentCard } from "./DepartmentCard";
import { DoctorCard } from "./DoctorCard";
import { TopicCard } from "./TopicCard";

type Props = { state: WizardState; dispatch: WizardDispatch; error?: string };

const TENANT_TYPE_OPTIONS: { value: TenantType; label: string; description: string; icon: typeof Building2 }[] = [
  { value: "hospital", label: "Hospital", description: "Multiple departments and doctors.", icon: Building2 },
  { value: "clinic", label: "Clinic", description: "A single doctor's practice.", icon: Stethoscope },
];

export function Step7HospitalDetails({ state, dispatch, error }: Props) {
  const bookingEnabled = state.enabledFeatures.includes("booking");
  const faqEnabled = state.enabledFeatures.includes("faq");
  const isClinic = state.tenantType === "clinic";

  const parts = [];
  if (bookingEnabled) parts.push(isClinic ? "your doctor's details" : "departments & doctors");
  if (faqEnabled) parts.push("topics & answers");
  const heading = parts.length ? `Add ${parts.join(" and ")}` : isClinic ? "Clinic details" : "Hospital details";
  const desc = bookingEnabled
    ? "This drives real slot generation — patients only see times a doctor is actually working."
    : faqEnabled
      ? "Each topic becomes a tappable option — patients get an instant answer, no scheduling involved."
      : isClinic
        ? "Basic details for this clinic."
        : "Basic details for this hospital.";

  return (
    <div>
      <p className="text-eyebrow mb-space-2">Step 7 of 9</p>
      <h2 className="text-display mb-space-2">{heading}</h2>
      <p className="text-body mb-space-4">{desc}</p>

      <Field label="Type of practice">
        <div className="grid grid-cols-1 gap-space-3 md:grid-cols-2">
          {TENANT_TYPE_OPTIONS.map(({ value, label, description, icon: Icon }) => {
            const selected = state.tenantType === value;
            return (
              <label
                key={value}
                className={cn(
                  "flex cursor-pointer items-start gap-space-3 rounded-lg border bg-card p-space-4 shadow-[var(--shadow-sm)] transition-all duration-150 ease-(--ease-standard)",
                  "hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]",
                  selected ? "border-brand-400 ring-2 ring-brand-100" : "border-line",
                )}
              >
                <input
                  type="radio"
                  name="tenant_type"
                  className="sr-only"
                  checked={selected}
                  onChange={() => dispatch({ type: "setTenantType", value })}
                />
                <div
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px]",
                    selected ? "bg-brand-600 text-white" : "bg-brand-50 text-brand-600",
                  )}
                >
                  <Icon size={16} strokeWidth={2} />
                </div>
                <div>
                  <h3 className="mb-space-1 text-[14.5px] font-bold text-ink-900">{label}</h3>
                  <p className="text-[12.5px] leading-relaxed text-ink-600">{description}</p>
                </div>
              </label>
            );
          })}
        </div>
      </Field>

      <Field label={isClinic ? "Clinic name" : "Hospital name"} htmlFor="hospital_name" required>
        <Input
          id="hospital_name"
          value={state.name}
          onChange={(e) => dispatch({ type: "set", field: "name", value: e.target.value })}
        />
      </Field>
      <Field label="Welcome message text" htmlFor="welcome_message">
        <Textarea
          id="welcome_message"
          rows={2}
          placeholder="Hi! Welcome to [Hospital Name]. How can we help you today?"
          value={state.welcomeMessageText}
          onChange={(e) => dispatch({ type: "set", field: "welcomeMessageText", value: e.target.value })}
        />
      </Field>

      {bookingEnabled && (
        <>
          <div className="grid grid-cols-1 gap-x-space-4 md:grid-cols-2">
            <Field
              label="Reminder offsets (comma-separated hours)"
              htmlFor="reminder_offsets"
              hint="e.g. 24,1 sends a reminder one day before and one hour before."
            >
              <Input
                id="reminder_offsets"
                placeholder="24,1"
                value={state.reminderOffsetsHours}
                onChange={(e) => dispatch({ type: "set", field: "reminderOffsetsHours", value: e.target.value })}
              />
            </Field>
            <Field
              label="Reminder template name"
              htmlFor="reminder_template"
              hint="Must match a message template approved in Meta's WhatsApp Manager."
            >
              <Input
                id="reminder_template"
                value={state.reminderTemplateName}
                onChange={(e) => dispatch({ type: "set", field: "reminderTemplateName", value: e.target.value })}
              />
            </Field>
          </div>

          <Field
            label="Bookings portal password"
            htmlFor="portal_password"
            required
            hint="Your staff will use this to log into the bookings dashboard and see every appointment booked through WhatsApp. You can change it anytime after onboarding too."
          >
            <Input
              id="portal_password"
              type="password"
              required
              value={state.portalPassword}
              onChange={(e) => dispatch({ type: "set", field: "portalPassword", value: e.target.value })}
            />
          </Field>

          {isClinic ? (
            <>
              <p className="text-label mb-space-2 mt-space-5">Doctor details</p>
              {state.departments[0]?.doctors[0] && (
                <DoctorCard
                  deptIndex={0}
                  docIndex={0}
                  doctor={state.departments[0].doctors[0]}
                  dispatch={dispatch}
                  hideActions
                />
              )}
            </>
          ) : (
            <>
              <p className="text-label mb-space-2 mt-space-5">Departments &amp; doctors</p>
              {state.departments.map((dept, i) => (
                <DepartmentCard key={i} deptIndex={i} department={dept} dispatch={dispatch} />
              ))}
              <button
                type="button"
                onClick={() => dispatch({ type: "addDepartment" })}
                className="flex items-center gap-1 text-[13px] font-semibold text-brand-600 hover:underline"
              >
                <Plus size={14} /> Add department
              </button>
            </>
          )}
        </>
      )}

      {faqEnabled && (
        <>
          <p className="text-label mb-space-2 mt-space-5">Topics &amp; answers</p>
          <p className="text-hint mb-space-3">
            Each topic becomes an option patients tap on WhatsApp — e.g. &quot;Hours,&quot; &quot;Location,&quot;
            &quot;Pricing.&quot; Keep answers short and clear.
          </p>
          {state.topics.map((topic, i) => (
            <TopicCard key={i} topicIndex={i} topic={topic} dispatch={dispatch} />
          ))}
          <button
            type="button"
            onClick={() => dispatch({ type: "addTopic" })}
            className="flex items-center gap-1 text-[13px] font-semibold text-brand-600 hover:underline"
          >
            <Plus size={14} /> Add topic
          </button>
        </>
      )}

      {error && <p className="mt-space-4 text-[12.5px] font-medium text-error">{error}</p>}
    </div>
  );
}

export function validateStep7(state: WizardState): string | null {
  const isClinic = state.tenantType === "clinic";
  if (!state.name.trim()) return isClinic ? "Clinic name is required." : "Hospital name is required.";
  if (state.enabledFeatures.includes("booking")) {
    const doctorCount = state.departments.reduce((n, d) => n + d.doctors.length, 0);
    if (doctorCount === 0) {
      return isClinic
        ? "Booking is enabled, so your doctor's details are required."
        : "Booking is enabled, so at least one department with at least one doctor is required.";
    }
    if (!state.portalPassword.trim()) return "A bookings portal password is required.";
  }
  if (state.enabledFeatures.includes("faq")) {
    const topicCount = state.topics.filter((t) => t.topicLabel.trim() && t.answerText.trim()).length;
    if (topicCount === 0) return "FAQ / Information Bot is enabled, so at least one topic with a label and an answer is required.";
  }
  return null;
}
