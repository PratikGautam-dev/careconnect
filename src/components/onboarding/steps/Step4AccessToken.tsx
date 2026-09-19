import Image from "next/image";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { WizardState } from "../types";
import type { WizardDispatch } from "../useWizardState";

type Props = { state: WizardState; dispatch: WizardDispatch };

export function Step4AccessToken({ state, dispatch }: Props) {
  return (
    <div>
      <p className="text-eyebrow mb-space-2">Step 4 of 9</p>
      <h2 className="text-display mb-space-2">Generate a permanent access token</h2>
      <p className="text-body mb-space-4">This avoids the default token expiring every 24 hours.</p>

      <div className="mb-space-4 grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <div className="flex gap-space-4 rounded-lg border border-line bg-paper p-space-4">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-[13px] font-bold text-white">
            1
          </div>
          <ol className="list-decimal space-y-space-2 pl-space-4 text-[14px] leading-relaxed text-ink-600 marker:font-semibold marker:text-brand-600">
            <li>
              Go to <strong>business.facebook.com/settings</strong> → <strong>Users</strong> →{" "}
              <strong>System Users</strong> → <strong>Add</strong>.
            </li>
            <li>
              Give it a name (e.g. &quot;[Hospital Name] Bot&quot;) and set its role to <strong>Admin</strong>.
            </li>
            <li>
              Click <strong>Assign Assets</strong> → <strong>Apps</strong> tab → select the app you created in
              Step 2 → give it <strong>Full Control</strong>.
            </li>
            <li>
              Click <strong>Generate New Token</strong> → select that same app → under permissions, check{" "}
              <strong>whatsapp_business_messaging</strong> and <strong>whatsapp_business_management</strong> → set
              expiration to <strong>Never</strong> → <strong>Generate Token</strong>.
            </li>
            <li>
              <strong>Copy the token immediately and paste it below</strong> — Meta only shows it once; if you
              lose it, you&apos;ll need to generate a new one.
            </li>
          </ol>
        </div>

        <div className="relative min-h-55 overflow-hidden rounded-xl border border-line bg-paper shadow-sm">
          <Image
            src="/meta-access-token.png"
            alt="Generate token walkthrough: click Generate token, select the same app, check both WhatsApp permissions, set expiration to Never, then copy the token immediately."
            fill
            className="object-contain p-space-2"
            priority
          />
        </div>
      </div>

      <Field label="Access token" htmlFor="access_token" hint="You'll find this on the System User's &quot;Generate token&quot; screen.">
        <Input
          id="access_token"
          placeholder="EAAxxxxxxxxxxxxxxxxxxxxxxx"
          value={state.accessToken}
          onChange={(e) => dispatch({ type: "set", field: "accessToken", value: e.target.value })}
        />
      </Field>
    </div>
  );
}
