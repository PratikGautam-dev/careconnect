"use client";

import { useState } from "react";
import { CheckCircle2, MessageCircle, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { portalFetch } from "@/lib/portalAuth";
import { hasPermission, useStaffSession } from "@/lib/staffAuth";
import { useBookingChannels } from "@/hooks/useBookingChannels";
import { usePortalSettings } from "@/hooks/usePortalSettings";

type ConnectionStatus = {
  connected: boolean;
  error: string | null;
  display_phone_number?: string;
  verified_name?: string;
  quality_rating?: string;
};

/** Status/config page for the WhatsApp booking channel -- matches
 * ShopConnect's own WhatsApp channel page shape (one status strip, one
 * "Ordering bot" card with inline-saved fields, a connection check) rather
 * than this project's earlier generic layout. */
export default function WhatsAppChannelPage() {
  const { hospital, ready } = usePortalGuard();
  const session = useStaffSession();
  const {
    info, error: channelsError,
    whatsappBookingEnabled, setWhatsappBookingEnabled, togglingWhatsapp,
  } = useBookingChannels(ready);
  const canManage = hasPermission(session, "settings", "write");
  const { settings, setSettings, error, saving, handleSave } = usePortalSettings(ready);

  const [checking, setChecking] = useState(false);
  const [status, setStatus] = useState<ConnectionStatus | null>(null);

  async function checkConnection() {
    setChecking(true);
    const result = await portalFetch("/api/portal/channels/whatsapp/connection-status");
    setChecking(false);
    if (result.ok) setStatus(result.data as ConnectionStatus);
  }

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="channels-whatsapp">
      <PageHeader
        title="WhatsApp"
        description="Patients book, reschedule, and cancel appointments through WhatsApp conversations."
      />

      {(channelsError || error) && (
        <p className="mb-space-4 text-error text-[13px]">{channelsError || error}</p>
      )}

      {/* Status strip */}
      <Card className="p-space-4 mb-space-4 gap-space-3 flex items-center">
        <Badge tone={whatsappBookingEnabled ? "success" : "neutral"}>
          {whatsappBookingEnabled ? "Connected" : "Off"}
        </Badge>
        <span className="text-ink-600 flex-1 text-[13px]">
          {info?.whatsapp_phone_number_id
            ? `WhatsApp is set up (${info.whatsapp_phone_number_id}).`
            : "WhatsApp isn't set up yet."}
        </span>
        <a href="/portal/settings" className="text-brand-600 hover:text-brand-700 text-[12.5px] font-semibold">
          Manage in Settings →
        </a>
      </Card>

      <div className="space-y-space-4">
      {/* Booking bot card */}
      <Card className="p-space-5">
        <div className="gap-space-3 flex items-start justify-between">
          <div className="gap-space-3 flex items-start">
            <div className="bg-success-tint text-success flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
              <MessageCircle size={18} />
            </div>
            <div>
              <p className="text-ink-900 text-[14px] font-semibold">Booking bot</p>
              <p className="text-hint mt-space-1 max-w-md text-[12.5px]">
                Patients who message your WhatsApp number can browse departments and doctors, pick
                a slot, and confirm an appointment without leaving the chat.
              </p>
            </div>
          </div>
          {canManage && (
            <div className="gap-space-2 flex shrink-0 items-center">
              <span className="text-ink-600 text-[11.5px] font-bold uppercase">
                {whatsappBookingEnabled ? "On" : "Off"}
              </span>
              <Switch
                checked={whatsappBookingEnabled}
                onChange={() => setWhatsappBookingEnabled(!whatsappBookingEnabled)}
                disabled={togglingWhatsapp}
              />
            </div>
          )}
        </div>

        {canManage && (
          <form onSubmit={handleSave} className="mt-space-4">
            <div className="border-line pt-space-3 border-t">
              <Field label="Welcome message" className="mb-space-2">
                <Textarea
                  rows={3}
                  value={settings?.welcome_message_text ?? ""}
                  onChange={(e) =>
                    settings && setSettings({ ...settings, welcome_message_text: e.target.value })
                  }
                  disabled={!settings}
                  placeholder="e.g. Namaste! Welcome to City Hospital. How can we help you today?"
                />
              </Field>
              <div className="gap-space-2 flex items-center">
                <Button type="submit" variant="secondary" size="md" disabled={!settings || saving}>
                  {saving ? "Saving…" : "Save"}
                </Button>
                <p className="text-hint text-[12px]">
                  Shown when a patient starts a chat. Leave empty for a default greeting using your
                  hospital&apos;s name.
                </p>
              </div>
            </div>

            <div className="border-line mt-space-4 pt-space-3 border-t">
              <Field label="Start over after (minutes)" className="mb-0">
                <div className="gap-space-3 flex items-center">
                  <Input
                    type="number"
                    min={2}
                    max={120}
                    value={settings?.session_timeout_minutes ?? 30}
                    onChange={(e) =>
                      settings &&
                      setSettings({ ...settings, session_timeout_minutes: Number(e.target.value) })
                    }
                    disabled={!settings}
                    className="w-[140px]"
                  />
                  <Button type="submit" variant="secondary" size="md" disabled={!settings || saving}>
                    {saving ? "Saving…" : "Save"}
                  </Button>
                </div>
              </Field>
              <p className="text-hint mt-space-2 text-[12px]">
                A patient who goes quiet this long returns to the main menu on their next message.
                2–120 minutes.
              </p>
            </div>

            <div className="border-line mt-space-4 pt-space-3 border-t">
              <p className="text-ink-900 text-[13.5px] font-semibold">Appointment reminders</p>
              <p className="text-hint mt-space-1 mb-space-3 text-[12.5px] max-w-lg">
                Patients get a reminder before their appointment. If they haven&apos;t messaged you
                in the last 24 hours, WhatsApp only allows an approved template — create one in
                Meta&apos;s WhatsApp Manager.
              </p>
              <Field label="Template name" className="mb-0 max-w-sm">
                <div className="gap-space-3 flex items-center">
                  <Input
                    value={settings?.reminder_template_name ?? ""}
                    onChange={(e) =>
                      settings && setSettings({ ...settings, reminder_template_name: e.target.value })
                    }
                    disabled={!settings}
                    placeholder="appointment_reminder"
                    className="flex-1"
                  />
                  <Button type="submit" variant="secondary" size="md" disabled={!settings || saving}>
                    {saving ? "Saving…" : "Save"}
                  </Button>
                </div>
              </Field>
            </div>
          </form>
        )}
      </Card>

      {/* Connection check */}
      <Card className="p-space-5">
        <div className="gap-space-3 flex items-center justify-between">
          <div>
            <p className="text-ink-900 text-[14px] font-semibold">Connection</p>
            <p className="text-hint mt-space-1 text-[12.5px]">
              Check your WhatsApp Business number&apos;s live status with Meta.
            </p>
          </div>
          <Button variant="secondary" onClick={checkConnection} disabled={checking}>
            {checking ? "Checking…" : "Check connection"}
          </Button>
        </div>

        {status && (
          <div className="border-line mt-space-4 pt-space-3 border-t">
            {status.connected ? (
              <div className="gap-space-2 text-success flex items-start">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
                <div className="text-[13px]">
                  <p className="font-semibold">Connected</p>
                  {status.display_phone_number && <p>Number: {status.display_phone_number}</p>}
                  {status.verified_name && <p>Business name: {status.verified_name}</p>}
                  {status.quality_rating && <p>Quality rating: {status.quality_rating}</p>}
                </div>
              </div>
            ) : (
              <div className="gap-space-2 text-error flex items-start">
                <XCircle size={16} className="mt-0.5 shrink-0" />
                <div className="text-[13px]">
                  <p className="font-semibold">Not connected</p>
                  {status.error && <p className="text-hint mt-space-1">{status.error}</p>}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
      </div>
    </PortalShell>
  );
}
