import { Plus } from "lucide-react";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { WizardState } from "../types";
import type { WizardDispatch } from "../useWizardState";
import { DepartmentCard } from "./DepartmentCard";
import { TopicCard } from "./TopicCard";

type Props = { state: WizardState; dispatch: WizardDispatch; error?: string };

export function Step7HospitalDetails({ state, dispatch, error }: Props) {
  const bookingEnabled = state.enabledFeatures.includes("booking");
  const faqEnabled = state.enabledFeatures.includes("faq");

  const parts = [];
  if (bookingEnabled) parts.push("departments & doctors");
  if (faqEnabled) parts.push("topics & answers");
  const heading = parts.length ? `Add ${parts.join(" and ")}` : "Hospital details";
  const desc = bookingEnabled
    ? "This drives real slot generation — patients only see times a doctor is actually working."
    : faqEnabled
      ? "Each topic becomes a tappable option — patients get an instant answer, no scheduling involved."
      : "Basic details for this hospital.";

  return (
    <div>
      <p className="text-eyebrow mb-space-2">Step 7 of 9</p>
      <h2 className="text-display mb-space-2">{heading}</h2>
      <p className="text-body mb-space-4">{desc}</p>

      <Field label="Hospital name" htmlFor="hospital_name" required>
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
          <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
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
            label="Bookings portal password (optional)"
            htmlFor="portal_password"
            hint="Your staff can use this to log into a simple dashboard at /portal/login and see every appointment booked through WhatsApp. You can set or change it anytime after onboarding too."
          >
            <Input
              id="portal_password"
              type="password"
              placeholder="Leave blank to set this later"
              value={state.portalPassword}
              onChange={(e) => dispatch({ type: "set", field: "portalPassword", value: e.target.value })}
            />
          </Field>

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
  if (!state.name.trim()) return "Hospital name is required.";
  if (state.enabledFeatures.includes("booking")) {
    const doctorCount = state.departments.reduce((n, d) => n + d.doctors.length, 0);
    if (doctorCount === 0) return "Booking is enabled, so at least one department with at least one doctor is required.";
  }
  if (state.enabledFeatures.includes("faq")) {
    const topicCount = state.topics.filter((t) => t.topicLabel.trim() && t.answerText.trim()).length;
    if (topicCount === 0) return "FAQ / Information Bot is enabled, so at least one topic with a label and an answer is required.";
  }
  return null;
}
