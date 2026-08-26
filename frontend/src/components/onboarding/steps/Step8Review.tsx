import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { FEATURE_LABELS, WizardState } from "../types";
import type { WizardDispatch } from "../useWizardState";

function maskSecret(value: string): string {
  if (!value) return "(not set)";
  if (value.length <= 4) return "••••";
  return "••••••••" + value.slice(-4);
}

const TIER_LABELS: Record<string, string> = {
  tier1: "Tier 1 — this platform",
  tier2: "Tier 2 — external API",
  tier3: "Tier 3 — direct database",
};

function ReviewSection({
  title,
  onEdit,
  children,
}: {
  title: string;
  onEdit: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-space-3 rounded-lg border border-line bg-card p-space-4 shadow-[var(--shadow-sm)]">
      <div className="mb-space-2 flex items-center justify-between">
        <h4 className="text-[13.5px] font-bold text-ink-900">{title}</h4>
        <button type="button" onClick={onEdit} className="text-[12.5px] font-semibold text-brand-600 hover:underline">
          Edit
        </button>
      </div>
      <dl className="grid grid-cols-1 gap-x-space-4 gap-y-space-1 text-[13px] sm:grid-cols-[180px_1fr]">{children}</dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="text-ink-600">{label}</dt>
      <dd className="text-ink-900">{value}</dd>
    </>
  );
}

type Props = {
  state: WizardState;
  dispatch: WizardDispatch;
  onGoToStep: (step: number) => void;
  onSubmit: () => void;
  submitting: boolean;
  submitErrors: string[];
};

export function Step8Review({ state, dispatch, onGoToStep, onSubmit, submitting, submitErrors }: Props) {
  const bookingEnabled = state.enabledFeatures.includes("booking");
  const faqEnabled = state.enabledFeatures.includes("faq");
  const isClinic = state.tenantType === "clinic";
  const namedDepartments = state.departments.filter((d) => d.name.trim() || d.doctors.length > 0);
  const filledTopics = state.topics.filter((t) => t.topicLabel.trim() || t.answerText.trim());

  return (
    <div>
      <p className="text-eyebrow mb-space-2">Step 8 of 9</p>
      <h2 className="text-display mb-space-2">Review &amp; go live</h2>
      <p className="text-body mb-space-4">One last look before this hospital is created and immediately bookable.</p>

      <ReviewSection title="Data connection (Step 0)" onEdit={() => onGoToStep(0)}>
        <Row label="Data connection" value={TIER_LABELS[state.dataTier]} />
        {state.dataTier === "tier2" && (
          <>
            <Row label="API base URL" value={state.apiBaseUrl} />
            <Row label="API key" value={state.apiKey} />
          </>
        )}
      </ReviewSection>

      <ReviewSection title="Access token (Step 4)" onEdit={() => onGoToStep(4)}>
        <Row label="Access token" value={maskSecret(state.accessToken)} />
      </ReviewSection>

      <ReviewSection title="WhatsApp connection (Step 5)" onEdit={() => onGoToStep(5)}>
        <Row label="Phone number ID" value={state.whatsappPhoneNumberId || "(not set)"} />
        <Row label="App secret" value={maskSecret(state.appSecret)} />
      </ReviewSection>

      <ReviewSection title="Patient experience (Step 6)" onEdit={() => onGoToStep(6)}>
        <Row
          label="Enabled for patients"
          value={
            state.enabledFeatures.length ? (
              <ul className="list-disc space-y-0.5 pl-space-4">
                {state.enabledFeatures.map((f) => (
                  <li key={f}>{FEATURE_LABELS[f]}</li>
                ))}
              </ul>
            ) : (
              "(none selected yet)"
            )
          }
        />
      </ReviewSection>

      <ReviewSection title="Hospital details (Step 7)" onEdit={() => onGoToStep(7)}>
        <Row label={isClinic ? "Clinic name" : "Hospital name"} value={state.name || "(not set)"} />
        <Row label="Welcome message" value={state.welcomeMessageText || "(not set)"} />
        {bookingEnabled && (
          <>
            <Row label="Reminder offsets (hours)" value={state.reminderOffsetsHours} />
            <Row label="Reminder template name" value={state.reminderTemplateName || "(not set)"} />
            <Row label="Bookings portal password" value={state.portalPassword ? "Set" : "Not set — can add later"} />
            {isClinic ? (
              <Row label="Doctor" value={state.departments[0]?.doctors[0]?.name || "(not set)"} />
            ) : (
              <Row
                label="Departments & doctors"
                value={
                  namedDepartments.length === 0 ? (
                    "(none added yet)"
                  ) : (
                    <ul className="list-disc space-y-0.5 pl-space-4">
                      {namedDepartments.map((d, i) => (
                        <li key={i}>
                          {d.name || "(unnamed department)"}:{" "}
                          {d.doctors.map((doc) => doc.name || "(unnamed doctor)").join(", ") || "(no doctors)"}
                        </li>
                      ))}
                    </ul>
                  )
                }
              />
            )}
          </>
        )}
        {faqEnabled && (
          <Row
            label="Topics & answers"
            value={
              filledTopics.length === 0 ? (
                "(none added yet)"
              ) : (
                <ul className="list-disc space-y-0.5 pl-space-4">
                  {filledTopics.map((t, i) => (
                    <li key={i}>
                      {t.topicLabel || "(unnamed topic)"}: {t.answerText || "(no answer yet)"}
                    </li>
                  ))}
                </ul>
              )
            }
          />
        )}
      </ReviewSection>

      <p className="mb-space-4 text-[13.5px] font-medium text-brand-700">
        Once you submit, your hospital will be live and bookable through WhatsApp within a few minutes.
      </p>

      {submitErrors.length > 0 && (
        <div className="mb-space-4 rounded-lg border border-error bg-error-tint p-space-4">
          <strong className="mb-space-1 block text-[13.5px] text-error">Please fix the following:</strong>
          <ul className="list-disc space-y-0.5 pl-space-4 text-[13px] text-error">
            {submitErrors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <Field label="Admin secret" htmlFor="admin_secret" required>
        <Input
          id="admin_secret"
          type="password"
          value={state.adminSecret}
          onChange={(e) => dispatch({ type: "set", field: "adminSecret", value: e.target.value })}
        />
      </Field>

      <Button onClick={onSubmit} disabled={submitting} size="lg">
        {submitting ? "Creating hospital…" : "Create hospital"}
      </Button>
    </div>
  );
}
