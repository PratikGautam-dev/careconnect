"use client";

import { useState } from "react";
import { Bell, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";

// Purely a design preview -- no notification/email infra exists in the
// backend yet (confirmed against the codebase), so none of this actually
// sends anything. Local component state only, never saved; wiring this up
// for real is a separate, later piece of work.
const NOTIFICATION_ROWS: { key: string; label: string; hint: string; defaultOn: boolean }[] = [
  {
    key: "new_hospital",
    label: "New Hospital Registration",
    hint: "Notify team when a new hospital signs up",
    defaultOn: true,
  },
  {
    key: "subscription_expiring",
    label: "Subscription Expiring",
    hint: "Alert when a subscription is expiring (7 days)",
    defaultOn: true,
  },
  {
    key: "payment_failures",
    label: "Payment Failures",
    hint: "Notify on failed payments",
    defaultOn: true,
  },
  {
    key: "system_alerts",
    label: "System Alerts",
    hint: "Critical system and security alerts",
    defaultOn: true,
  },
  {
    key: "weekly_summary",
    label: "Weekly Summary",
    hint: "Send weekly platform summary",
    defaultOn: false,
  },
];

export function NotificationsTab() {
  const [enabled, setEnabled] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(NOTIFICATION_ROWS.map((r) => [r.key, r.defaultOn])),
  );
  const [recipients, setRecipients] = useState<string[]>([]);
  const [recipientDraft, setRecipientDraft] = useState("");

  function addRecipient() {
    const email = recipientDraft.trim();
    if (!email || recipients.includes(email)) return;
    setRecipients((prev) => [...prev, email]);
    setRecipientDraft("");
  }

  return (
    <Card className="p-space-5">
      <div className="mb-space-3 gap-space-3 flex items-start justify-between">
        <div className="gap-space-2 flex items-start">
          <Bell size={18} className="text-ink-600 mt-0.5 shrink-0" />
          <div>
            <h2 className="text-ink-900 text-[15px] font-bold">Notification Rules</h2>
            <p className="text-ink-400 text-[12.5px]">Configure system notifications and alerts.</p>
          </div>
        </div>
        <Badge tone="clay">Mock</Badge>
      </div>

      <div className="space-y-space-3 mb-space-4">
        {NOTIFICATION_ROWS.map((row) => (
          <div key={row.key} className="gap-space-3 flex items-center justify-between">
            <div>
              <p className="text-ink-900 text-[13.5px] font-semibold">{row.label}</p>
              <p className="text-hint">{row.hint}</p>
            </div>
            <Switch
              checked={enabled[row.key]}
              onChange={() => setEnabled((prev) => ({ ...prev, [row.key]: !prev[row.key] }))}
              aria-label={row.label}
            />
          </div>
        ))}
      </div>

      <Field label="Notification Recipients">
        <div className="gap-space-2 mb-space-2 flex flex-wrap">
          {recipients.map((email) => (
            <span
              key={email}
              className="gap-space-1 px-space-2 text-ink-700 inline-flex items-center rounded-full bg-black/4 py-1 text-[12px]"
            >
              {email}
              <button
                type="button"
                onClick={() => setRecipients((prev) => prev.filter((e) => e !== email))}
                aria-label={`Remove ${email}`}
                className="text-ink-400 hover:text-error"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
        <div className="gap-space-2 flex">
          <Input
            type="email"
            placeholder="name@example.com"
            value={recipientDraft}
            onChange={(e) => setRecipientDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addRecipient();
              }
            }}
          />
          <Button type="button" variant="secondary" onClick={addRecipient}>
            Add
          </Button>
        </div>
      </Field>

      <p className="text-hint mt-space-3">
        Preview only -- no email/SMS is sent yet. This will be wired up to a real notification
        pipeline later.
      </p>
    </Card>
  );
}
