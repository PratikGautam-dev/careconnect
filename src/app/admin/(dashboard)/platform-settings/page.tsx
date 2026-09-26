"use client";

import { useState } from "react";
import { Bell, ClipboardList, ListChecks, Settings as SettingsIcon } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { usePlatformSettings } from "@/hooks/usePlatformSettings";
import { AuditLogsTab } from "./_components/AuditLogsTab";
import { GeneralTab } from "./_components/GeneralTab";
import { MenuLabelsTab } from "./_components/MenuLabelsTab";
import { NotificationsTab } from "./_components/NotificationsTab";
import {
  SettingsTabsNav,
  type PlatformSettingsTabDef,
  type PlatformSettingsTabKey,
} from "./_components/SettingsTabsNav";

const TABS: PlatformSettingsTabDef[] = [
  { key: "general", label: "General", icon: SettingsIcon },
  { key: "menu_labels", label: "Menu Labels", icon: ListChecks },
  { key: "notifications", label: "Notifications", icon: Bell },
  { key: "audit_logs", label: "Audit Logs", icon: ClipboardList },
];

/** /admin/platform-settings -- same segmented-tab layout as /portal/settings
 * (SettingsTabsNav), just this page's own local copy/vocabulary since the
 * two pages' tabs are unrelated. Unlike the portal page, every tab here
 * shares ONE form/save (usePlatformSettings' single combined payload) --
 * tabs are purely a display filter over one draft, not independent
 * per-tab saves, so the Save button stays visible regardless of which tab
 * is active. Notifications is the one exception: it's a local-only design
 * preview (see NotificationsTab's own docstring), not part of the saved
 * payload at all. */
function PlatformSettingsForm() {
  const {
    settings,
    maxActiveLinks,
    setMaxActiveLinks,
    featureLabels,
    setFeatureLabel,
    dpdpRequired,
    setDpdpRequired,
    auditLogRetentionDays,
    setAuditLogRetentionDays,
    error,
    saved,
    saving,
    handleSubmit,
  } = usePlatformSettings();

  const [tab, setTab] = useState<PlatformSettingsTabKey>("general");

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Platform settings</h1>
        <p className="text-ink-600 text-[13px]">
          Global values that apply identically across every hospital — no per-tenant override.
        </p>
      </div>

      {!settings ? (
        <Card className="p-space-5">
          <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
        </Card>
      ) : (
        <form onSubmit={handleSubmit} className="gap-space-5 flex flex-col">
          <SettingsTabsNav tabs={TABS} active={tab} onChange={setTab} />

          {tab === "general" && (
            <GeneralTab
              maxActiveLinks={maxActiveLinks}
              setMaxActiveLinks={setMaxActiveLinks}
              dpdpRequired={dpdpRequired}
              setDpdpRequired={setDpdpRequired}
              error={error}
            />
          )}
          {tab === "menu_labels" && (
            <MenuLabelsTab
              defaultLabels={settings.feature_default_labels}
              featureLabels={featureLabels}
              setFeatureLabel={setFeatureLabel}
            />
          )}
          {tab === "notifications" && <NotificationsTab />}
          {tab === "audit_logs" && (
            <AuditLogsTab
              auditLogRetentionDays={auditLogRetentionDays}
              setAuditLogRetentionDays={setAuditLogRetentionDays}
            />
          )}

          <div className="gap-space-3 border-line pt-space-4 flex items-center border-t">
            {saved && <p className="text-success text-[13px]">Saved.</p>}
            <Button type="submit" disabled={saving || !maxActiveLinks} className="ml-auto">
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

export default function PlatformSettingsPage() {
  return <PlatformSettingsForm />;
}
