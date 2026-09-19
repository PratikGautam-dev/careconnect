import Image from "next/image";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { WizardState } from "../types";
import type { WizardDispatch } from "../useWizardState";

type Props = { state: WizardState; dispatch: WizardDispatch; error?: string };

export function Step5PhoneSecret({ state, dispatch, error }: Props) {
  return (
    <div>
      <p className="text-eyebrow mb-space-2">Step 5 of 9</p>
      <h2 className="text-display mb-space-2">Paste your remaining credentials</h2>
      <p className="text-body mb-space-4">Both of these come from the app created in Step 2.</p>

      <div className="mb-space-4 gap-space-4 grid grid-cols-1 lg:grid-cols-2">
        <div className="gap-space-4 border-line bg-paper p-space-4 flex rounded-lg border">
          <div className="bg-brand-600 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px] font-bold text-white">
            1
          </div>
          <ol className="space-y-space-2 pl-space-4 text-ink-600 marker:text-brand-600 list-decimal text-[14px] leading-relaxed marker:font-semibold">
            <li>
              Go back to your app&apos;s <strong>WhatsApp → API Setup</strong> page (from Step 2).
            </li>
            <li>
              Copy the <strong>Phone Number ID</strong> shown there and paste it below.
            </li>
            <li>
              Go to your app&apos;s <strong>Settings → Basic</strong> → click <strong>Show</strong>{" "}
              next to <strong>App Secret</strong> → copy and paste it below.
            </li>
          </ol>
        </div>

        <div className="border-line bg-paper relative min-h-55 overflow-hidden rounded-xl border shadow-sm">
          <Image
            src="/meta-credentials.png"
            alt="Credentials walkthrough: go to WhatsApp API Setup, copy the Phone Number ID, then go to Settings → Basic → Show next to App Secret and copy it, pasting both into the fields below."
            fill
            className="p-space-2 object-contain"
            priority
          />
        </div>
      </div>

      <Field
        label="WhatsApp phone_number_id"
        htmlFor="whatsapp_phone_number_id"
        required
        error={error}
      >
        <Input
          id="whatsapp_phone_number_id"
          value={state.whatsappPhoneNumberId}
          invalid={!!error}
          onChange={(e) =>
            dispatch({ type: "set", field: "whatsappPhoneNumberId", value: e.target.value })
          }
        />
      </Field>
      <Field label="App secret" htmlFor="app_secret">
        <Input
          id="app_secret"
          value={state.appSecret}
          onChange={(e) => dispatch({ type: "set", field: "appSecret", value: e.target.value })}
        />
      </Field>
    </div>
  );
}

export function validateStep5(state: WizardState): string | null {
  if (!state.whatsappPhoneNumberId.trim()) return "WhatsApp phone_number_id is required.";
  return null;
}
